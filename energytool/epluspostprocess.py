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
                time = timestamp.replace('24', '23')
                time = dt.datetime.strptime(time, ' %m/%d %H:%M:%S')
            except ValueError:
                time = timestamp.replace('24', '23')
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

    # Careful here, not sure what will happen with leap years
    if ref_year is not None:
        results.index = results.index.map(
            lambda t: t.replace(year=int(ref_year)))

    return results


def contains_regex(elmt_list):
    tempo = [elmt + ".+|" for elmt in elmt_list]
    return ''.join(tempo)[:-1]


def get_output_zone_variable(eplus_res, zones, variables):

    if zones == '*':
        zone_mask = np.full((1, eplus_res.shape[1]), True).flatten()
    else:
        zone_list = format_input_to_list(zones)
        zone_list_upper = [elmt.upper() for elmt in zone_list]
        reg_zone = contains_regex(zone_list_upper)
        zone_mask = eplus_res.columns.str.contains(reg_zone)

    variable_names_list = format_input_to_list(variables)
    reg_var = contains_regex(variable_names_list)
    variable_mask = eplus_res.columns.str.contains(reg_var)

    mask = np.logical_and(zone_mask, variable_mask)

    return eplus_res.loc[:, mask]
