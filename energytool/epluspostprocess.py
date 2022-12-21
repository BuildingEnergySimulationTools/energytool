import re

import pandas as pd
import numpy as np
import datetime as dt

from energytool.tools import format_input_to_list


def eplus_date_parser(timestamp):
    """Because EnergyPlus works with 1-24h and python with 0-23h"""
    try:
        time = dt.datetime.strptime(timestamp, ' %m/%d %H:%M:%S')
        time += -dt.timedelta(hours=1)

    except ValueError:
        try:
            time = dt.datetime.strptime(timestamp, '%m/%d %H:%M:%S')
            time += -dt.timedelta(hours=1)

        except ValueError:
            try:
                time = timestamp.replace('24:', '23:')
                time = dt.datetime.strptime(time, ' %m/%d %H:%M:%S')
            except ValueError:
                time = timestamp.replace('24:', '23:')
                time = dt.datetime.strptime(time, '%m/%d %H:%M:%S')

    return time


def read_eplus_res(file_path, ref_year=None):
    try:
        results = pd.read_csv(
            file_path,
            index_col=0,
            parse_dates=True,
            date_parser=eplus_date_parser
        )
    except FileNotFoundError:
        print("EnergyPlus output file not found, "
              "Empty DataFrame is returned")
        return pd.DataFrame()

    if not ref_year:
        ref_year = dt.datetime.today().year

    timestep = results.index[1] - results.index[0]
    dt_range = pd.date_range(
        results.index[0].replace(year=int(ref_year)),
        periods=results.shape[0],
        freq=timestep
    )
    dt_range.name = 'Date/Time'
    results.index = dt_range

    return results


def zone_contains_regex(elmt_list):
    tempo = [elmt + ":.+|" for elmt in elmt_list]
    return ''.join(tempo)[:-1]


def variable_contains_regex(elmt_list):
    if not elmt_list:
        return None
    tempo = [elmt + ".+|" for elmt in elmt_list]
    return ''.join(tempo)[:-1]


def get_output_variable(
        eplus_res, variables, key_values='*', drop_suffix=True):
    if key_values == '*':
        key_mask = np.full((1, eplus_res.shape[1]), True).flatten()
    else:
        key_list = format_input_to_list(key_values)
        key_list_upper = [elmt.upper() for elmt in key_list]
        reg_key = zone_contains_regex(key_list_upper)
        key_mask = eplus_res.columns.str.contains(reg_key)

    variable_names_list = format_input_to_list(variables)
    reg_var = variable_contains_regex(variable_names_list)
    variable_mask = eplus_res.columns.str.contains(reg_var)

    mask = np.logical_and(key_mask, variable_mask)

    results = eplus_res.loc[:, mask]

    if drop_suffix:
        new_columns = [re.sub(f':{variables}.+', '', col)
                       for col in results.columns]
        results.columns = new_columns

    return results


def get_aggregated_indicator(simulation_list,
                             results_group='building_results',
                             indicator='Total',
                             method=np.sum,
                             method_args=None,
                             reference=None):
    if not simulation_list:
        raise ValueError("Empty simulation list. "
                         "Cannot perform indicator aggregation")

    first_build = simulation_list[0].building
    available = list(first_build.building_results.columns)
    available += list(first_build.energyplus_results.columns)
    available.append("Total")

    if indicator not in available:
        raise ValueError("Indicator is not present in building_results or "
                         "in energyplus_results")

    y_df = pd.concat([
        getattr(sim.building, results_group)[indicator]
        for sim in simulation_list
    ], axis=1)

    if reference is None:
        return method(y_df).to_numpy()

    elif method_args is None:
        return np.array([
            method(reference, y_df.iloc[:, i])
            for i in range(y_df.shape[1])
        ])

    else:
        return np.array([
            method(reference, y_df.iloc[:, i], **method_args)
            for i in range(y_df.shape[1])
        ])




