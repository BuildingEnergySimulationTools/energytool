from typing import Any, Union
import numpy as np

from energytool.base.idf_utils import get_objects_name_list
from energytool.base.idfobject_utils import (
    get_windows_by_boundary_condition,
    get_constructions_layer_list,
)
from energytool.building import Building
from energytool.tools import is_items_in_list


def _matches_filter(name: str, name_filter: Union[str, list, None]) -> bool:
    if name_filter is None:
        return True
    if isinstance(name_filter, list):
        return any(f in name for f in name_filter)
    return name_filter in name


def reverse_kwargs(construction_kwargs):
    construction_name = construction_kwargs["Name"]

    construction_layers = [
        value for key, value in construction_kwargs.items() if key != "Name" and value
    ]

    reversed_layers = construction_layers[::-1]

    reversed_kwargs = {"Name": construction_name, "Outside_Layer": reversed_layers[0]}
    reversed_kwargs.update(
        {f"Layer_{idx + 2}": layer for idx, layer in enumerate(reversed_layers[1:])}
    )

    return reversed_kwargs


def set_opaque_surface_construction(
    model: Building,
    description: dict[str, list[dict[str, Any]]],
    name_filter: Union[str, list[str]] = None,
    surface_type: str = "Wall",
    outside_boundary_condition: str = None,
):
    """
    This function modifies the construction of opaque building surfaces in an EnergyPlus IDF file.
    It is intended for use as a modifier for the corrai variant framework.

    :param model: energytool Building object.
    :param description: A dictionary describing the construction
    materials and properties. The argument must be of the form:
        {
            "construction_name": [
                {
                    "Name": "material_1_name",
                    "Thickness": 0.01,
                    ...
                },
                {
                    "Name": "material_2_name",
                    "Thickness": 0.5,
                    ...
                }
            ]
        }
    :param name_filter: An optional filter for surface names.
    :param surface_type: The type of surface to modify (default is 'Wall').
    :param outside_boundary_condition: The outside boundary condition (default is None).

    This function first identifies the surfaces to modify based on the provided parameters.
    It then modifies the construction of these surfaces according
    to the provided construction description.

    If a new construction is created during this process, its properties are stored in kwargs.
    These kwargs are then reversed to ensure consistency for any surfaces
    that require the inversion of their construction.
    """
    new_construction_name = list(description.keys())[0]
    new_composition = description[new_construction_name]
    surface_list = model.idf.idfobjects["BuildingSurface:Detailed"]

    if all(
        surface_type not in obj.getfieldidd("Surface_Type")["key"]
        for obj in surface_list
    ):
        raise ValueError(
            f"surface_type must be one of "
            f"{surface_list[0].getfieldidd('Surface_Type')['key']}, "
            f"got {surface_type}"
        )

    if outside_boundary_condition is not None:
        if any(
            outside_boundary_condition
            not in obj.getfieldidd("Outside_Boundary_Condition")["key"]
            for obj in surface_list
            if _matches_filter(obj.Name, name_filter)
        ):
            raise ValueError(
                f"outside_boundary_condition must be one of "
                f"{surface_list[0].getfieldidd('Outside_Boundary_Condition')['key']}, "
                f"got {outside_boundary_condition}"
            )

    for material in new_composition:
        if "Roughness" not in material.keys():
            material["Roughness"] = "Rough"

        if material["Name"] not in get_objects_name_list(model.idf, "Material"):
            model.idf.newidfobject("Material", **material)

    construction_kwargs = {
        "Name": new_construction_name,
        "Outside_Layer": new_composition[0]["Name"],
    }

    if len(new_composition) > 1:
        for idx, mat in enumerate(new_composition[1:]):
            construction_kwargs[f"Layer_{idx + 2}"] = mat["Name"]

    if new_construction_name not in get_objects_name_list(model.idf, "Construction"):
        model.idf.newidfobject("Construction", **construction_kwargs)

    surf_to_modify = [
        obj
        for obj in surface_list
        if obj.Surface_Type == surface_type
        and (
            obj.Outside_Boundary_Condition == outside_boundary_condition
            if outside_boundary_condition is not None
            else True
        )
        and _matches_filter(obj.Name, name_filter)
    ]

    for surf in surf_to_modify:
        surf.Construction_Name = new_construction_name

    construction_to_reverse = [
        obj.Construction_Name
        for obj in surface_list
        if _matches_filter(obj.Outside_Boundary_Condition_Object, name_filter)
        and (
            getattr(
                obj.Outside_Boundary_Condition_Object,
                "Outside_Boundary_Condition",
                None,
            )
            == outside_boundary_condition
            if outside_boundary_condition is not None
            else True
        )
        and obj.Surface_Type == surface_type
    ]

    reversed_kwargs = reverse_kwargs(construction_kwargs)
    for construction_name in construction_to_reverse:
        construction_object = model.idf.getobject("Construction", construction_name)
        num_layers = min(len(reversed_kwargs), len(construction_object.fieldnames) - 1)
        for idx, (_, value) in enumerate(reversed_kwargs.items()):
            if idx < num_layers:
                construction_object[construction_object.fieldnames[idx + 1]] = value
            else:
                break
        construction_object["Name"] = construction_name

        for field in construction_object.fieldnames[num_layers + 1 :]:
            if field in construction_object:
                construction_object.pop(field)


def set_external_windows(
    model: Building,
    description: dict[str, dict[str, Any]],
    name_filter: Union[str, list[str]] = None,
    surface_name_filter: Union[str, list[str]] = None,
    boundary_conditions: str = None,
):
    """
    Replace windows in an EnergyPlus building model with new window descriptions.

    This function iterates through the windows in the model, filters them based on their
    name and boundary conditions, and replaces them with new window descriptions.
    It also handles associated constructions and materials.

    Parameters:
    :param model: An EnergyPlus building model.
    :param description: A dictionary containing the new window description(s).
        The expected dictionary must be of the following form:
        {
            "Variant_1": {
                "Name": "Var_1",
                "UFactor": 1,
                "Solar_Heat_Gain_Coefficient": 0.1,
                "Visible_Transmittance": 0.1,
            },
        }
    :param name_filter: An optional filter to match window names.
    :param surface_name_filter: An optional filter to match window surface names.
    :param boundary_conditions: The boundary condition for the windows
        (default is "Outdoors").

    """
    idf = model.idf

    # Get windows materials list and shaded windows constructions
    if boundary_conditions:
        windows = get_windows_by_boundary_condition(
            idf, boundary_condition=boundary_conditions
        )
    else:
        windows = idf.idfobjects["FENESTRATIONSURFACE:DETAILED"]

    if name_filter is not None or surface_name_filter is not None:
        windows = [
            win
            for win in windows
            if _matches_filter(win.Name, name_filter)
            and _matches_filter(win.Building_Surface_Name, surface_name_filter)
        ]
    windows_names = [win.Name for win in windows]
    win_cons_names = {win.Construction_Name for win in windows}
    windows_constructions = [
        idf.getobject("Construction", name) for name in win_cons_names
    ]

    win_mat_list = get_constructions_layer_list(windows_constructions)
    windows_materials = [
        idf.getobject("WindowMaterial:SimpleGlazingSystem", name)
        for name in set(win_mat_list)
        if idf.getobject("WindowMaterial:SimpleGlazingSystem", name) is not None
    ]

    shading_controls = [
        obj
        for obj in idf.idfobjects["WindowShadingControl"]
        if any(is_items_in_list(obj.fieldvalues, windows_names))
    ]

    obj_list = [
        obj.get_referenced_object("Construction_with_Shading_Name")
        for obj in shading_controls
    ]
    set_name = {obj.Name for obj in obj_list}

    shaded_window_constructions = [
        idf.getobject("Construction", name) for name in set_name
    ]

    # Replace windows
    new_window_name = list(description.keys())[0]
    new_window = description[new_window_name]

    name_to_replace = [obj.Name for obj in windows_materials]
    constructions_list = windows_constructions + shaded_window_constructions
    for construction in constructions_list:
        for field in construction.fieldnames:
            if construction[field] in name_to_replace:
                construction[field] = new_window["Name"]

    # Add the new window material to the IDF
    if new_window["Name"] not in [
        win.Name for win in idf.idfobjects["WindowMaterial:SimpleGlazingSystem"]
    ]:
        idf.newidfobject(key="WindowMaterial:SimpleGlazingSystem", **new_window)

    used_mat_list = [
        val for cons in idf.idfobjects["CONSTRUCTION"] for val in cons.fieldvalues[2:]
    ]

    idf.idfobjects["WindowMaterial:SimpleGlazingSystem"] = [
        win
        for win in idf.idfobjects["WindowMaterial:SimpleGlazingSystem"]
        if win.Name in used_mat_list
    ]


