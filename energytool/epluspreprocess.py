import numpy as np
from pathlib import Path

import pandas as pd

import os
import uuid
import tempfile
import energytool.tools as tl
import eppy

from eppy.modeleditor import IDF

RESOURCES_PATH = Path(__file__).parent / "resources"

try:
    IDF.setiddname(RESOURCES_PATH / 'Energy+.idd')
except eppy.modeleditor.IDDAlreadySetError:
    pass


def get_resources_idf():
    return IDF(RESOURCES_PATH / "resources_idf.idf")


def get_objects_name_list(idf, idf_object):
    return [obj.Name for obj in idf.idfobjects[idf_object]]


def get_objects_by_names(idf, idf_object, names):
    names_list = tl.format_input_to_list(names)
    objects_list = idf.idfobjects[idf_object]

    return [obj for obj in objects_list if obj.Name in names_list]


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
    values_list = tl.format_input_to_list(values)

    try:
        outputs = idf.idfobjects[idf_object]
    except KeyError:
        outputs = []

    var_in_idf = [out[field_name] for out in outputs]

    return tl.is_list_items_in_list(var_in_idf, values_list)


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
            idf_object_name_list = tl.format_input_to_list(idf_object_name)
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
    zones_list = tl.format_input_to_list(zones)
    variables_list = tl.format_input_to_list(variables)

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


def get_number_of_people(idf, zones="*"):
    zone_name_list = tl.format_input_to_list(zones)
    if zones == "*":
        zone_list = idf.idfobjects["Zone"]
    else:
        zone_list = [obj for obj in idf.idfobjects["Zone"]
                     if obj.Name in zone_name_list]

    people_list = idf.idfobjects["People"]
    occupation = 0
    for zone in zone_list:
        try:
            people = next(
                p for p in people_list if p.Zone_or_ZoneList_Name == zone.Name
            )
        except StopIteration:
            continue
        else:
            people_method = people.Number_of_People_Calculation_Method
            if people_method == "People/Area":
                occupation += (
                        people.People_per_Zone_Floor_Area * zone.Floor_Area)
            elif people_method == "People":
                occupation += people.Number_of_People
            elif people_method == "Area/Person":
                occupation += (
                        zone.Floor_Area / people.Zone_Floor_Area_per_Person)
    return occupation


def add_hourly_schedules_from_df(
        idf, data, schedule_type="Dimensionless",
        file_name=None, directory=None):

    if isinstance(data, pd.Series):
        data = data.to_frame()
    if not isinstance(data, pd.DataFrame):
        raise ValueError("data must be a Pandas Series on DataFrame")
    if not (data.shape[0] == 8760 or data.shape[0] == 8760 + 24):
        raise ValueError("Invalid DataFrame. Dimension 0 must be 8760 or "
                         "8760 + 24")

    eplus_ref = ["Dimensionless", "Temperature", "DeltaTemperature",
                 "PrecipitationRate", "Angle", "Convection" "Coefficient",
                 "Activity" "Level", "Velocity",  "Capacity", "Power",
                 "Availability", "Percent", "Control", "Mode"
                 ]

    schedule_type_list = tl.format_input_to_list(schedule_type)
    if not np.array(
            tl.is_list_items_in_list(schedule_type_list, eplus_ref)).all():
        raise ValueError(f"Invalid schedules type in schedules type list\n"
                         f"Valid types are {eplus_ref}")

    if len(schedule_type_list) == 1:
        schedule_type_list = schedule_type_list * len(data.columns)
    elif len(schedule_type_list) != len(data.columns):
        raise ValueError("Invalid Schedule type list. Provide a single type"
                         "or as many type as data columns")

    already_existing = is_value_in_object_fieldnames(
        idf,
        idf_object="Schedule:File",
        field_name="Name",
        values=list(data.columns)
    )

    if np.array(already_existing).any():
        raise ValueError(f"{list(data.columns[already_existing])} already "
                         f"presents in Schedules:Files")

    if file_name is None:
        file_name = str(uuid.uuid4()) + ".csv"

    if directory is None:
        directory = tempfile.mkdtemp()

    full_path = os.path.realpath(os.path.join(directory, file_name))

    data.to_csv(full_path, index=False, sep=",")

    for idx, (schedule, schedule_type) in enumerate(
            zip(data.columns, schedule_type_list)):
        idf.newidfobject(
            "Schedule:File",
            Name=schedule,
            Schedule_Type_Limits_Name=schedule_type,
            File_Name=full_path,
            Column_Number=idx + 1,
            Rows_to_Skip_at_Top=1,
            Number_of_Hours_of_Data=8760,
            Column_Separator='Comma',
            Interpolate_to_Timestep='No',
        )
