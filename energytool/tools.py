import pandas as pd
import datetime as dt


def format_input_to_list(f_input):
    """
    Convert a string into a list
    return f_input if f_input is a list
    else raise ValueError

    :param f_input:
    :return: list
    """
    if isinstance(f_input, (str, int, float)):
        return [f_input]
    elif isinstance(f_input, list):
        return f_input
    else:
        raise ValueError("Input must be a string an interger a "
                         "float or a list")


def select_by_strings(items_list, select_by):
    select_by_list = format_input_to_list(select_by)

    if select_by == '*':
        return items_list

    output_list = []
    for elmt in select_by_list:
        for items in items_list:
            if elmt in items:
                output_list.append(items)

    return output_list


def hourly_lst_from_dict(hourly_dict):
    if list(hourly_dict.keys())[-1] != 24:
        raise ValueError("Last dict key must be 24")

    val_list = []
    for hour, val in hourly_dict.items():
        val_list += [val for _ in range(len(val_list), hour)]

    return val_list


def is_list_items_in_list(tested_list, reference_list):
    return [
        True if elmt in reference_list
        else False
        for elmt in tested_list]


class Scheduler:
    def __init__(self, name, year=dt.datetime.today().year):
        self.name = name
        self.year = year
        self.series = pd.Series(
            index=pd.date_range(
                f'{year}-01-01 00:00:00', freq="H", periods=8760),
            name=name,
            dtype='float64'
        )

    def add_day_in_period(self, start, end, days, hourly_dict):
        start = dt.datetime.strptime(start, '%Y-%m-%d')
        end = dt.datetime.strptime(end, '%Y-%m-%d')
        end = end.replace(hour=23)

        if start.year != self.year or end.year != end.year:
            raise ValueError("start date or end date is out of bound ")

        day_list = format_input_to_list(days)
        period = self.series.loc[start: end]

        selected_timestamp = [idx for idx in period.index
                              if idx.day_name() in day_list]

        self.series.loc[selected_timestamp] = hourly_lst_from_dict(
            hourly_dict) * int(len(selected_timestamp) / 24)