def set_afn_surface_opening_factor(
    model: Building,
    description: dict[str, dict[str, Any]],
    name_filter: Union[str, list[str]] = None,
    surface_name_filter: Union[str, list[str]] = None,
):
    """
    Modify AirFlowNetwork:Multizone:Surface WindowDoor_Opening_Factor_or_Crack_Factor
    based on their name.

    :param model: An EnergyPlus building model.
    :param description: A dictionary containing the new value.
        the expected dictionary must be of the following form:
        {
            "Variant_1": {
                "WindowDoor_Opening_Factor_or_Crack_Factor": 0.3,
            },
        }
    :param name_filter: An optional filter to match window names.
    :param surface_name_filter: An optional filter to match window surface names.
    """
    idf = model.idf

    openings = idf.idfobjects["AirflowNetwork:MultiZone:Surface"]

    if name_filter is not None or surface_name_filter is not None:
        openings = [
            op
            for op in openings
            if _matches_filter(op.Surface_Name, name_filter)
            and _matches_filter(op.Surface_Name, surface_name_filter)
        ]

    new_opening_ratio_name = list(description.keys())[0]
    new_opening_ratio = description[new_opening_ratio_name][
        "WindowDoor_Opening_Factor_or_Crack_Factor"
    ]

    for opening in openings:
        opening["WindowDoor_Opening_Factor_or_Crack_Factor"] = new_opening_ratio




def set_blinds_solar_transmittance(
    model: Building,
    description: dict[str, dict[str, Any]],
    name_filter: Union[str, list[str]] = None,
    surface_name_filter: Union[str, list[str]] = None,
):
    """
    Modify WindowMaterial:Shade Solar_Transmittance (or/and Reflectance) based
    on the given description.

    :param model: An EnergyPlus building model.
    :param description: A dictionary containing the new values for shades.
        The expected dictionary must be of the following form:
        {
            "Variant_1": [
                {
                    "Solar_Transmittance": 0.66,
                    "Solar_Reflectance": 0.20
                }
            ]
        }
    :param name_filter: An optional filter to match window names.
    :param surface_name_filter: An optional filter to match window surface names.
    """
    idf = model.idf

    shades = idf.idfobjects["WindowMaterial:Shade"]
    all_constructions = idf.idfobjects["Construction"]
    scenarios = idf.idfobjects["WindowShadingControl"]

    new_shaded_window_name = list(description.keys())[0]

    selected_shades = []

    filtered_windows = [
        window
        for window in idf.idfobjects["FenestrationSurface:Detailed"]
        if _matches_filter(window.Name, name_filter)
        and _matches_filter(window.Building_Surface_Name, surface_name_filter)
    ]
    construction_names_dict = {
        window.Name: window.Construction_Name for window in filtered_windows
    }

    # Check if construction_name of filtered window includes a shade or a shaded version
    for window_name, target_name in construction_names_dict.items():
        for construction in all_constructions:
            if (
                construction.Name == target_name
                or construction.Name == target_name + "_Shaded"
            ):
                construction_values = [
                    construction[field] for field in construction.fieldnames[2:]
                ]
                for shade in shades:
                    if any(
                        construction_value == shade.Name
                        for construction_value in construction_values
                        if construction_value
                    ):
                        selected_shades.append(shade)

        # Also, check "WINDOWSHADINGCONTROL" construction associated to filtered windows
        for scen in scenarios:
            for n in range(1, 10):
                if scen[f"Fenestration_Surface_{n}_Name"] == window_name:
                    construction_name = scen.Construction_with_Shading_Name
                    for construction in all_constructions:
                        if construction.Name == construction_name:
                            construction_values = [
                                construction[field]
                                for field in construction.fieldnames[2:]
                            ]
                            for shade in shades:
                                if any(
                                    construction_value == shade.Name
                                    for construction_value in construction_values
                                    if construction_value
                                ):
                                    selected_shades.append(shade)

    new_transmittance = description[new_shaded_window_name][0].get(
        "Solar_Transmittance"
    )
    new_reflectance = description[new_shaded_window_name][0].get("Solar_Reflectance")

    for shade in selected_shades:
        if new_transmittance is not None:
            shade["Solar_Transmittance"] = new_transmittance
        if new_reflectance is not None:
            shade["Solar_Reflectance"] = new_reflectance


def set_schedule_constant(
    model: Building,
    description: dict[str, dict[str, Any]],
):
    idf = model.idf

    schedule_constant = idf.idfobjects["SCHEDULE:CONSTANT"]

    for schedule_name, schedule_fields in description.items():
        schedule_exists = False

        for sched in schedule_constant:
            if sched["Name"] == schedule_fields["Name"]:
                sched["Hourly_Value"] = schedule_fields["Hourly_Value"]
                schedule_exists = True
                break  # Exit loop once found and modified

        if not schedule_exists:
            new_schedule = {
                "Name": schedule_fields["Name"],
                "Schedule_Type_Limits_Name": schedule_fields[
                    "Schedule_Type_Limits_Name"
                ],
                "Hourly_Value": schedule_fields["Hourly_Value"],
            }
            model.idf.newidfobject("SCHEDULE:CONSTANT", **new_schedule)


