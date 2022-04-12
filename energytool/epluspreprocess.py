import numpy as np

from energytool.tools import format_input_to_list
from energytool.tools import value_in_object_fieldnames


def output_zone_variable_present(idf, zones, variables):
    zones_bool = value_in_object_fieldnames(
        idf, "Output:Variable", "Key_Value", zones)

    all_zones_bool = value_in_object_fieldnames(
        idf, "Output:Variable", "Key_Value", "*")

    zones_bool = np.logical_or(zones_bool, all_zones_bool)

    variables_bool = value_in_object_fieldnames(
        idf, "Output:Variable", "Variable_Name", variables)

    return np.logical_and(zones_bool, variables_bool)


def del_output_zone_variable(idf, zones, variables):
    output_list = idf.idfobjects["OUTPUT:VARIABLE"]
    to_delete = output_zone_variable_present(idf, zones, variables)

    if np.any(to_delete):
        indices_to_remove = [i for i, trig in enumerate(to_delete) if trig]

        for idx in sorted(indices_to_remove, reverse=True):
            del output_list[idx]


def del_output_variable(idf, variables):
    output_list = idf.idfobjects["OUTPUT:VARIABLE"]
    to_delete = value_in_object_fieldnames(
        idf, "Output:Variable", "Variable_Name", variables)

    if np.any(to_delete):
        indices_to_remove = [i for i, trig in enumerate(to_delete) if trig]

        for idx in sorted(indices_to_remove, reverse=True):
            del output_list[idx]


def add_output_zone_variable(idf, zones, variables,
                             reporting_frequency="Hourly"):
    zones_list = format_input_to_list(zones)
    variables_list = format_input_to_list(variables)

    for zne in zones_list:
        for var in variables_list:
            if not np.any(output_zone_variable_present(idf, zne, var)):
                if zne == "*":
                    del_output_variable(idf, var)

                idf.newidfobject(
                    "OUTPUT:VARIABLE",
                    Key_Value=zne,
                    Variable_Name=var,
                    Reporting_Frequency=reporting_frequency
                )
