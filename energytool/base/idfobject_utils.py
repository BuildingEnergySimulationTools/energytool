import datetime

import numpy as np
from pathlib import Path

import pandas as pd

import os
import uuid
import tempfile
from energytool.tools import to_list, is_items_in_list
import eppy

from typing import Union

from eppy.modeleditor import IDF

from energytool.base.idf_utils import (
    get_objects_name_list,
    is_value_in_objects_fieldname,
)

RESOURCES_PATH = Path(__file__).parent.parent / "resources"

try:
    IDF.setiddname((RESOURCES_PATH / "Energy+.idd").as_posix())
except eppy.modeleditor.IDDAlreadySetError:
    pass


def get_zones_idealloadsairsystem(idf: IDF, zones: Union[str, list] = "*"):
    """
    Get a list of IdealLoadsAirSystem objects for specified zones in an EnergyPlus
    IDF file.

    :param idf: An EnergyPlus IDF object.
    :param zones: The zones for which to retrieve IdealLoadsAirSystem objects.
    This can be a single zone (string) or a list of zone names (list of strings).
    By default, "*" is used to retrieve IdealLoadsAirSystem objects for all zones.
    :return: A list of IdealLoadsAirSystem objects associated with the specified zones.

    The function first checks if the zones have HVAC equipment connections and then
    searches for IdealLoadsAirSystem objects associated with those zones.
    """
    if zones == "*":
        zones = get_objects_name_list(idf, "ZONE")
    else:
        zones = to_list(zones)

    ilas_list = []
    for zone in zones:
        equip_con = idf.getobject("ZONEHVAC:EQUIPMENTCONNECTIONS", zone)
        # If zone has hvac equipments
        if not equip_con:
            raise ValueError(f"{zone} doesn't have an IdealLoadAirSystem")

        equip_list = equip_con.get_referenced_object(
            "Zone_Conditioning_Equipment_List_Name"
        )
        for i in range(18):
            # 18 seem to be the max allowed (eppy)
            hvac_obj = equip_list.get_referenced_object(f"Zone_Equipment_{i + 1}_Name")
            if hvac_obj:
                if hvac_obj.key == "ZoneHVAC:IdealLoadsAirSystem":
                    ilas_list.append(hvac_obj)
    return ilas_list


def set_run_period(
    idf: IDF,
    simulation_start: Union[datetime.datetime, pd.Timestamp],
    simulation_stop: Union[datetime.datetime, pd.Timestamp],
):
    """
    Configure the IDF run period using datetime objects.

    This function allows you to set the IDF run period based on specified start and
    stop dates.

    :param idf: An EnergyPlus IDF object.
    :param simulation_start: The start date and time of the simulation as a
    datetime.datetime or pd.Timestamp object.
    :param simulation_stop: The stop date and time of the simulation as a
    datetime.datetime or pd.Timestamp object.
    :return: None

    The function configures the IDF run period with the provided start and stop dates,
    as well as other default settings for EnergyPlus simulation. Any existing run period
    configurations are cleared before adding the new run period definition.
    """

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
        Day_of_Week_for_Start_Day=simulation_start.strftime("%A"),
        Use_Weather_File_Holidays_and_Special_Days="No",
        Use_Weather_File_Daylight_Saving_Period="No",
        Apply_Weekend_Holiday_Rule="Yes",
        Use_Weather_File_Rain_Indicators="Yes",
        Use_Weather_File_Snow_Indicators="Yes",
        Treat_Weather_as_Actual="No",
    )


def set_timestep(idf, nb_timestep_per_hour: int):
    timestep_list = idf.idfobjects["Timestep"]
    timestep_list.clear()
    idf.newidfobject("Timestep", Number_of_Timesteps_per_Hour=nb_timestep_per_hour)


def output_zone_variable_present(idf: IDF, zones: str, variables):
    """
    For the idfobject OUTPUT:VARIABLE, returns True if the required zone variable is already

    :param idf:
    :param zones:
    :param variables:
    :return:
    """
    zones_bool = is_value_in_objects_fieldname(
        idf, "Output:Variable", "Key_Value", zones
    )

    all_zones_bool = is_value_in_objects_fieldname(
        idf, "Output:Variable", "Key_Value", "*"
    )

    zones_bool = np.logical_or(zones_bool, all_zones_bool)

    variables_bool = is_value_in_objects_fieldname(
        idf, "Output:Variable", "Variable_Name", variables
    )

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
    to_delete = is_value_in_objects_fieldname(
        idf, "Output:Variable", "Variable_Name", variables
    )

    if np.any(to_delete):
        indices_to_remove = [i for i, trig in enumerate(to_delete) if trig]

        for idx in sorted(indices_to_remove, reverse=True):
            del output_list[idx]