def set_blinds_schedule(
    model: Building,
    description: dict[str, dict[str, Any]],
    name_filter: Union[str, list[str]] = None,
    surface_name_filter: Union[str, list[str]] = None,
):
    """
    Create/update Schedule based on the given description.

    :param model: An EnergyPlus building model.
    :param description: A dictionary containing the new values for schedule.
        The expected dictionary must be of the following form:
        {
            "Variant_1": [
                {
                    "Scenario": {
                        "Name": 'Shading_control',
                        "Schedule_Type_Limits_Name": 'Fractional1',
                        "Field1": "Through: 01 April",
                        # ... other fields ...
                    },
                    "Limits": {
                        "Name": 'Fractional1',
                        "Lower_Limit_Value": 0,
                        "Upper_Limit_Value": 1,
                        "Numeric_Type": "Continuous"
                    }
                }
            ]
        }
    :param name_filter: An optional filter to match window names.
    :param surface_name_filter: An optional filter to match window surface names.
    """
    idf = model.idf

    scenarios = idf.idfobjects["WindowShadingControl"]
    new_shaded_window_name = list(description.keys())[0]
    new_schedule = description[new_shaded_window_name][0]["Scenario"]

    schedule = idf.idfobjects["Schedule:Year"]
    compact = idf.idfobjects["Schedule:Compact"]
    existing_shading_control = [entry["Name"] for entry in schedule] + [
        entry["Name"] for entry in compact
    ]

    name_in_existing = any(
        new_schedule["Name"] in entry for entry in existing_shading_control
    )

    if not name_in_existing and "Field_1" not in new_schedule:
        raise ValueError(
            "Scenario's name not found in IDF. "
            "Use existing name or define Schedule "
            "fields in description"
        )

    if name_filter or surface_name_filter:
        filtered_windows = [
            window
            for window in idf.idfobjects["FenestrationSurface:Detailed"]
            if _matches_filter(window.Name, name_filter)
            and _matches_filter(window.Building_Surface_Name, surface_name_filter)
        ]
        construction_names_dict = {
            window.Name: window.Construction_Name for window in filtered_windows
        }
    else:
        construction_names_dict = {
            window.Name: window.Construction_Name
            for window in idf.idfobjects["FenestrationSurface:Detailed"]
        }

    for wind_name, _ in construction_names_dict.items():
        for scen in scenarios:
            for n in range(1, 10):
                # check if construction_Name matches construction names of windows +
                # check if window is assigned to Fenestration_Surface_1 to _10
                # of "WINDOWSHADINGCONTROL"
                if scen[f"Fenestration_Surface_{n}_Name"] == wind_name:
                    scen["Schedule_Name"] = new_schedule["Name"]

    required_fields = ["Name", "Schedule_Type_Limits_Name"]

    if any(field not in required_fields for field in new_schedule):
        # More than Name or Schedule_Type_Limits_Name is given in Description
        schedule_kwargs = {
            "Name": new_schedule["Name"],
            "Schedule_Type_Limits_Name": (
                new_schedule["Schedule_Type_Limits_Name"]
                if "Schedule_Type_Limits_Name" in new_schedule
                else "Fractional"
            ),
        }

        for idx, info in enumerate(new_schedule.values()):
            if "Schedule_Type_Limits_Name" in new_schedule.keys():
                if idx >= 2:
                    schedule_kwargs[f"Field_{idx - 1}"] = info
            else:
                if idx >= 1:
                    schedule_kwargs[f"Field_{idx}"] = info

        existing_st_limits = [
            entry["Name"] for entry in idf.idfobjects["ScheduleTypeLimits"]
        ]
        if (
            "Limits" not in description[new_shaded_window_name][0]
            and schedule_kwargs["Schedule_Type_Limits_Name"] not in existing_st_limits
        ):
            raise ValueError(
                "ScheduleTypeLimit is not specified in IDF. Define "
                "ScheduleTypeLimit fields in Description"
            )

        model.idf.newidfobject(
            "Schedule:Compact", **schedule_kwargs
        )  # new or replaced ?

        st_limit = schedule_kwargs["Schedule_Type_Limits_Name"]
        existing_st_limits = [
            entry["Name"] for entry in idf.idfobjects["ScheduleTypeLimits"]
        ]

        if st_limit not in existing_st_limits and (
            limits := description.get(new_shaded_window_name, [{}])[0].get("Limits")
        ):
            limits_kwargs = {
                "Name": new_schedule["Schedule_Type_Limits_Name"],
                "Lower_Limit_Value": limits["Lower_Limit_Value"],
                "Upper_Limit_Value": limits["Upper_Limit_Value"],
                "Numeric_Type": limits["Numeric_Type"],
            }
            model.idf.newidfobject("ScheduleTypeLimits", **limits_kwargs)


def update_idf_objects(
    model: Building,
    description: dict[str, dict[str, Any]],
    idfobject_type: str,
    name_filter: Union[str, list[str]] = None,
):
    """
    Updates or creates objects in an IDF based on the provided description.

    This function updates the fields of existing objects in an IDF or creates new objects
    if no matching objects are found. A partial name filter can be used to update only
    the objects whose names contain the specified filter.

    Parameters:
    model (Building): The building model containing the IDF.
    description (dict[str, dict[str, Any]]): A dictionary describing the objects to be updated or created.
        Example:
            description = {
                "Schedule1": {
                    "Name": "Schedule_test1",
                    "Schedule_Type_Limits_Name": "Fractional",
                    "Hourly_Value": 0.77,
                },
            }
    idfobject_type (str): The type of IDF object to be updated or created.
    name_filter (str, optional): A partial name filter to match objects for updating. Defaults to None.

    """
    idf = model.idf
    idf_objects = idf.idfobjects[idfobject_type]

    for obj_name, obj_fields in description.items():
        obj_name_filter = obj_fields.get("Name")
        obj_exists = False

        for obj in idf_objects:
            if name_filter is not None and _matches_filter(obj["Name"], name_filter):
                for field, value in obj_fields.items():
                    if field != "Name":
                        obj[field] = value
                obj_exists = True
            elif name_filter is None and obj["Name"] == obj_name_filter:
                for field, value in obj_fields.items():
                    if field != "Name":
                        obj[field] = value
                obj_exists = True

        if not obj_exists and name_filter is None:
            new_obj_kwargs = {field: value for field, value in obj_fields.items()}
            model.idf.newidfobject(idfobject_type, **new_obj_kwargs)


def set_blinds_st_and_schedule(
    model: Building,
    description: dict[str, dict[str, Any]],
    name_filter: Union[str, list[str]] = None,
    surface_name_filter: Union[str, list[str]] = None,
):
    """
    Modify WindowMaterial:Shade Solar_Transmittance and create/update
    Schedule based on the given description.

    :param model: An EnergyPlus building model.
    :param description: A dictionary containing the new values for shades and schedule.
        The expected dictionary must be of the following form:
        {
            "Variant_1": [
                {
                    "Solar_Transmittance": 0.66,
                    "Scenario": {
                        "Name": 'Shading_control',
                        "Schedule_Type_Limits_Name": 'Fractional1',
                        "Field1": "Through: 01 April",
                        "Field2": "For: AllDays",
                        "Field4": "Until: 24:00",
                        "Field3": 0.0,
                        "Field5": "Through: 30 September",
                        "Field6": "For: Weekdays",
                        "Field7": "Until: 24:00",
                        "Field8": 1.0,
                        "Field9": "For: Weekends",
                        "Field10": "Until: 24:00",
                        "Field11": 0.0,
                        "Field12": "For: AllOtherDays",
                        "Field13": "Until: 24:00",
                        "Field14": 0.0,
                    },
                    "Limits": {
                        "Name": 'Fractional1',
                        "Lower_Limit_Value": 0,
                        "Upper_Limit_Value": 1,
                        "Numeric_Type": "Continuous"
                    }
                }
            ]
        }
    :param name_filter: An optional filter to match window names.
    :param surface_name_filter: An optional filter to match window surface names.
    """
    set_blinds_solar_transmittance(model, description, name_filter, surface_name_filter)
    set_blinds_schedule(model, description, name_filter, surface_name_filter)


