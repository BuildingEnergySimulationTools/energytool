import datetime
import os
import tempfile
import uuid

import eppy
import numpy as np
import pandas as pd
from eppy.modeleditor import IDF

from energytool.base.idf_utils import (
    get_objects_name_list,
    is_value_in_objects_fieldname,
    get_building_surface_area,
    get_building_volume,
)
from energytool.tools import to_list, is_items_in_list


def idf_to_dict(idf: IDF):
    """
    Convert an IDF object into a nested dictionary representation.

    This function takes an IDF object (from eppy library)
    and converts it into a dictionary where each key is an IDF object
    type (e.g., 'BUILDING', 'MATERIAL'), and the value is another
    dictionary mapping the object name to a dictionary of its fields
    and values.

    Parameters
    ----------
    idf : IDF
        An instance of an IDF object containing IDFObjects with
        `fieldnames` and `fieldvalues` attributes.

    Returns
    -------
    dict
        A nested dictionary where the top-level keys are IDF object
        types, the second-level keys are object names, and the values
        are dictionaries mapping field names to their corresponding
        values.

    Examples
    --------
    >>> idf_dict = idf_to_dict(my_idf)
    >>> idf_dict["MATERIAL"]["Insulation"]["Thickness"]
    '0.1'
    """
    objects_dict = {}
    for obj in idf.idfobjects:
        if idf.idfobjects[obj]:
            objects_dict[obj] = {}
            for instance in idf.idfobjects[obj]:
                objects_dict[obj].update(
                    {
                        instance.Name: {
                            name: val
                            for name, val in zip(
                                instance.fieldnames, instance.fieldvalues
                            )
                        }
                    }
                )
    return objects_dict


def add_obj_from_obj_dict(idf: IDF, obj_dict: dict, idfobject: str, name: str):
    """
    Add an IDF object to an IDF instance from a nested object dictionary.

    This function adds a new IDF object to the given IDF instance,
    using data from a nested dictionary typically created by `idf_to_dict`.
    If an object with the same name already exists, a `ValueError` is raised.

    Parameters
    ----------
    idf : IDF
        An instance of an IDF object to which the new object will be added.
    obj_dict : dict
        A nested dictionary containing IDF object data. The format should
        match the output of `idf_to_dict` function, where the top-level keys are
        IDF object types, second-level keys are object names, and values
        are field dictionaries.
    idfobject : str
        The type of the IDF object to be added (e.g., 'MATERIAL', 'ZONE').
    name : str
        The name of the object to be added. Must be present in `obj_dict`.

    Raises
    ------
    ValueError
        If an object of the specified type and name already exists in the IDF.

    Examples
    --------
    >>> add_obj_from_obj_dict(idf, obj_dict, "MATERIAL", "NewInsulation")
    """
    if name not in get_objects_name_list(idf, idfobject):
        obj = obj_dict[idfobject][name]
        idf.newidfobject(**obj)
    else:
        raise ValueError(f"{idfobject}, named {name} already exists")


def get_zones_idealloadsairsystem(idf: IDF, zones: str | list = "*"):
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
    simulation_start: datetime.datetime | pd.Timestamp,
    simulation_stop: datetime.datetime | pd.Timestamp,
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


def is_output_zone_variable(idf: IDF, zones: str, variables):
    """
    For the idfobject OUTPUT:VARIABLE, returns True if the required zone variable is
    already

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
    to_delete = is_output_zone_variable(idf, zones, variables)

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
    key_values: str | list,
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
            if not np.any(is_output_zone_variable(idf, key, var)):
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
            # Compatibility with EnergyPlus version older than 2022
            if idf.idd_version[0] >= 22:
                people = next(
                    p
                    for p in people_list
                    if p.Zone_or_ZoneList_or_Space_or_SpaceList_Name == zone.Name
                )
            else:
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
    data: pd.DataFrame | pd.Series,
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
        raise ValueError("Invalid DataFrame. Dimension 0 must be 8760 or 8760 + 24")

    eplus_ref = [
        "Dimensionless",
        "Temperature",
        "DeltaTemperature",
        "PrecipitationRate",
        "Angle",
        "ConvectionCoefficient",
        "ActivityLevel",
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
            f"f{schedule_type_list} is not a valid schedules type Valid types "
            f"are {eplus_ref}"
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

    if len(data) != 8760 and len(data) != 8784:
        print(
            "Warning: the length of your data must either be 8760 or 8784. 8760 by Default"
        )
        number_hour = 8760
    else:
        number_hour = len(data)

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
            Number_of_Hours_of_Data=number_hour,
            Column_Separator="Comma",
            Interpolate_to_Timestep="No",
        )


def add_natural_ventilation(
    idf: IDF,
    ach: float,
    zones: str | list = "*",
    occupancy_schedule: bool = True,
    minimum_indoor_temperature: float = 22.0,
    delta_temperature: float = 0,
    kwargs: dict = None,
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
        (in degrees Celsius) at which natural ventilation is allowed
        (default is 22.0°C).
    :param delta_temperature: The temperature difference (in degrees Celsius) above
        the outdoor temperature at which natural ventilation is initiated
        (default is 0.0°C).
    :param kwargs: Additional properties for "ZoneVentilation:DesignFlowrate" object
    """

    if kwargs is None:
        kwargs = {}

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


