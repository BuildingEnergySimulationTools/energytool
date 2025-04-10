import pandas as pd
import datetime as dt


def to_list(f_input):
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
        raise ValueError(
            f"{f_input} must be an instance of str, int, float or list."
            f"Got {type(f_input)} instead"
        )


def select_in_list(target_list: list, target: str | list):
    """
    Select elements from a list based on a target string or a list of target strings.

    :param target_list: The source list from which elements will be selected.
    :param target: A string or a list of strings to match against elements in
    the target_list. If "*", all elements in the target_list are returned.

    :return: A list containing the selected elements from the target_list.
    """
    select_by_list = to_list(target)

    if target == "*":
        return target_list

    output_list = []
    for elmt in select_by_list:
        for items in target_list:
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


def is_items_in_list(items: str | list, target_list: list):
    """
    This function checks whether one or more items (strings or lists) are present
    within the target list.

    :param target_list: The list to search for items.
    :param items: The item(s) to check for presence in the target list. This can be a
    single string or a list of strings.
    :return: A list of Boolean values indicating whether each item is present in the
    target list.
    """
    items = to_list(items)
    return [True if elmt in target_list else False for elmt in items]


class Scheduler:
    def __init__(self, name, year=None):
        self.name = name
        if year is None:
            year = dt.datetime.today().year
        self.year = year
        self.series = pd.Series(
            index=pd.date_range(f"{year}-01-01 00:00:00", freq="h", periods=8760),
            name=name,
            dtype="float64",
        )

    def add_day_in_period(self, start, end, days, hourly_dict):
        start = dt.datetime.strptime(start, "%Y-%m-%d")
        end = dt.datetime.strptime(end, "%Y-%m-%d")
        end = end.replace(hour=23)

        if start.year != self.year or end.year != end.year:
            raise ValueError("start date or end date is out of bound ")

        day_list = to_list(days)
        period = self.series.loc[start:end]

        selected_timestamp = [idx for idx in period.index if idx.day_name() in day_list]

        self.series.loc[selected_timestamp] = hourly_lst_from_dict(hourly_dict) * int(
            len(selected_timestamp) / 24
        )