def set_system(model, description, **kwargs):
    system = list(description.values())[0]
    system_name = kwargs.get("system_name", system.name)

    # Remove existing system with the same name if needed
    model.del_system(system_name)

    # Add new system
    model.add_system(system)


def set_ahu_night_ventilation(
    model: Building,
    description: dict[str, dict[str, Any]],
    name_filter: Union[str, list[str]] = None,
):
    """
    Modify DesignSpecification:OutdoorAir objects to represent a
    night ventilation strategy.

    This modifier updates all DesignSpecification:OutdoorAir objects
    in the model and forces the outdoor air method to be specified
    as air changes per hour (ACH).

    Parameters
    ----------
    model : Building
        EnergyTool Building object.

    description : dict[str, dict[str, Any]]
        Dictionary describing the night ventilation strategy.

        The expected dictionary must be of the following form:

        {
            "NightVentilation": {
                "Outdoor_Air_Flow_Air_Changes_per_Hour": 4.0,
                "Outdoor_Air_Schedule_Name": "NIGHT_VENTILATION",
            }
        }

    name_filter : str, optional
        Partial name filter used to select
        DesignSpecification:OutdoorAir objects.

        If provided, only objects whose Name
        contains the specified string will be
        modified.

        If None, all DesignSpecaouaification:OutdoorAir
        objects are modified.

        Optionally, a Schedule:Compact description can be provided
        using the "Scenario" key. If present, the schedule will be
        created or updated before being assigned to the outdoor air
        specification.

        Example:

        {
            "NightVentilation": {
                "Outdoor_Air_Flow_Air_Changes_per_Hour": 4.0,
                "Outdoor_Air_Schedule_Name": "NIGHT_VENTILATION",
                "Scenario": {
                    "Name": "NIGHT_VENTILATION",
                    "Schedule_Type_Limits_Name": "Fraction",
                    "Field_1": "Through: 12/31",
                    "Field_2": "For: AllDays",
                    "Field_3": "Until: 07:00",
                    "Field_4": 1,
                    "Field_5": "Until: 22:00",
                    "Field_6": 0.2,
                    "Field_7": "Until: 24:00",
                    "Field_8": 1,
                }
            }
        }

    Notes
    -----
    The modifier updates all DesignSpecification:OutdoorAir objects
    found in the model.

    The following fields are modified:

    - Outdoor_Air_Method
    - Outdoor_Air_Flow_Air_Changes_per_Hour
    - Outdoor_Air_Schedule_Name

    Outdoor_Air_Method is automatically set to:

        "AirChanges/Hour"

    This modifier is intended to represent free cooling or night
    ventilation strategies through scheduled outdoor air supply.
    """

    params = list(description.values())[0]

    if "Scenario" in params:
        schedule = params["Scenario"]

        update_idf_objects(
            model,
            {schedule["Name"]: schedule},
            "Schedule:Compact",
        )

    for obj in model.idf.idfobjects["DESIGNSPECIFICATION:OUTDOORAIR"]:

        if not _matches_filter(obj.Name, name_filter):
            continue

        obj.Outdoor_Air_Method = "AirChanges/Hour"

        if "Outdoor_Air_Flow_Air_Changes_per_Hour" in params:
            obj.Outdoor_Air_Flow_Air_Changes_per_Hour = (
                params["Outdoor_Air_Flow_Air_Changes_per_Hour"]
            )

        if "Outdoor_Air_Schedule_Name" in params:
            obj.Outdoor_Air_Schedule_Name = (
                params["Outdoor_Air_Schedule_Name"]
            )