def get_n50_from_q4(q4, heated_volume, outside_surface, n=2 / 3):
    """
    Outside surface correspond to building surface in contact with outside Air
    n is flow exponent. 1 is laminar 0.5 is turbulent. Default 2/3
    """
    return q4 / ((4 / 50) ** n * heated_volume / outside_surface)


def get_ach_from_n50(n50, delta_qv, wind_exposition=0.07, f=15):
    """
    wind_exposition : ranging from 0.1 to 0.04 default 0.07
    f : can't remember why but default is 15
    delta_qv = in ach , the difference between mechanically blown and extracted
        air.
    For extraction only  delta_qv = Qv, for crossflow ventilation delta_qv = 0

    """
    return n50 * wind_exposition / (1 + f / wind_exposition * (delta_qv / n50) ** 2)


def get_building_infiltration_ach_from_q4(idf, q4pa=1.2, wind_exposition=0.07, f=15):
    building_outdoor_surface = get_building_surface_area(
        idf, outside_boundary_condition="Outdoors"
    )
    building_volume = get_building_volume(idf)

    # Compute N50 from q4pa
    n50 = get_n50_from_q4(
        q4=q4pa, heated_volume=building_volume, outside_surface=building_outdoor_surface
    )

    # Get qv
    z_ach_dict = {}
    for siz in idf.idfobjects["Sizing:Zone"]:
        zone = siz.get_referenced_object("Zone_or_ZoneList_Name")
        design = siz.get_referenced_object(
            "Design_Specification_Outdoor_Air_Object_Name"
        )
        if design.Outdoor_Air_Method != "AirChanges/Hour":
            raise ValueError(
                "Outdoor Air method other than AirChanges/Hour not yet implemented"
            )
        z_ach_dict[zone.Name] = design.Outdoor_Air_Flow_Air_Changes_per_Hour

    z_hx_dict = {}
    for connection in idf.idfobjects["ZoneHVAC:EquipmentConnections"]:
        z_name = connection.Zone_Name
        sys = connection.get_referenced_object(
            "Zone_Conditioning_Equipment_List_Name"
        ).get_referenced_object("Zone_Equipment_1_Name")
        z_hx_dict[z_name] = sys.Heat_Recovery_Type

    qv = (
        sum(
            [
                eppy.modeleditor.zonevolume(idf, zname) * z_ach_dict[zname]
                for zname in z_ach_dict.keys()
                if z_hx_dict[zname] == "None"
            ]
        )
        / building_volume
    )

    return get_ach_from_n50(n50, delta_qv=qv, wind_exposition=wind_exposition, f=f)


def get_windows_by_boundary_condition(idf, boundary_condition):
    ext_surf_name = [
        obj.Name
        for obj in idf.idfobjects["BuildingSurface:Detailed"]
        if obj.Outside_Boundary_Condition == boundary_condition
    ]

    return [
        obj
        for obj in idf.idfobjects["FenestrationSurface:Detailed"]
        if obj.Building_Surface_Name in ext_surf_name
    ]


def get_constructions_layer_list(constructions):
    construction_list = to_list(constructions)
    material_name_list = []
    for constructions in construction_list:
        material_name_list += [
            elmt
            for elmt, key in zip(constructions.fieldvalues, constructions.fieldnames)
            if key not in ["key", "Name"]
        ]
    return material_name_list


def del_layer_from_constructions(building, names):
    names_list = to_list(names)

    new_cons_list = []
    for construction in building.idf.idfobjects["Construction"]:
        keys = [k for k in construction.fieldnames]
        values = [v for v in construction.fieldvalues if v not in names_list]

        new_cons = {k: v for v, k in zip(values, keys)}

        new_cons_list.append(new_cons)

    building.idf.idfobjects["Construction"] = [
        building.idf.newidfobject(**cons) for cons in new_cons_list
    ]


def idf_object_to_dict(obj):
    return {k: v for k, v in zip(obj.fieldnames, obj.fieldvalues)}
