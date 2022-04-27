import numpy as np

from energytool.tools import format_input_to_list


def get_objects_name_list(idf, idf_object):
    return [obj.Name for obj in idf.idfobjects[idf_object]]


def is_value_in_object_fieldnames(idf, idf_object, field_name, values):
    """
    :param values:
    :param idf:
    :param idf_object
    :param field_name:
    :return: list of Boolean.

    For  each instance of the idf_object in the idf.
    Return True if specific field_name as variables value
    """
    idf_object = idf_object.upper()
    values_list = format_input_to_list(values)

    try:
        outputs = idf.idfobjects[idf_object]
    except KeyError:
        outputs = []

    var_in_idf = [out[field_name] for out in outputs]

    return [
        True if elmt in values_list
        else False
        for elmt in var_in_idf]


def set_object_field_value(
        idf, idf_object, field_name, value, idf_object_name=None):
    try:
        obj_list = idf.idfobjects[idf_object]
    except KeyError:
        print("Unknown EnergyPlus idf_object")
        obj_list = []

    if not obj_list:
        raise ValueError("No idf_object was found")

    for obj in obj_list:
        if idf_object_name is not None:
            idf_object_name_list = format_input_to_list(idf_object_name)
            if obj.Name in idf_object_name_list:
                obj[field_name] = value
        else:
            obj[field_name] = value


def set_run_period(idf, simulation_start, simulation_stop):
    run_period_list = idf.idfobjects["RunPeriod"]
    run_period_list.clear()
    idf.newidfobject(
        "RunPeriod",
        Name="run_period",
        Begin_Month=simulation_start.month,
        Begin_Day_of_Month=simulation_start.day,
        Begin_Year=simulation_start.year,
        End_Month=simulation_stop.month,
        End_Day_of_Month=simulation_stop.day,
        End_Year=simulation_stop.year,
        Day_of_Week_for_Start_Day=simulation_start.strftime('%A'),
        Use_Weather_File_Holidays_and_Special_Days="No",
        Use_Weather_File_Daylight_Saving_Period="No",
        Apply_Weekend_Holiday_Rule="Yes",
        Use_Weather_File_Rain_Indicators="Yes",
        Use_Weather_File_Snow_Indicators="Yes",
        Treat_Weather_as_Actual="No"
    )


def set_timestep(idf, nb_timestep_per_hour):
    timestep_list = idf.idfobjects["Timestep"]
    timestep_list.clear()
    idf.newidfobject(
        "Timestep",
        Number_of_Timesteps_per_Hour=nb_timestep_per_hour
    )


def output_zone_variable_present(idf, zones, variables):
    zones_bool = is_value_in_object_fieldnames(
        idf, "Output:Variable", "Key_Value", zones)

    all_zones_bool = is_value_in_object_fieldnames(
        idf, "Output:Variable", "Key_Value", "*")

    zones_bool = np.logical_or(zones_bool, all_zones_bool)

    variables_bool = is_value_in_object_fieldnames(
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
    to_delete = is_value_in_object_fieldnames(
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
