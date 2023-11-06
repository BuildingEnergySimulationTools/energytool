import datetime as dt
import re
from pathlib import Path

import numpy as np
import pandas as pd

from energytool.tools import to_list


def eplus_date_parser(timestamp: str) -> dt.datetime:
    """Convert energyplus timestamp to datetime."""
    if not isinstance(timestamp, str):
        raise TypeError()

    timestamp = timestamp.lstrip()
    if " 24:" in timestamp:
        # EnergyPlus works with 1-24h and python with 0-23h
        timestamp = timestamp.replace(" 24:", " 23:")
        return dt.datetime.strptime(timestamp, "%m/%d %H:%M:%S")
    return dt.datetime.strptime(timestamp, "%m/%d %H:%M:%S") - dt.timedelta(hours=1)


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
        results = pd.read_csv(file_path, index_col=0)
    except FileNotFoundError:
        raise ValueError("EnergyPlus result file not found")
    results.index = [eplus_date_parser(ind) for ind in results.index]

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
    variables: str | list,
    key_values: str | list = "*",
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