def set_shading_geometry(
        model: Building,
        shading_type: str,
        description: dict = None,
        name_filter: Union[str, list[str]] = None,
):
    """
    Create or replace shading geometry attached to fenestration surfaces (windows).

    Existing shading objects of the same type are removed before new ones are created.

    Supported shading types and their default parameters
    ----------------------------------------------------
    ``"overhang"``
        Horizontal projection above the window.

        - ``Depth`` (m, default 0.5): how far the overhang extends from the wall.
        - ``Offset`` (m, default 0.0): vertical offset above the top edge of the window.

    ``"sidefins"``
        Vertical fins on the sides of the window.

        - ``Depth`` (m, default 0.5): how far each fin extends from the wall.
        - ``Left`` (bool, default True): add a fin on the left side.
        - ``Right`` (bool, default True): add a fin on the right side.

    ``"horizontal_louvers"``
        Horizontal slats distributed over the window height.

        - ``Depth`` (m, default 0.5): depth of each louver.
        - ``Spacing`` (m, default 0.25): vertical distance between louvers.
        - ``Tilt`` (°, default 0): tilt of the louvers (0 = horizontal plane).
        - ``Offset`` (m, default 0): horizontal gap between the louver and the wall.

    ``"vertical_louvers"``
        Vertical slats distributed over the window width.

        - ``Depth`` (m, default 0.5): depth of each louver.
        - ``Spacing`` (m, default 0.30): horizontal distance between louvers.
        - ``Tilt`` (°, default 0): tilt of the louvers (0 = perpendicular to wall).

    Parameters
    ----------
    model : Building
        EnergyTool Building object.
    shading_type : str
        Type of shading geometry to create.  Must be one of
        ``"overhang"``, ``"sidefins"``, ``"horizontal_louvers"``,
        ``"vertical_louvers"``.
    description : dict, optional
        Parameter overrides for the chosen shading type.
        Only keys that exist in the default parameters are meaningful.
        Example for an overhang::

            {"Depth": 1.2, "Offset": 0.1}

    name_filter : str or list[str], optional
        If provided, only windows whose name contains the filter string
        (or any string in the list) are processed.
        If None, all windows are processed.
    """
    default_parameters = {
        "overhang": {
            "Depth": 0.5,
            "Offset": 0.0,
        },
        "sidefins": {
            "Depth": 0.5,
            "Left": True,
            "Right": True,
        },
        "horizontal_louvers": {
            "Depth": 0.5,
            "Spacing": 0.25,
            "Tilt": 0,
            "Offset": 0,
        },
        "vertical_louvers": {
            "Depth": 0.5,
            "Spacing": 0.30,
            "Tilt": 0,
        },
    }

    if shading_type not in default_parameters:
        raise ValueError(
            f"shading_type must be one of "
            f"{list(default_parameters.keys())}"
        )

    params = default_parameters[shading_type].copy()

    if description is not None:
        params.update(description)

    windows = [
        window
        for window in model.idf.idfobjects["FenestrationSurface:Detailed"]
        if (not window.Surface_Type or window.Surface_Type.upper() == "WINDOW")
           and _matches_filter(window.Name, name_filter)
    ]

    def get_top_edge(vertices):
        top_vertices = sorted(
            vertices,
            key=lambda p: p[2],
            reverse=True,
        )[:2]

        edge = top_vertices[1] - top_vertices[0]

        if abs(edge[0]) >= abs(edge[1]):
            top_vertices = sorted(
                top_vertices,
                key=lambda p: p[0],
            )
        else:
            top_vertices = sorted(
                top_vertices,
                key=lambda p: p[1],
            )

        return top_vertices

    def get_bottom_edge(vertices):
        bottom_vertices = sorted(
            vertices,
            key=lambda p: p[2],
        )[:2]

        edge = bottom_vertices[1] - bottom_vertices[0]

        if abs(edge[0]) >= abs(edge[1]):
            bottom_vertices = sorted(
                bottom_vertices,
                key=lambda p: p[0],
            )
        else:
            bottom_vertices = sorted(
                bottom_vertices,
                key=lambda p: p[1],
            )

        return bottom_vertices

    def get_vertices(window):
        return [
            np.array(
                [
                    float(getattr(window, f"Vertex_{i}_Xcoordinate") or 0),
                    float(getattr(window, f"Vertex_{i}_Ycoordinate") or 0),
                    float(getattr(window, f"Vertex_{i}_Zcoordinate") or 0),
                ]
            )
            for i in range(1, 5)
        ]

    def get_outward_normal(vertices):
        p1, p2 = vertices[:2]
        horizontal = p2 - p1
        normal = np.cross(horizontal, np.array([0.0, 0.0, 1.0]))
        norm = np.linalg.norm(normal)
        if norm < 1e-10:
            return np.array([1.0, 0.0, 0.0])
        return normal / norm

    def delete_existing_shading(window_name):
        objects = model.idf.idfobjects["Shading:Zone:Detailed"]
        for obj in list(objects):
            if obj.Name.startswith(f"{window_name}_{shading_type}"):
                model.idf.removeidfobject(obj)

    def create_shading_surface(
            name,
            vertices,
            base_surface_name,
    ):
        kwargs = {
            "Name": name,
            'Base_Surface_Name': base_surface_name,
            "Number_of_Vertices": 4,
        }
        for i, vertex in enumerate(vertices, start=1):
            kwargs[f"Vertex_{i}_Xcoordinate"] = float(vertex[0])
            kwargs[f"Vertex_{i}_Ycoordinate"] = float(vertex[1])
            kwargs[f"Vertex_{i}_Zcoordinate"] = float(vertex[2])
        model.idf.newidfobject(
            "Shading:Zone:Detailed",
            **kwargs,
        )

    for window in windows:
        delete_existing_shading(window.Name)
        vertices = get_vertices(window)
        p1, p2, p3, p4 = vertices

        normal = get_outward_normal(vertices)
        depth = params["Depth"]

        top_1, top_2 = get_top_edge(vertices)
        bottom_1, bottom_2 = get_bottom_edge(vertices)

        height = (
                max(v[2] for v in vertices)
                - min(v[2] for v in vertices)
        )

        width = np.linalg.norm(
            top_2 - top_1
        )

        if shading_type == "overhang":
            offset = params["Offset"]

            top_vertices = sorted(
                vertices,
                key=lambda p: p[2],
                reverse=True,
            )[:2]

            edge = top_vertices[1] - top_vertices[0]

            if np.linalg.norm(edge) > 1e-10:
                edge = edge / np.linalg.norm(edge)

            if abs(edge[0]) >= abs(edge[1]):
                top_vertices = sorted(top_vertices, key=lambda p: p[0])
            else:
                top_vertices = sorted(top_vertices, key=lambda p: p[1])

            top_1, top_2 = top_vertices

            top_1 = top_1 + np.array([0.0, 0.0, offset])
            top_2 = top_2 + np.array([0.0, 0.0, offset])

            q1 = top_1 + depth * normal
            q2 = top_2 + depth * normal

            create_shading_surface(
                f"{window.Name}_overhang",
                [
                    top_1,
                    top_2,
                    q2,
                    q1,
                ],
                window.Building_Surface_Name,
            )

        elif shading_type == "sidefins":

            if params["Left"]:
                q1 = p1 + depth * normal
                q4 = p4 + depth * normal

                create_shading_surface(
                    f"{window.Name}_left_fin",
                    [
                        p1,
                        q1,
                        q4,
                        p4,
                    ],
                    window.Building_Surface_Name,
                )

            if params["Right"]:
                q2 = p2 + depth * normal
                q3 = p3 + depth * normal

                create_shading_surface(
                    f"{window.Name}_right_fin",
                    [
                        p2,
                        p3,
                        q3,
                        q2,
                    ],
                    window.Building_Surface_Name,
                )

        elif shading_type == "horizontal_louvers":

            spacing = params["Spacing"]
            offset = params["Offset"]
            tilt = np.deg2rad(params["Tilt"])

            vertical = np.array([0.0, 0.0, 1.0])

            louver_direction = (
                    np.cos(tilt) * normal
                    - np.sin(tilt) * vertical
            )

            z_positions = np.arange(
                0,
                height + 1e-6,
                spacing,
            )

            for i, z_offset in enumerate(z_positions):
                p1_louver = (
                        top_1
                        - np.array([0, 0, z_offset])
                        + offset * normal
                )

                p2_louver = (
                        top_2
                        - np.array([0, 0, z_offset])
                        + offset * normal
                )

                q1 = (
                        p1_louver
                        + depth * louver_direction
                )

                q2 = (
                        p2_louver
                        + depth * louver_direction
                )

                create_shading_surface(
                    f"{window.Name}_horizontal_louver_{i}",
                    [
                        p1_louver,
                        p2_louver,
                        q2,
                        q1,
                    ],
                    window.Building_Surface_Name,
                )

        elif shading_type == "vertical_louvers":

            spacing = params["Spacing"]
            tilt = np.deg2rad(params["Tilt"])

            edge_vector = top_2 - top_1
            edge_vector /= np.linalg.norm(edge_vector)

            horizontal_normal = normal.copy()
            horizontal_normal[2] = 0.0
            horizontal_normal /= np.linalg.norm(horizontal_normal)

            vertical = np.array(
                [0.0, 0.0, 1.0]
            )

            local_right = np.cross(
                vertical,
                horizontal_normal,
            )
            local_right /= np.linalg.norm(local_right)

            louver_direction = (
                    np.cos(tilt) * horizontal_normal
                    + np.sin(tilt) * local_right
            )

            n_louvers = int(
                np.floor(width / spacing)
            )

            occupied_width = (
                    n_louvers * spacing
            )

            margin = (
                             width - occupied_width
                     ) / 2

            x_positions = np.arange(
                margin,
                width - margin + 1e-6,
                spacing,
            )

            for i, x_offset in enumerate(x_positions):
                offset_vector = (
                        x_offset
                        * edge_vector
                )

                p_bottom = (
                        bottom_1
                        + offset_vector
                )

                p_top = (
                        top_1
                        + offset_vector
                )

                q_bottom = (
                        p_bottom
                        + depth * louver_direction
                )

                q_top = (
                        p_top
                        + depth * louver_direction
                )

                create_shading_surface(
                    f"{window.Name}_vertical_louver_{i}",
                    [
                        p_bottom,
                        q_bottom,
                        q_top,
                        p_top,
                    ],
                    window.Building_Surface_Name,
                )