def add_output_variable(
    idf: IDF,
    key_values: Union[str, list],
    variables,
    reporting_frequency: str = "Hourly",
):
    """
    This function allows you to add output:variable object to an EnergyPlus IDF file.
    You can specify key values, variables, and reporting frequency for the output
    variables.

    :param idf: An EnergyPlus IDF object.
    :param key_values: The key values for which to add output variables.
        This can be a single key value (string) or a list of key values
        (list of strings).
    :param variables: The names of the variables to output. This can be a single
        variable name (string) or a list of variable names (list of strings).
    :param reporting_frequency: The reporting frequency for the output
        variables (e.g., "Hourly", "Daily", etc.). Default is "Hourly."
    :return: None

    The function iterates through the specified key values and variables, checking if
    corresponding output variables already exist in the IDF. If not, it adds new output
    variable definitions with the provided key values, variable names, and reporting
    frequency.

    Note: If a key value is set to "*", all existing output variables with the same
    variable name will be removed before adding the new definition.

    Example:
    ```
    idf = IDF("example.idf")
    add_output_variable(idf, "Zone1", "Zone Air Temperature")
    # Adds an output variable definition for "Zone Air Temperature" for "Zone1"
    # with default reporting frequency ("Hourly").
    ```
    """
    key_values_list = to_list(key_values)
    variables_list = to_list(variables)

    for key in key_values_list:
        for var in variables_list:
            if not np.any(output_zone_variable_present(idf, key, var)):
                if key == "*":
                    del_output_variable(idf, var)

                idf.newidfobject(
                    "OUTPUT:VARIABLE",
                    Key_Value=key,
                    Variable_Name=var,
                    Reporting_Frequency=reporting_frequency,
                )


def get_number_of_people(idf, zones="*"):
    zone_name_list = to_list(zones)
    if zones == "*":
        zone_list = idf.idfobjects["Zone"]
    else:
        zone_list = [idf.getobject("Zone", zname) for zname in zone_name_list]

    people_list = idf.idfobjects["People"]
    occupation = 0
    for zone in zone_list:
        try:
            people = next(
                p for p in people_list if p.Zone_or_ZoneList_Name == zone.Name
            )
        except StopIteration:
            continue

        people_method = people.Number_of_People_Calculation_Method
        if people_method == "People/Area":
            occupation += people.People_per_Zone_Floor_Area * zone.Floor_Area
        elif people_method == "People":
            occupation += people.Number_of_People
        elif people_method == "Area/Person":
            occupation += zone.Floor_Area / people.Zone_Floor_Area_per_Person
    return occupation


def add_hourly_schedules_from_df(
    idf: IDF,
    data: Union[pd.DataFrame, pd.Series],
    schedule_type="Dimensionless",
    file_name=None,
    directory=None,
):
    """
    Add hourly schedules from a Pandas DataFrame or Series to an EnergyPlus IDF

    This function facilitates the integration of hourly schedule data into an
    EnergyPlus IDF, which is commonly used in building energy modeling.
    The provided data should represent hourly values for various parameters like
    temperature, occupancy, or lighting.

    :param idf: An EnergyPlus IDF object, which serves as the container for
        building simulation input data.
    :param data: A Pandas DataFrame or Series containing the hourly schedule data.
        The data should align with the EnergyPlus weather data format.
    :param schedule_type: The type of schedule data being added (e.g., "Dimensionless,"
        "Temperature," "Percent"). Default is "Dimensionless."
    :param file_name: The name of the CSV file where the schedule data will be
        temporarily stored before integration. If not provided, a random name will
         be generated.
    :param directory: The directory where the temporary CSV file will be stored.
        If not provided, a system-generated temporary directory will be used.

    Raises:
    - ValueError: If the input data is not a valid Pandas DataFrame or Series,
        or if it does not have the expected shape (8760 rows).
    - ValueError: If the schedule_type provided is not one of the valid EnergyPlus
        schedule types.
    - ValueError: If the length of schedule_type_list does not match the number
        of columns in the data.
    - ValueError: If schedule names in data columns already exist in the EnergyPlus IDF.

    Notes:
    The function reads the data, organizes it to match a single year
    (e.g., replacing years with 2009), and then writes it to a CSV file.
    Subsequently, it adds schedule objects to the EnergyPlus IDF,
    linking them to the CSV file.
    The schedules are defined as hourly data spanning 8760 hours,
    which corresponds to a typical year.
    """

    if isinstance(data, pd.Series):
        data = data.to_frame()
    if not isinstance(data, pd.DataFrame):
        raise ValueError("data must be a Pandas Series or DataFrame")
    if not (data.shape[0] == 8760 or data.shape[0] == 8760 + 24):
        raise ValueError("Invalid DataFrame. Dimension 0 must be 8760 or " "8760 + 24")

    eplus_ref = [
        "Dimensionless",
        "Temperature",
        "DeltaTemperature",
        "PrecipitationRate",
        "Angle",
        "Convection" "Coefficient",
        "Activity" "Level",
        "Velocity",
        "Capacity",
        "Power",
        "Availability",
        "Percent",
        "Control",
        "Mode",
    ]

    schedule_type_list = to_list(schedule_type)
    if not np.array(
        is_items_in_list(items=schedule_type_list, target_list=eplus_ref)
    ).all():
        raise ValueError(
            f"f{schedule_type_list} is not a valid schedules type Valid types are {eplus_ref}"
        )

    if len(schedule_type_list) == 1:
        schedule_type_list = schedule_type_list * len(data.columns)
    elif len(schedule_type_list) != len(data.columns):
        raise ValueError(
            "Invalid Schedule type list. Provide a single type"
            "or as many type as data columns"
        )

    already_existing = is_value_in_objects_fieldname(
        idf, idf_object="Schedule:File", field_name="Name", values=list(data.columns)
    )

    if np.array(already_existing).any():
        raise ValueError(
            f"{list(data.columns[already_existing])} already "
            f"presents in Schedules:Files"
        )

    if file_name is None:
        file_name = str(uuid.uuid4()) + ".csv"

    if directory is None:
        directory = tempfile.mkdtemp()

    full_path = os.path.realpath(os.path.join(directory, file_name))

    # In case we have data spanning over several years. Reorganise
    data.index = [idx.replace(year=2009) for idx in data.index]
    data.sort_index(inplace=True)
    data.to_csv(full_path, index=False, sep=",")

    for idx, (schedule, schedule_type) in enumerate(
        zip(data.columns, schedule_type_list)
    ):
        idf.newidfobject(
            "Schedule:File",
            Name=schedule,
            Schedule_Type_Limits_Name=schedule_type,
            File_Name=full_path,
            Column_Number=idx + 1,
            Rows_to_Skip_at_Top=1,
            Number_of_Hours_of_Data=8760,
            Column_Separator="Comma",
            Interpolate_to_Timestep="No",
        )


