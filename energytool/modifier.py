from typing import Any

from energytool.base.idf_utils import get_objects_name_list
from energytool.base.idfobject_utils import (
    get_windows_by_boundary_condition,
    get_constructions_layer_list,
)
from energytool.building import Building
from energytool.tools import is_items_in_list


def set_opaque_surface_construction(
    model: Building,
    description: dict[str, list[dict[str, Any]]],
    name_filter: str = None,
    surface_type: str = "Wall",
    outside_boundary_condition: str = "Outdoors",
):
    """
    This function modifies the construction of opaque building surfaces in an EnergyPlus
    IDF file.
    It is supposed to be used as a modifier for the corrai variant framework

    :param model: energytool Building object.
    :param description: A dictionary describing the construction materials and
        properties. The argument must be of the form :
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
    :param surface_type: The type of surface to modify
        (default is 'Wall').
    :param outside_boundary_condition: The outside boundary condition
        (default is 'Outdoors').
    """
    if name_filter is None:
        name_filter = ""

    new_construction_name = list(description.keys())[0]
    new_composition = description[new_construction_name]
    surface_list = model.idf.idfobjects["BuildingSurface:Detailed"]

    if surface_type not in surface_list[0].getfieldidd("Surface_Type")["key"]:
        raise ValueError(
            f"surface_type must be one of "
            f"{surface_list[0].getfieldidd('Surface_Type')['key']}, "
            f"got {surface_type}"
        )

    if (
        outside_boundary_condition
        not in surface_list[0].getfieldidd("Outside_Boundary_Condition")["key"]
    ):
        raise ValueError(
            f"surface_type must be one of "
            f"{surface_list[0].getfieldidd('Outside_Boundary_Condition')['key']}, "
            f"got {outside_boundary_condition}"
        )

    for material in new_composition:
        if "Roughness" not in material.keys():
            material["Roughness"] = "Rough"

        if material["Name"] not in get_objects_name_list(model.idf, "Material"):
            model.idf.newidfobject("Material", **material)

    if new_construction_name not in get_objects_name_list(model.idf, "Construction"):
        construction_kwargs = {
            "Name": new_construction_name,
            "Outside_Layer": new_composition[0]["Name"],
        }

        if len(new_composition) > 1:
            for idx, mat in enumerate(new_composition[1:]):
                construction_kwargs[f"Layer_{idx + 2}"] = mat["Name"]

        model.idf.newidfobject("Construction", **construction_kwargs)

    surf_to_modify = [
        obj
        for obj in surface_list
        if obj.Surface_Type == surface_type
        and obj.Outside_Boundary_Condition == outside_boundary_condition
        and name_filter in obj.Name
    ]

    for surf in surf_to_modify:
        surf.Construction_Name = new_construction_name


def set_external_windows(
    model: Building,
    description: dict[str, dict[str, Any]],
    name_filter: str = None,
    boundary_conditions: str = "Outdoors",
):
    """
    Replace windows in an EnergyPlus building model with new window descriptions.

    This function iterates through the windows in the model, filters them based on their
    name and boundary conditions, and replaces them with new window descriptions.
    It also handles associated constructions and materials.

    :param model: An EnergyPlus building model.
    :param description: A dictionary containing the new window description(s).
        the expected dictionary must be of the following form:
        {
            "Variant_1": {
                "Name": "Var_1",
                "UFactor": 1,
                "Solar_Heat_Gain_Coefficient": 0.1,
                "Visible_Transmittance": 0.1,
            },
        }
    :param name_filter: An optional filter to match window names.
    :param boundary_conditions: The boundary condition for the windows
    (default is "Outdoors").

    """
    idf = model.idf

    # Get windows materials list and shaded windows constructions
    windows = get_windows_by_boundary_condition(
        idf, boundary_condition=boundary_conditions
    )

    if name_filter is not None:
        windows = [win for win in windows if name_filter in win.Name]

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
):
    idf = model.idf

    openings = idf.idfobjects["AirflowNetwork:MultiZone:Surface"]
    if name_filter is not None:
        openings = [op for op in openings if name_filter in op.Surface_Name]

    new_opening_ratio_name = list(description.keys())[0]
    new_opening_ratio = description[new_opening_ratio_name][
        "WindowDoor_Opening_Factor_or_Crack_Factor"
    ]

    for opening in openings:
        opening["WindowDoor_Opening_Factor_or_Crack_Factor"] = new_opening_ratio