def set_shading_properties(
    model: Building,
    description: dict = None,
    name_filter: Union[str, list[str]] = None,
):
    """
    Assign reflectance and transmittance properties to shading surfaces.

    For each ``Shading:Zone:Detailed`` and ``Shading:Building:Detailed`` surface,
    a ``ShadingProperty:Reflectance`` object is created or updated.
    A transmittance schedule can also be attached.

    Default values (applied when ``description`` is None or a key is absent)
    -------------------------------------------------------------------------
    - ``Diffuse_Solar_Reflectance_of_Unglazed_Part_of_Shading_Surface``: 0.2
    - ``Diffuse_Visible_Reflectance_of_Unglazed_Part_of_Shading_Surface``: 0.2
    - ``Fraction_of_Shading_Surface_That_Is_Glazed``: 0.0
    - ``Glazing_Construction_Name``: "" (none)

    Parameters
    ----------
    model : Building
        EnergyTool Building object.
    description : dict, optional
        Property overrides.  Accepted special keys:

        - ``"Transmittance"`` (float): constant transmittance value.
          A ``Schedule:Constant`` is automatically created and assigned
          to ``Transmittance_Schedule_Name`` for each surface.
        - ``"Transmittance_Schedule"`` (str): name of an existing EnergyPlus
          schedule to use directly.  Takes precedence over ``"Transmittance"``.

        Any other key must be a valid ``ShadingProperty:Reflectance`` field name,
        e.g. ``"Diffuse_Solar_Reflectance_of_Unglazed_Part_of_Shading_Surface"``.

    name_filter : str or list[str], optional
        If provided, only shading surfaces whose name contains the filter string
        (or any string in the list) are affected.  If None, all surfaces are updated.
    """
    DEFAULT_SHADING_PROPERTIES = {
        "Diffuse_Solar_Reflectance_of_Unglazed_Part_of_Shading_Surface": 0.2,
        "Diffuse_Visible_Reflectance_of_Unglazed_Part_of_Shading_Surface": 0.2,
        "Fraction_of_Shading_Surface_That_Is_Glazed": 0.0,
        "Glazing_Construction_Name": "",
    }

    params = DEFAULT_SHADING_PROPERTIES.copy()

    transmittance = None
    schedule = None

    if description is not None:
        transmittance = description.get(
            "Transmittance"
        )

        schedule = description.get(
            "Transmittance_Schedule"
        )

        for key, value in description.items():
            if key not in ("Transmittance", "Transmittance_Schedule"):
                params[key] = value

    existing = {
        obj.Shading_Surface_Name: obj
        for obj in model.idf.idfobjects[
            "SHADINGPROPERTY:REFLECTANCE"
        ]
    }

    shading_objects = [
        obj
        for obj in (
            list(model.idf.idfobjects["SHADING:ZONE:DETAILED"])
            + list(model.idf.idfobjects["SHADING:BUILDING:DETAILED"])
        )
        if _matches_filter(obj.Name, name_filter)
    ]

    for shading in shading_objects:
        if schedule is not None:

            shading.Transmittance_Schedule_Name = (
                schedule
            )

        elif transmittance is not None:

            schedule_name = (
                f"{shading.Name}_transmittance"
            )

            update_idf_objects(
                model,
                {
                    schedule_name: {
                        "Name": schedule_name,
                        "Schedule_Type_Limits_Name": "Fraction",
                        "Hourly_Value": transmittance,
                    }
                },
                "Schedule:Constant",
            )

            shading.Transmittance_Schedule_Name = (
                schedule_name
            )

        if shading.Name in existing:
            refl_obj = existing[shading.Name]

        else:
            refl_obj = model.idf.newidfobject(
                "SHADINGPROPERTY:REFLECTANCE",
                Shading_Surface_Name=shading.Name,
            )

        for field, value in params.items():
            setattr(refl_obj, field, value)

def set_shading_object(
        model: Building,
        geometry: dict = None,
        properties: dict = None,
        name_filter: Union[str, list[str]] = None,
):
    """
    Create shading geometry and/or assign shading properties in a single call.

    Convenience wrapper around :func:`set_shading_geometry` and
    :func:`set_shading_properties`.

    Property presets (use ``properties={"Preset": "<name>", ...}``)
    ---------------------------------------------------------------
    +--------------------+----------------------------+-----------------------------+
    | Preset             | Solar reflectance          | Visible reflectance         |
    +====================+============================+=============================+
    | ``vegetation``     | 0.25                       | 0.15                        |
    +--------------------+----------------------------+-----------------------------+
    | ``light_concrete`` | 0.60                       | 0.60                        |
    +--------------------+----------------------------+-----------------------------+
    | ``dark_metal``     | 0.15                       | 0.15                        |
    +--------------------+----------------------------+-----------------------------+
    | ``pv_panel``       | 0.05                       | 0.05                        |
    +--------------------+----------------------------+-----------------------------+

    Preset values are used as defaults and can be overridden by other keys in
    ``properties``.

    Parameters
    ----------
    model : Building
        EnergyTool Building object.
    geometry : dict, optional
        Geometry configuration.  Must contain a ``"Type"`` key set to one of
        ``"overhang"``, ``"sidefins"``, ``"horizontal_louvers"``, or
        ``"vertical_louvers"``.  All other keys are forwarded as parameter
        overrides to :func:`set_shading_geometry`.  Example::

            {"Type": "overhang", "Depth": 1.0, "Offset": 0.05}

    properties : dict, optional
        Properties configuration.  May include:

        - ``"Preset"`` (str): one of the preset names listed above.
        - ``"Transmittance"`` (float): constant transmittance (0–1).
        - ``"Transmittance_Schedule"`` (str): name of an existing schedule.
        - Any ``ShadingProperty:Reflectance`` EnergyPlus field.

        Example::

            {"Preset": "light_concrete", "Transmittance": 0.0}

    name_filter : str or list[str], optional
        Forwarded to both :func:`set_shading_geometry` and
        :func:`set_shading_properties`.
    """
    SHADING_PROPERTY_PRESETS = {
        "vegetation": {
            "Diffuse_Solar_Reflectance_of_Unglazed_Part_of_Shading_Surface": 0.25,
            "Diffuse_Visible_Reflectance_of_Unglazed_Part_of_Shading_Surface": 0.15,
        },
        "light_concrete": {
            "Diffuse_Solar_Reflectance_of_Unglazed_Part_of_Shading_Surface": 0.60,
            "Diffuse_Visible_Reflectance_of_Unglazed_Part_of_Shading_Surface": 0.60,
        },
        "dark_metal": {
            "Diffuse_Solar_Reflectance_of_Unglazed_Part_of_Shading_Surface": 0.15,
            "Diffuse_Visible_Reflectance_of_Unglazed_Part_of_Shading_Surface": 0.15,
        },
        "pv_panel": {
            "Diffuse_Solar_Reflectance_of_Unglazed_Part_of_Shading_Surface": 0.05,
            "Diffuse_Visible_Reflectance_of_Unglazed_Part_of_Shading_Surface": 0.05,
        },
    }

    if geometry is not None:
        shading_type = geometry.pop("Type")

        set_shading_geometry(
            model=model,
            shading_type=shading_type,
            description=geometry,
            name_filter=name_filter,
        )

    if properties is not None:

        properties = properties.copy()

        preset = properties.pop("Preset", None)

        if preset is not None:
            preset_values = SHADING_PROPERTY_PRESETS[
                preset
            ].copy()

            preset_values.update(properties)

            properties = preset_values

        set_shading_properties(
            model=model,
            description=properties,
            name_filter=name_filter,
        )

