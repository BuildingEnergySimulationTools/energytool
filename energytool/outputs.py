import datetime as dt
import pandas as pd

from pathlib import Path


def eplus_date_parser(timestamp: str):
    """Convert energyplus timestamp to datetime."""
    try:
        time = dt.datetime.strptime(timestamp, " %m/%d %H:%M:%S")
        time += -dt.timedelta(hours=1)

    except ValueError:
        try:
            time = dt.datetime.strptime(timestamp, "%m/%d %H:%M:%S")
            time += -dt.timedelta(hours=1)

        except ValueError:
            # Because EnergyPlus works with 1-24h and python with 0-23h
            try:
                time = timestamp.replace("24:", "23:")
                time = dt.datetime.strptime(time, " %m/%d %H:%M:%S")
            except ValueError:
                time = timestamp.replace("24:", "23:")
                time = dt.datetime.strptime(time, "%m/%d %H:%M:%S")

    return time


def read_eplus_res(file_path: Path, ref_year: int = None):
    """
    Read EnergyPlus result data from output CSV file and adjust the date/time index.

    Parameters:
    - file_path (Path): The path to the EnergyPlus result file in CSV format.
    - ref_year (int, optional): The reference year for adjusting the date/time index.
      If not provided, the current year will be used as the reference year.

    Returns:
    - results (DataFrame): A pandas DataFrame containing the EnergyPlus result data
      with the adjusted date/time index.

    Raises:
    - ValueError: If the specified EnergyPlus result file is not found.
    """
    try:
        results = pd.read_csv(
            file_path, index_col=0, parse_dates=True, date_parser=eplus_date_parser
        )
    except FileNotFoundError:
        raise ValueError("EnergyPlus result file not found")

    if ref_year is None:
        ref_year = dt.datetime.today().year

    timestep = results.index[1] - results.index[0]
    dt_range = pd.date_range(
        results.index[0].replace(year=int(ref_year)),
        periods=results.shape[0],
        freq=timestep,
    )
    dt_range.name = "Date/Time"
    results.index = dt_range

    return results


def system_energy_results(self):
    system_dict = {
        "Heating": self.heating_system,
        "Cooling": self.cooling_system,
        "Ventilation": self.ventilation_system,
        "Lighting": self.artificial_lighting_system,
        "DHW": self.dwh_system,
        "Local_production": self.pv_production,
    }

    sys_nrj_res = pd.DataFrame(columns=system_dict.keys())
    if self.building_results.empty:
        return sys_nrj_res

    for header, systems in system_dict.items():
        if systems:
            to_find = variable_contains_regex([sys.name for sys in systems.values()])
            mask = self.building_results.columns.str.contains(to_find)
            res = self.building_results.loc[:, mask]
            sys_nrj_res[header] = res.sum(axis=1)
        else:
            sys_nrj_res[header] = pd.Series(
                self.building_results.shape[0] * [0.0],
                index=self.building_results.index,
            )
    sys_nrj_res["Total"] = sys_nrj_res.sum(axis=1)
    return sys_nrj_res


@property
def overshoot_thermal_comfort(self):
    if self.energyplus_results.empty:
        raise ValueError("No energyplus results available")

    year = self.building_results.index[0].year
    begin_loc = f"{year}-{self.month_summer_begins}"
    end_loc = f"{year}-{self.month_summer_ends}"

    zones_top = po.get_output_variable(
        self.energyplus_results,
        "Zone Operative Temperature",
        self.zone_name_list,
    )

    zones_occupation = po.get_output_variable(
        self.energyplus_results,
        "Zone People Occupant Count",
        self.zone_name_list,
    )

    zones_top = zones_top.loc[begin_loc:end_loc, :]
    zones_occupation = zones_occupation.loc[begin_loc:end_loc, :]

    zones_top_hot = zones_top > self.summer_comfort_top
    zones_is_someone = zones_occupation > 0

    shared_zones = list(set(zones_top_hot) & set(zones_is_someone))

    zone_hot_and_someone = np.logical_and(
        zones_top_hot[shared_zones], zones_is_someone[shared_zones]
    )

    return (zone_hot_and_someone.sum() / zones_is_someone.sum()) * 100
