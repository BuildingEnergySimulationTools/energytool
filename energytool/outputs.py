import enum
import pandas as pd
import numpy as np

from energytool.base.parse_results import get_output_variable

from energytool.system import System, SystemCategories
from typing import Dict, List
from eppy.modeleditor import IDF
from energytool.base.units import Units


class OutputCategories(enum.Enum):
    RAW = "RAW"
    SYSTEM = "SYSTEM"
    OVERSHOOT_28 = "OVERSHOOT_28"
    OPERATIVE_TEMPERATURES = "OPERATIVE_TEMPERATURES"


def get_systems_results(
    idf: IDF,
    eplus_res: pd.DataFrame,
    outputs: str,
    systems: Dict[SystemCategories, List[System]] = None,
):
    """
    Retrieve HVAC systems results based on specified output categories.

    :param eplus_res: DataFrame containing EnergyPlus simulation results.
    :param outputs: String containing pipe-separated output categories
        (e.g., "RAW|SYSTEM"). Categories must be values from OutputCategories enum
    :param idf: IDF object representing the EnergyPlus input data.
    :param systems: Optional, dictionary mapping SystemCategories to lists of System
        objects.
    :return: A DataFrame containing the concatenated results based on the specified
        categories.
    """
    to_return = []
    split_outputs = outputs.split("|")
    for output_cat in split_outputs:
        if output_cat == OutputCategories.RAW.value:
            to_return.append(eplus_res)
        elif output_cat == OutputCategories.SYSTEM.value:
            to_return.append(get_system_energy_results(idf, systems, eplus_res))
        else:
            raise ValueError(f"{output_cat} not recognized or not yet implemented")

    return pd.concat(to_return, axis=1)


def get_system_energy_results(
    idf: IDF,
    systems: Dict[SystemCategories, List[System]],
    eplus_res: pd.DataFrame,
):
    """
    Retrieve energy results for systems contains in the SystemCategories.
    If several systems are present in a category, it will return the sum of there
    energy use.
    The energy absorbed by a system is identified by the ENERGY_[J] tag in its name.
    A TOTAL_ENERGY_[J] column sums all the energy consumed by the systems

    :param idf: IDF object representing the EnergyPlus input data.
    :param systems: Dictionary mapping SystemCategories to lists of System objects.
    :param eplus_res: DataFrame containing EnergyPlus simulation results.
    :return: A DataFrame containing energy results for different system categories.
    """
    sys_nrj_res = []
    for cat in SystemCategories:
        syst_list = systems[cat]
        if syst_list:
            cat_res = []
            for system in syst_list:
                res = system.post_process(idf, eplus_results=eplus_res)
                unit = Units.ENERGY.value
                unit = unit.replace("[", r"\[").replace("]", r"\]")
                cat_res.append(res.loc[:, res.columns.str.contains(unit, regex=True)])
            cat_res_series = pd.concat(cat_res, axis=1).sum(axis=1)
            cat_res_series.name = f"{cat.value}_{Units.ENERGY.value}"
            sys_nrj_res.append(cat_res_series)

    sys_nrj_res_df = pd.concat(sys_nrj_res, axis=1)
    sys_nrj_res_df[f"TOTAL_SYSTEM_{Units.ENERGY.value}"] = sys_nrj_res_df.sum(axis=1)
    return sys_nrj_res_df


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