#
# class EnvelopeShadesModifier:
#     def __init__(
#         self,
#         name,
#         building=None,
#         variant_dict=None,
#     ):
#         self.name = name
#         self.building = building
#         self.variant_dict = variant_dict
#         self.resources_idf = energytool.base.epluspreprocess.get_resources_idf()
#
#     @property
#     def windows(self):
#         return get_windows_by_boundary_condition(self.building.idf, "Outdoors")
#
#     @property
#     def window_constructions(self):
#         win_cons_names = set(win.Construction_Name for win in self.windows)
#         return [
#             self.building.idf.getobject("Construction", name) for name in win_cons_names
#         ]
#
#     @property
#     def shaded_window_constructions(self):
#         obj_list = [
#             obj.get_referenced_object("Construction_with_Shading_Name")
#             for obj in self.shading_control
#         ]
#         set_name = set([obj.Name for obj in obj_list])
#
#         return [self.building.idf.getobject("Construction", name) for name in set_name]
#
#     @property
#     def shading_materials(self):
#         layer_names = get_constructions_layer_list(self.shaded_window_constructions)
#
#         obj_list = [
#             self.building.idf.getobject("WindowMaterial:Shade", name)
#             for name in layer_names
#             if self.building.idf.getobject("WindowMaterial:Shade", name)
#         ]
#
#         set_name = set([obj.Name for obj in obj_list])
#
#         return [
#             self.building.idf.getobject("WindowMaterial:Shade", name)
#             for name in set_name
#         ]
#
#     @property
#     def shading_control(self):
#         win_names = [win.Name for win in self.windows]
#         return [
#             obj
#             for obj in self.building.idf.idfobjects["WindowShadingControl"]
#             if any(is_items_in_list(obj.fieldvalues, win_names))
#         ]
#
#     def set_variant(self, variant_name):
#         new_shade = self.variant_dict[variant_name]["shading"]
#
#         # Remove Shades
#         for shd in self.shading_materials:
#             self.building.idf.idfobjects["WindowMaterial:Shade"].remove(shd)
#         for cons in self.shaded_window_constructions:
#             self.building.idf.idfobjects["Construction"].remove(cons)
#         for ctrl in self.shading_control:
#             self.building.idf.idfobjects["WindowShadingControl"].remove(ctrl)
#
#         if new_shade:
#             # Add shading object
#             shade_template = self.resources_idf.getobject(
#                 key="WINDOWMATERIAL:SHADE", name="Shading_template"
#             )
#
#             shade_dict = idf_object_to_dict(shade_template)
#
#             for k, v in new_shade.items():
#                 if k in shade_dict.keys():
#                     shade_dict[k] = v
#
#             if "Name" not in new_shade.keys():
#                 shade_dict["Name"] = f"{variant_name}_shade"
#
#             self.building.idf.newidfobject(**shade_dict)
#
#             for cons in self.window_constructions:
#                 self.building.idf.copyidfobject(cons)
#                 new_cons = self.building.idf.idfobjects["Construction"][-1]
#                 new_cons.Name = f"{cons.Name}_shaded"
#                 keys = new_cons.fieldnames[2:]
#                 values = new_cons.fieldvalues[2:]
#                 values.insert(0, shade_dict["Name"])
#
#                 for v, k in zip(values, keys):
#                     new_cons[k] = v
#
#             zone_win_dict = {}
#             for win in self.windows:
#                 ref_wall = win.get_referenced_object("Building_Surface_Name")
#                 ref_zone = ref_wall.get_referenced_object("Zone_Name")
#                 if ref_zone.Name not in zone_win_dict.keys():
#                     zone_win_dict[ref_zone.Name] = [win]
#                 else:
#                     zone_win_dict[ref_zone.Name].append(win)
#
#             ctrl_template = self.resources_idf.getobject(
#                 "WindowShadingControl", "Shading_ctrl_template"
#             )
#             ctrl_dict = idf_object_to_dict(ctrl_template)
#
#             for zone in zone_win_dict.keys():
#                 cons_dict = {}
#                 for win in zone_win_dict[zone]:
#                     cons = win.get_referenced_object("Construction_Name")
#                     if cons.Name not in cons_dict.keys():
#                         cons_dict[cons.Name] = [win]
#                     else:
#                         cons_dict[cons.Name].append(win)
#
#                 for cons in cons_dict.keys():
#                     ctrl = deepcopy(ctrl_dict)
#                     ctrl["Name"] = f"{zone}_{cons}_Shading_control"
#                     ctrl["Zone_Name"] = zone
#                     ctrl["Construction_with_Shading_Name"] = f"{cons}_shaded"
#                     for idx, win in enumerate(cons_dict[cons]):
#                         ctrl[f"Fenestration_Surface_{idx + 1}_Name"] = win.Name
#                     self.building.idf.newidfobject(**ctrl)
#
#
# class InfiltrationModifier:
#     def __init__(
#         self,
#         name,
#         building=None,
#         variant_dict=None,
#     ):
#         self.name = name
#         self.building = building
#         self.variant_dict = variant_dict
#
#     @property
#     def infiltration_objects(self):
#         return self.building.idf.idfobjects["ZoneInfiltration:DesignFlowRate"]
#
#     def set_variant(self, variant_name):
#         inf = self.variant_dict[variant_name]
#         self.building.idf.idfobjects["ZoneInfiltration:DesignFlowRate"] = []
#
#         if not self.building.idf.getobject("Schedule:Compact", "On 24/7"):
#             self.building.idf.newidfobject(
#                 key="Schedule:Compact",
#                 Name="On 24/7",
#                 Schedule_Type_Limits_Name="Any Number",
#                 Field_1="Through: 12/31",
#                 Field_2="For: AllDays",
#                 Field_3="Until: 24:00",
#                 Field_4=1,
#             )
#
#         if "ach" in inf.keys():
#             inf_ach = inf["ach"]
#         elif "q4pa" in inf.keys():
#             inf_ach = get_building_infiltration_ach_from_q4(self.building.idf, **inf)
#         else:
#             raise ValueError(
#                 "Invalid infiltration coefficient method. " "Allowed : ach and q4pa"
#             )
#
#         for zone in self.building.idf.idfobjects["Zone"]:
#             self.building.idf.newidfobject(
#                 key="ZoneInfiltration:DesignFlowRate",
#                 Name=f"{zone.Name}_infiltration",
#                 Zone_or_ZoneList_Name=zone.Name,
#                 Schedule_Name="On 24/7",
#                 Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
#                 Air_Changes_per_Hour=inf_ach,
#                 Constant_Term_Coefficient=1,
#                 Temperature_Term_Coefficient=0,
#                 Velocity_Term_Coefficient=0,
#                 Velocity_Squared_Term_Coefficient=0,
#             )
#
#
# class LightsModifier:
#     def __init__(
#         self,
#         name,
#         building=None,
#         variant_dict=None,
#     ):
#         self.name = name
#         self.building = building
#         self.variant_dict = variant_dict
#
#     @property
#     def lights_objects(self):
#         return self.building.idf.idfobjects["Lights"]
#
#     def set_variant(self, variant_name):
#         power = self.variant_dict[variant_name]
#
#         if self.lights_objects:
#             for lig in self.lights_objects:
#                 lig.Watts_per_Zone_Floor_Area = power
#         else:
#             raise ValueError("No artificial lighting is defined")
#
#
# class SystemModifier:
#     def __init__(
#         self,
#         name,
#         building=None,
#         category=None,
#         system_name=None,
#         variant_dict=None,
#     ):
#         self.name = name
#         self.building = building
#         self.category = category
#         self.system_name = system_name
#         self.variant_dict = variant_dict
#
#     def set_variant(self, variant_name):
#         sys_dict = getattr(self.building, self.category)
#         if self.system_name not in sys_dict.keys():
#             raise ValueError("Unknown system")
#
#         new_sys = self.variant_dict[variant_name]
#         new_sys.building = self.building
#         sys_dict[self.system_name] = new_sys
#
#         new_sys.pre_process()
#
#
# class Combiner:
#     def __init__(self, building, modifier_list=None):
#         if modifier_list is None:
#             modifier_list = []
#         self.modifier_list = modifier_list
#         self.building = building
#         self.simulation_list = []
#         self.simulation_runner = SimulationsRunner(self.simulation_list)
#
#     @property
#     def modifier_name_list(self):
#         return [mod.name for mod in self.modifier_list]
#
#     @property
#     def combination_list(self):
#         var_list = [
#             ["Existing"] + list(mod.variant_dict.keys()) for mod in self.modifier_list
#         ]
#         return list(itertools.product(*var_list))
#
#     def run(
#         self,
#         epw_file_path,
#         simulation_start=dt.datetime(2009, 1, 1, 0, 0, 0),
#         simulation_stop=dt.datetime(2009, 12, 31, 23, 0, 0),
#         timestep_per_hour=6,
#         run_directory=None,
#         nb_cpus=-1,
#         nb_simu_per_batch=5,
#     ):
#         prog_bar = progress_bar(range(len(self.combination_list)))
#         for mb, combine in zip(prog_bar, self.combination_list):
#             simu_building = deepcopy(self.building)
#             for mod, var in zip(self.modifier_list, combine):
#                 if var != "Existing":
#                     combine_mod = deepcopy(mod)
#                     setattr(combine_mod, "building", simu_building)
#                     combine_mod.set_variant(var)
#
#             self.simulation_list.append(
#                 Simulation(
#                     building=simu_building,
#                     epw_file_path=epw_file_path,
#                     simulation_start=simulation_start,
#                     simulation_stop=simulation_stop,
#                     timestep_per_hour=timestep_per_hour,
#                 )
#             )
#
#         self.simulation_runner = SimulationsRunner(
#             simu_list=self.simulation_list,
#             run_dir=run_directory,
#             nb_cpus=nb_cpus,
#             nb_simu_per_batch=nb_simu_per_batch,
#         )
#
#         self.simulation_runner.run()
#
#     def get_annual_system_results(self, per_square_meter=False):
#         if not self.simulation_list:
#             raise ValueError("No simulation results to get")
#         combine_columns = pd.DataFrame(
#             self.combination_list, columns=self.modifier_name_list
#         )
#
#         calc_res = pd.DataFrame()
#
#         for i, sim in enumerate(self.simulation_list):
#             sim_res = sim.building.get_system_energy_results.sum().to_frame().T
#             sim_res.index = [i]
#             calc_res = pd.concat([calc_res, sim_res])
#
#         calc_res = calc_res / 3600 / 1000
#
#         if per_square_meter:
#             calc_res = calc_res / self.building.surface
#
#         return pd.concat([combine_columns, calc_res], axis=1)
#
#     def plot_consumption_stacked_bar(self, per_square_meter=False):
#         df = self.get_annual_system_results(per_square_meter)
#         if per_square_meter:
#             unit = "[kWh/m²]"
#         else:
#             unit = "[kWh]"
#
#         df["Variant_index"] = df.index
#         df = df.sort_values(by="Total", ascending=False)
#         df.index = np.arange(df.shape[0])
#         fig = px.bar(df, y=self.building.get_system_energy_results.columns)
#
#         fig.update_layout(
#             title="Annual HVAC system consumption",
#             yaxis_title=f"Hvac system consumption {unit}",
#             legend_title="HVAC",
#         )
#
#         fig.show()