def set_shade(
    model: Building,
    description: dict = None,
    name_filter: Union[str, list[str]] = None,
):
    """
    Attach a shade material to windows via a ``WindowShadingControl``.

    Creates a ``WindowMaterial:Shade`` and an associated construction, then
    assigns a ``WindowShadingControl`` (type ``OnIfScheduleAllows``) to each
    matching window.  Existing shade material and construction objects are reused
    if their names already exist in the IDF.

    Default parameters
    ------------------
    - ``Name``: ``"DEFAULT_SHADE"``
    - ``Solar_Transmittance``: 0.10
    - ``Solar_Reflectance``: 0.70
    - ``Visible_Transmittance``: 0.10
    - ``Visible_Reflectance``: 0.70
    - ``Infrared_Hemispherical_Emissivity``: 0.90
    - ``Thickness`` (m): 0.005
    - ``Conductivity`` (W/m·K): 0.10
    - ``Shading_Type``: ``"InteriorShade"`` — also accepts ``"ExteriorShade"``
    - ``Schedule``: None (no schedule assigned, control is always considered active)

    Parameters
    ----------
    model : Building
        EnergyTool Building object.
    description : dict, optional
        Parameter overrides.  Any key from the default list above can be set.

        - ``"Shading_Type"``: ``"InteriorShade"`` or ``"ExteriorShade"``.
        - ``"Schedule"`` (str): name of an existing EnergyPlus schedule used to
          drive the shading control (value 1 = active, 0 = inactive).

        Example::

            {
                "Name": "MY_SHADE",
                "Solar_Transmittance": 0.05,
                "Shading_Type": "ExteriorShade",
                "Schedule": "SummerOnlySchedule",
            }

    name_filter : str or list[str], optional
        If provided, only windows whose name contains the filter string
        (or any string in the list) receive the shade control.
        If None, all windows are processed.
    """
    DEFAULT_SHADE = {
        "Name": "DEFAULT_SHADE",
        "Solar_Transmittance": 0.10,
        "Solar_Reflectance": 0.70,
        "Visible_Transmittance": 0.10,
        "Visible_Reflectance": 0.70,
        "Infrared_Hemispherical_Emissivity": 0.90,
        "Thickness": 0.005,
        "Conductivity": 0.10,
        "Schedule": None,
        "Shading_Type": "InteriorShade",
    }

    params = DEFAULT_SHADE.copy()

    if description is not None:
        params.update(description)

    shade_name = params["Name"]
    construction_name = f"{shade_name}_CONSTRUCTION"

    existing_shades = {
        obj.Name
        for obj in model.idf.idfobjects["WINDOWMATERIAL:SHADE"]
    }

    if shade_name not in existing_shades:

        model.idf.newidfobject(
            "WINDOWMATERIAL:SHADE",
            Name=shade_name,
            Solar_Transmittance=params["Solar_Transmittance"],
            Solar_Reflectance=params["Solar_Reflectance"],
            Visible_Transmittance=params["Visible_Transmittance"],
            Visible_Reflectance=params["Visible_Reflectance"],
            Infrared_Hemispherical_Emissivity=params[
                "Infrared_Hemispherical_Emissivity"
            ],
            Thickness=params["Thickness"],
            Conductivity=params["Conductivity"],
        )

    existing_constructions = {
        obj.Name
        for obj in model.idf.idfobjects["CONSTRUCTION"]
    }

    if construction_name not in existing_constructions:

        model.idf.newidfobject(
            "CONSTRUCTION",
            Name=construction_name,
            Outside_Layer=shade_name,
        )

    windows = [
        window
        for window in model.idf.idfobjects[
            "FENESTRATIONSURFACE:DETAILED"
        ]
        if (
            (
                not window.Surface_Type
                or window.Surface_Type.upper() == "WINDOW"
            )
            and _matches_filter(window.Name, name_filter)
        )
    ]

    existing_controls = {
        obj.Name: obj
        for obj in model.idf.idfobjects[
            "WINDOWSHADINGCONTROL"
        ]
    }

    for window in windows:

        control_name = (
            f"{window.Name}_{shade_name}_control"
        )

        if control_name in existing_controls:

            control = existing_controls[
                control_name
            ]

        else:

            control = model.idf.newidfobject(
                "WINDOWSHADINGCONTROL",
                Name=control_name,
            )

        control.Zone_Name = (
            getattr(window, "Zone_Name", "")
        )

        control.Shading_Type = (
            params["Shading_Type"]
        )

        control.Construction_with_Shading_Name = (
            construction_name
        )

        control.Shading_Control_Type = (
            "OnIfScheduleAllows"
        )

        if params["Schedule"] is not None:

            control.Schedule_Name = (
                params["Schedule"]
            )

        try:
            control.Fenestration_Surface_1_Name = (
                window.Name
            )
        except Exception:
            pass

