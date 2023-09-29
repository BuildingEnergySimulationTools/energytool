import datetime as dt
import re

import pandas as pd
import numpy as np

from pathlib import Path

from energytool.tools import to_list

from typing import Union


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


def overshoot_thermal_comfort(self):
    if self.energyplus_results.empty:
        raise ValueError("No energyplus results available")

    year = self.building_results.index[0].year
    begin_loc = f"{year}-{self.month_summer_begins}"
    end_loc = f"{year}-{self.month_summer_ends}"

    zones_top = get_output_variable(
        self.energyplus_results,
        "Zone Operative Temperature",
        self.zone_name_list,
    )

    zones_occupation = get_output_variable(
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


def zone_contains_regex(elmt_list):
    tempo = [elmt + ":.+|" for elmt in elmt_list]
    return "".join(tempo)[:-1]


def variable_contains_regex(elmt_list):
    if not elmt_list:
        return None
    tempo = [elmt + ".+|" for elmt in elmt_list]
    return "".join(tempo)[:-1]


def get_output_variable(
    eplus_res: pd.DataFrame,
    variables: Union[str, list],
    key_values: Union[str, list] = "*",
    drop_suffix=True,
) -> pd.DataFrame:
    """
    This function allows you to extract specific output variables from an EnergyPlus
     result DataFrame based on the provided variable names and key values.

    :param eplus_res: A pandas DataFrame containing EnergyPlus simulation results.
        Index is a DateTimeIndex, columns are output variables
    :param variables: The names of the specific output variables to retrieve.
        This can be a single variable name (string) or a list of variable names
        (list of strings).
    :param key_values: (Optional) The key values that identify the simulation
        outputs. This can be a single key value (string) or a list of key values
        (list of strings). By default, "*" is used to retrieve variables for all
        key values.
    :param drop_suffix: (Optional) If True, remove the suffixes from the column
        names in the returned DataFrame. Default is True.
    :return: A DataFrame containing the selected output variables.
    Example:
    ```
    get_output_variable(
        eplus_res=toy_df,
        key_values="Zone1",
        variables="Equipment Total Heating Energy",
    )


    get_output_variable(
        eplus_res=toy_df,
        key_values=["Zone1", "ZONE2"],
        variables="Equipment Total Heating Energy",
    )

    get_output_variable(
        eplus_res=toy_df,
        key_values="*",
        variables="Equipment Total Heating Energy",
    )

    get_output_variable(
        eplus_res=toy_df,
        key_values="Zone1",
        variables=[
            "Equipment Total Heating Energy",
            "Ideal Loads Supply Air Total Heating Energy",
        ],
    )
    ```

    """
    if key_values == "*":
        key_mask = np.full((1, eplus_res.shape[1]), True).flatten()
    else:
        key_list = to_list(key_values)
        key_list_upper = [elmt.upper() for elmt in key_list]
        reg_key = zone_contains_regex(key_list_upper)
        key_mask = eplus_res.columns.str.contains(reg_key)

    variable_names_list = to_list(variables)
    reg_var = variable_contains_regex(variable_names_list)
    variable_mask = eplus_res.columns.str.contains(reg_var)

    mask = np.logical_and(key_mask, variable_mask)

    results = eplus_res.loc[:, mask]

    if drop_suffix:
        new_columns = [re.sub(f":{variables}.+", "", col) for col in results.columns]
        results.columns = new_columns

    return results