def add_natural_ventilation(
    idf: IDF,
    ach: float,
    zones: Union[str, list] = "*",
    occupancy_schedule: bool = True,
    minimum_indoor_temperature: float = 22.0,
    delta_temperature: float = 0,
    kwargs: dict = {},
):
    """
    This function facilitates the addition of natural ventilation settings to specific
    zones in an EnergyPlus IDF (Input Data File).
    Natural ventilation is modeled by specifying the desired Air Changes per Hour (ACH)
    for each zone. Users can also choose whether to link the ventilation schedule
    to occupancy or use a fixed schedule.

    :param idf: An EnergyPlus IDF object.
    :param ach: The desired Air Changes per Hour (ACH) for natural ventilation.
    :param zones: The zones to which natural ventilation settings should be applied.
        Can be a single zone name or a list of zone names. Default is "*," which
        applies the settings to all zones.
    :param occupancy_schedule: If True, the ventilation schedule is linked to occupancy
        schedules in the IDF. If False, a fixed schedule "On 24/7" is used for all
        specified zones (default is True).
    :param minimum_indoor_temperature: The minimum indoor temperature
        (in degrees Celsius) at which natural ventilation is allowed (default is 22.0°C).
    :param delta_temperature: The temperature difference (in degrees Celsius) above
        the outdoor temperature at which natural ventilation is initiated
        (default is 0.0°C).
    """

    if zones == "*":
        z_list = get_objects_name_list(idf, "Zone")
    else:
        z_list = to_list(zones)

    if occupancy_schedule:
        zone_sched_dict = {}
        for ppl in idf.idfobjects["People"]:
            z_name = ppl.get_referenced_object("Zone_or_ZoneList_Name").Name
            if z_name in z_list:
                zone_sched_dict[z_name] = ppl.Number_of_People_Schedule_Name
    else:
        if not idf.getobject("Schedule:Compact", "On 24/7"):
            idf.newidfobject(
                key="Schedule:Compact",
                Name="On 24/7",
                Schedule_Type_Limits_Name="Any Number",
                Field_1="Through: 12/31",
                Field_2="For: AllDays",
                Field_3="Until: 24:00",
                Field_4=1,
            )
        zone_sched_dict = {z_name: "On 24/7" for z_name in z_list}

    for z_name in zone_sched_dict.keys():
        vnat = idf.getobject("ZoneVentilation:DesignFlowrate", f"Natvent_{z_name}")

        if vnat:
            idf.idfobjects["ZoneVentilation:DesignFlowrate"].remove(vnat)

        idf.newidfobject(
            "ZoneVentilation:DesignFlowrate",
            Name=f"Natvent_{z_name}",
            Zone_or_ZoneList_Name=z_name,
            Schedule_Name=zone_sched_dict[z_name],
            Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
            Design_Flow_Rate=ach,
            Minimum_Indoor_Temperature=minimum_indoor_temperature,
            Delta_Temperature=delta_temperature,
            **kwargs,
        )


def get_resources_idf():
    return IDF(RESOURCES_PATH / "resources_idf.idf")