def set_blind(
    model: Building,
    description: dict = None,
    name_filter: Union[str, list[str]] = None,
):
    """
    Attach a venetian blind material to windows via a ``WindowShadingControl``.

    Creates a ``WindowMaterial:Blind`` and an associated construction, then
    assigns a ``WindowShadingControl`` (type ``OnIfScheduleAllows``) to each
    matching window.  Existing blind material and construction objects are reused
    if their names already exist in the IDF.

    Available presets (use ``description={"Preset": "<name>", ...}``)
    -----------------------------------------------------------------
    +----------------------+-------------------+------------+------------------------------------+
    | Preset               | Shading_Type      | Slat_Angle | Slat_Beam_Solar_Reflectance        |
    +======================+===================+============+====================================+
    | ``venetian_indoor``  | InteriorBlind     | 45°        | 0.70                               |
    +----------------------+-------------------+------------+------------------------------------+
    | ``bso_exterior``     | ExteriorBlind     | 60°        | 0.80                               |
    +----------------------+-------------------+------------+------------------------------------+
    | ``micro_louver``     | BetweenGlassBlind | 75°        | — (uses default 0.70)              |
    +----------------------+-------------------+------------+------------------------------------+

    ``micro_louver`` also sets ``Slat_Separation`` to 0.01 m.
    Preset values are applied first; any other key in ``description`` overrides them.

    Default parameters
    ------------------
    - ``Name``: ``"DEFAULT_BLIND"``
    - ``Slat_Orientation``: ``"Horizontal"``
    - ``Slat_Width`` (m): 0.08
    - ``Slat_Separation`` (m): 0.07
    - ``Slat_Thickness`` (m): 0.002
    - ``Slat_Angle`` (°): 45
    - ``Slat_Conductivity`` (W/m·K): 160
    - ``Slat_Beam_Solar_Transmittance``: 0.0
    - ``Slat_Beam_Solar_Reflectance``: 0.7
    - ``Slat_Diffuse_Solar_Transmittance``: 0.0
    - ``Slat_Diffuse_Solar_Reflectance``: 0.7
    - ``Slat_Beam_Visible_Transmittance``: 0.0
    - ``Slat_Beam_Visible_Reflectance``: 0.7
    - ``Slat_Diffuse_Visible_Transmittance``: 0.0
    - ``Slat_Diffuse_Visible_Reflectance``: 0.7
    - ``Slat_Infrared_Hemispherical_Transmittance``: 0.0
    - ``Slat_Infrared_Hemispherical_Emissivity``: 0.9
    - ``Blind_to_Glass_Distance`` (m): 0.05
    - ``Minimum_Slat_Angle`` (°): 0
    - ``Maximum_Slat_Angle`` (°): 180
    - ``Shading_Type``: ``"ExteriorBlind"``
    - ``Schedule``: None (no schedule assigned)

    Parameters
    ----------
    model : Building
        EnergyTool Building object.
    description : dict, optional
        Parameter overrides.  Any key from the default list above can be set.

        - ``"Preset"`` (str): one of the preset names above.
        - ``"Schedule"`` (str): name of an existing EnergyPlus schedule (1 = active,
          0 = inactive).

        Example::

            {
                "Preset": "venetian_indoor",
                "Name": "MY_BLIND",
                "Schedule": "SummerBlindSchedule",
            }

    name_filter : str or list[str], optional
        If provided, only windows whose name contains the filter string
        (or any string in the list) receive the blind control.
        If None, all windows are processed.
    """
    BLIND_PRESETS = {
        "venetian_indoor": {
            "Shading_Type": "InteriorBlind",
            "Slat_Angle": 45,
            "Slat_Beam_Solar_Reflectance": 0.7,
        },
        "bso_exterior": {
            "Shading_Type": "ExteriorBlind",
            "Slat_Angle": 60,
            "Slat_Beam_Solar_Reflectance": 0.8,
        },
        "micro_louver": {
            "Shading_Type": "BetweenGlassBlind",
            "Slat_Angle": 75,
            "Slat_Separation": 0.01,
        },
    }

    DEFAULT_BLIND = {
        "Name": "DEFAULT_BLIND",
        "Slat_Orientation": "Horizontal",
        "Slat_Width": 0.08,
        "Slat_Separation": 0.07,
        "Slat_Thickness": 0.002,
        "Slat_Angle": 45,
        "Slat_Conductivity": 160,
        "Slat_Beam_Solar_Transmittance": 0.0,
        "Slat_Beam_Solar_Reflectance": 0.7,
        "Slat_Diffuse_Solar_Transmittance": 0.0,
        "Slat_Diffuse_Solar_Reflectance": 0.7,
        "Slat_Beam_Visible_Transmittance": 0.0,
        "Slat_Beam_Visible_Reflectance": 0.7,
        "Slat_Diffuse_Visible_Transmittance": 0.0,
        "Slat_Diffuse_Visible_Reflectance": 0.7,
        "Slat_Infrared_Hemispherical_Transmittance": 0.0,
        "Slat_Infrared_Hemispherical_Emissivity": 0.9,
        "Blind_to_Glass_Distance": 0.05,
        "Minimum_Slat_Angle": 0,
        "Maximum_Slat_Angle": 180,
        "Schedule": None,
        "Shading_Type": "ExteriorBlind",
    }

    params = DEFAULT_BLIND.copy()
    if description is not None:
        preset = description.pop(
            "Preset",
            None,
        )
        if preset is not None:
            params.update(
                BLIND_PRESETS[preset]
            )
        params.update(description)

    blind_name = params["Name"]
    construction_name = f"{blind_name}_CONSTRUCTION"

    existing_blinds = {
        obj.Name
        for obj in model.idf.idfobjects[
            "WINDOWMATERIAL:BLIND"
        ]
    }

    if blind_name not in existing_blinds:
        model.idf.newidfobject(
            "WINDOWMATERIAL:BLIND",
            Name=blind_name,
            Slat_Orientation=params["Slat_Orientation"],
            Slat_Width=params["Slat_Width"],
            Slat_Separation=params["Slat_Separation"],
            Slat_Thickness=params["Slat_Thickness"],
            Slat_Angle=params["Slat_Angle"],
            Slat_Conductivity=params["Slat_Conductivity"],
            Slat_Beam_Solar_Transmittance=
            params["Slat_Beam_Solar_Transmittance"],
            Front_Side_Slat_Beam_Solar_Reflectance=
            params["Slat_Beam_Solar_Reflectance"],
            Back_Side_Slat_Beam_Solar_Reflectance=
            params["Slat_Beam_Solar_Reflectance"],
            Slat_Diffuse_Solar_Transmittance=
            params["Slat_Diffuse_Solar_Transmittance"],
            Front_Side_Slat_Diffuse_Solar_Reflectance=
            params["Slat_Diffuse_Solar_Reflectance"],
            Back_Side_Slat_Diffuse_Solar_Reflectance=
            params["Slat_Diffuse_Solar_Reflectance"],
            Slat_Beam_Visible_Transmittance=
            params["Slat_Beam_Visible_Transmittance"],
            Front_Side_Slat_Beam_Visible_Reflectance=
            params["Slat_Beam_Visible_Reflectance"],
            Back_Side_Slat_Beam_Visible_Reflectance=
            params["Slat_Beam_Visible_Reflectance"],
            Slat_Diffuse_Visible_Transmittance=
            params["Slat_Diffuse_Visible_Transmittance"],
            Front_Side_Slat_Diffuse_Visible_Reflectance=
            params["Slat_Diffuse_Visible_Reflectance"],
            Back_Side_Slat_Diffuse_Visible_Reflectance=
            params["Slat_Diffuse_Visible_Reflectance"],
            Slat_Infrared_Hemispherical_Transmittance=
            params["Slat_Infrared_Hemispherical_Transmittance"],
            Front_Side_Slat_Infrared_Hemispherical_Emissivity=
            params["Slat_Infrared_Hemispherical_Emissivity"],
            Back_Side_Slat_Infrared_Hemispherical_Emissivity=
            params["Slat_Infrared_Hemispherical_Emissivity"],
            Blind_to_Glass_Distance=
            params["Blind_to_Glass_Distance"],
            Blind_Top_Opening_Multiplier=1,
            Blind_Bottom_Opening_Multiplier=1,
            Blind_Left_Side_Opening_Multiplier=1,
            Blind_Right_Side_Opening_Multiplier=1,
            Minimum_Slat_Angle=
            params["Minimum_Slat_Angle"],
            Maximum_Slat_Angle=
            params["Maximum_Slat_Angle"],
        )

    existing_constructions = {
        obj.Name
        for obj in model.idf.idfobjects[
            "CONSTRUCTION"
        ]
    }

    if construction_name not in existing_constructions:

        model.idf.newidfobject(
            "CONSTRUCTION",
            Name=construction_name,
            Outside_Layer=blind_name,
        )

    windows = [
        window
        for window in model.idf.idfobjects[
            "FENESTRATIONSURFACE:DETAILED"
        ]
        if (
            (
                not window.Surface_Type
                or window.Surface_Type.upper() == "WINDOW"
            )
            and _matches_filter(window.Name, name_filter)
        )
    ]

    existing_controls = {
        obj.Name: obj
        for obj in model.idf.idfobjects[
            "WINDOWSHADINGCONTROL"
        ]
    }

    for window in windows:

        control_name = (
            f"{window.Name}_{blind_name}_control"
        )

        if control_name in existing_controls:

            control = existing_controls[
                control_name
            ]

        else:

            control = model.idf.newidfobject(
                "WINDOWSHADINGCONTROL",
                Name=control_name,
            )

        control.Shading_Type = (
            params["Shading_Type"]
        )

        control.Construction_with_Shading_Name = (
            construction_name
        )

        control.Shading_Control_Type = (
            "OnIfScheduleAllows"
        )

        if params["Schedule"] is not None:

            control.Schedule_Name = (
                params["Schedule"]
            )

        try:
            control.Fenestration_Surface_1_Name = (
                window.Name
            )
        except Exception:
            pass