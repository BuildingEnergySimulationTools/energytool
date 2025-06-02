import enum

import pandas as pd
from eppy.modeleditor import IDF

from energytool.base.units import Units
from energytool.system import System, SystemCategories


class OutputCategories(enum.Enum):
    RAW = "RAW"
    SYSTEM = "SYSTEM"
    SENSOR = "SENSOR"


def get_results(
    idf: IDF,
    eplus_res: pd.DataFrame,
    outputs: str,
    systems: dict[SystemCategories, list[System]] = None,
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
            results = get_system_energy_results(idf, systems, eplus_res)
            if results is not None:
                to_return.append(results)
        elif output_cat == OutputCategories.SENSOR.value:
            results = get_sensor_results(idf, systems, eplus_res)
            if results is not None:
                to_return.append(results)

        else:
            raise ValueError(f"{output_cat} not recognized or not yet implemented")

    if to_return:
        concatenated = pd.concat(to_return, axis=1)
        concatenated = concatenated.loc[
            :, ~concatenated.columns.duplicated()
        ]  # to avoid duplicates

        return concatenated


def get_sensor_results(
    idf: IDF,
    systems: dict[SystemCategories, list[System]],
    eplus_res: pd.DataFrame,
):
    result_list = []
    for sens in systems[SystemCategories.SENSOR]:
        result_list.append(sens.post_process(idf, eplus_res))
    return pd.concat(result_list, axis=1)


def get_system_energy_results(
    idf: IDF,
    systems: dict[SystemCategories, list[System]],
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
    hvac_list = [
        SystemCategories.HEATING,
        SystemCategories.COOLING,
        SystemCategories.AUXILIARY,
        SystemCategories.DHW,
        SystemCategories.VENTILATION,
        SystemCategories.LIGHTING,
    ]

    for cat in hvac_list:
        syst_list = systems[cat]
        if syst_list:
            cat_res = []
            for system in syst_list:
                res = system.post_process(idf, eplus_results=eplus_res)
                if res is not None:
                    unit = Units.ENERGY.value
                    unit = unit.replace("[", r"\[").replace("]", r"\]")
                    cat_res.append(
                        res.loc[:, res.columns.str.contains(unit, regex=True)]
                    )
            if cat_res:
                cat_res_series = pd.concat(cat_res, axis=1).sum(axis=1)
                cat_res_series.name = f"{cat.value}_{Units.ENERGY.value}"
                sys_nrj_res.append(cat_res_series)

    if sys_nrj_res:
        sys_nrj_res_df = pd.concat(sys_nrj_res, axis=1)
        sys_nrj_res_df[f"TOTAL_SYSTEM_{Units.ENERGY.value}"] = sys_nrj_res_df.sum(
            axis=1
        )
        return sys_nrj_res_df
