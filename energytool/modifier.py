from typing import Any

from energytool.base.idf_utils import get_objects_name_list
from energytool.base.idfobject_utils import (
    get_windows_by_boundary_condition,
    get_constructions_layer_list,
)
from energytool.building import Building
from energytool.tools import is_items_in_list


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
    name_filter: str = None,
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
    if name_filter is None:
        name_filter = ""

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
            if name_filter in obj.Name
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
        and name_filter in obj.Name
    ]

    for surf in surf_to_modify:
        surf.Construction_Name = new_construction_name

    construction_to_reverse = [
        obj.Construction_Name
        for obj in surface_list
        if name_filter in obj.Outside_Boundary_Condition_Object
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
    name_filter: str = None,
    surface_name_filter: str = None,
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
            if (
                name_filter is None and surface_name_filter in win.Building_Surface_Name
            )
            or (surface_name_filter is None and name_filter in win.Name)
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
    name_filter: str = None,
    surface_name_filter: str = None,
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
            if (surface_name_filter is None and name_filter in op.Surface_Name)
            or (name_filter is None and surface_name_filter in op.Surface_Name)
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
    name_filter: str = None,
    surface_name_filter: str = None,
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

    if name_filter is None:
        name_filter = ""
    if surface_name_filter is None:
        surface_name_filter = ""

    filtered_windows = [
        window
        for window in idf.idfobjects["FenestrationSurface:Detailed"]
        if (surface_name_filter == "" and name_filter in window.Name)
        or (name_filter == "" and surface_name_filter in window.Building_Surface_Name)
        or (surface_name_filter == "" and name_filter == "")
        or (
            surface_name_filter in window.Building_Surface_Name
            and name_filter in window.Name
        )
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
    name_filter: str = None,
    surface_name_filter: str = None,
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
            if (surface_name_filter is None and name_filter in window.Name)
            or (
                name_filter is None
                and surface_name_filter in window.Building_Surface_Name
            )
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
    name_filter: str = None,
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
            if name_filter is not None and name_filter in obj["Name"]:
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
    name_filter: str = None,
    surface_name_filter: str = None,
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
