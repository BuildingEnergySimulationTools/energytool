import eppy

import energytool.epluspreprocess as pr
from energytool.tools import format_input_to_list
from energytool.tools import is_list_items_in_list
from energytool.epluspreprocess import get_building_surface_area
from energytool.epluspreprocess import get_building_volume
from copy import deepcopy

"""Infiltrations related functions"""


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
    return n50 * wind_exposition / (
            1 + f / wind_exposition * (delta_qv / n50) ** 2)


def calculate_building_infiltration_ach_from_q4(
        idf, q4pa=1.2, wind_exposition=0.07, f=15):
    building_outdoor_surface = get_building_surface_area(
        idf, outside_boundary_condition="Outdoors")
    building_volume = get_building_volume(idf)

    # Compute N50 from q4pa
    n50 = get_n50_from_q4(
        q4=q4pa,
        heated_volume=building_volume,
        outside_surface=building_outdoor_surface
    )

    # Get qv
    z_ach_dict = {}
    for siz in idf.idfobjects["Sizing:Zone"]:
        zone = siz.get_referenced_object("Zone_or_ZoneList_Name")
        design = siz.get_referenced_object(
            "Design_Specification_Outdoor_Air_Object_Name")
        if design.Outdoor_Air_Method != "AirChanges/Hour":
            raise ValueError("Outdoor Air method other than AirChanges/Hour"
                             " not yet implemented")
        z_ach_dict[zone.Name] = design.Outdoor_Air_Flow_Air_Changes_per_Hour

    z_hx_dict = {}
    for connection in idf.idfobjects["ZoneHVAC:EquipmentConnections"]:
        z_name = connection.Zone_Name
        sys = connection.get_referenced_object(
            "Zone_Conditioning_Equipment_List_Name").get_referenced_object(
            "Zone_Equipment_1_Name")
        z_hx_dict[z_name] = sys.Heat_Recovery_Type

    qv = sum([
        eppy.modeleditor.zonevolume(idf, zname) * z_ach_dict[zname]
        for zname in z_ach_dict.keys()
        if z_hx_dict[zname]
    ]) / building_volume

    return get_ach_from_n50(
        n50,
        delta_qv=qv,
        wind_exposition=wind_exposition,
        f=f
    )


def get_windows_by_boundary_condition(idf, boundary_condition):
    ext_surf_name = [obj.Name for obj in
                     idf.idfobjects[
                         "BuildingSurface:Detailed"]
                     if obj.Outside_Boundary_Condition == boundary_condition]

    return [obj for obj in
            idf.idfobjects[
                "FenestrationSurface:Detailed"]
            if obj.Building_Surface_Name in ext_surf_name]


def get_constructions_layer_list(constructions):
    construction_list = format_input_to_list(constructions)
    material_name_list = []
    for constructions in construction_list:
        material_name_list += [elmt for elmt, key in
                               zip(constructions.fieldvalues,
                                   constructions.fieldnames)
                               if key not in ["key", "Name"]]
    return material_name_list


def remove_layer_from_constructions(building, names):
    names_list = format_input_to_list(names)

    new_cons_list = []
    for construction in building.idf.idfobjects["Construction"]:
        keys = [k for k in construction.fieldnames]
        values = [v for v in construction.fieldvalues
                  if v not in names_list]

        new_cons = {k: v for v, k in zip(values, keys)}

        new_cons_list.append(new_cons)

    building.idf.idfobjects["Construction"] = [
        building.idf.newidfobject(**cons) for cons in new_cons_list]


def idf_object_to_dict(obj):
    return {k: v for k, v in zip(obj.fieldnames, obj.fieldvalues)}


class OpaqueSurfaceModifier:
    def __init__(self,
                 building,
                 name,
                 surface_type,
                 outside_boundary_condition,
                 construction_variant_dict,
                 ):
        self.building = building
        self.name = name
        self.surface_type = surface_type
        self.outside_boundary_condition = outside_boundary_condition
        self.construction_variant_dict = construction_variant_dict

    def set_variant(self, name):
        construction = self.construction_variant_dict[name]

        for material in construction:
            if "Roughness" not in material.keys():
                material["Roughness"] = "Rough"

            if material["Name"] not in pr.get_objects_name_list(
                    self.building.idf, "Material"):
                new_material = self.building.idf.newidfobject(
                    "Material", **material)

        if name not in pr.get_objects_name_list(
                self.building.idf, "Construction"):
            construction_kwargs = {"Name": name,
                                   "Outside_Layer": construction[0]["Name"]}

            if len(construction) > 1:
                for idx, mat in enumerate(construction[1:]):
                    construction_kwargs[f"Layer_{idx + 2}"] = mat["Name"]

            new_construction = self.building.idf.newidfobject(
                "Construction", **construction_kwargs)

        surface_list = self.building.idf.idfobjects["BuildingSurface:Detailed"]
        surf_to_modify = [
            obj for obj in surface_list
            if obj.Surface_Type == self.surface_type
               and obj.Outside_Boundary_Condition == self.outside_boundary_condition
        ]

        for surf in surf_to_modify:
            surf.Construction_Name = name


class ExternalWindowsModifier:
    def __init__(self,
                 building,
                 name,
                 window_variant_dict,
                 ):
        self.building = building
        self.name = name
        self.window_variant_dict = window_variant_dict

    @property
    def windows(self):
        return get_windows_by_boundary_condition(self.building.idf, "Outdoors")

    @property
    def windows_constructions(self):
        win_cons_names = set(
            win.Construction_Name for win in self.windows)
        return [self.building.idf.getobject("Construction", name)
                for name in win_cons_names]

    @property
    def windows_materials(self):
        win_mat_list = get_constructions_layer_list(self.windows_constructions)

        return [self.building.idf.getobject(
            "WindowMaterial:SimpleGlazingSystem", name)
            for name in set(win_mat_list)
            if self.building.idf.getobject(
                "WindowMaterial:SimpleGlazingSystem", name) is not None
        ]

    @property
    def shaded_window_constructions(self):
        win_names = [win.Name for win in self.windows]
        shading_controls = [
            obj for obj in self.building.idf.idfobjects["WindowShadingControl"]
            if any(is_list_items_in_list(obj.fieldvalues, win_names))]

        obj_list = [obj.get_referenced_object("Construction_with_Shading_Name")
                    for obj in shading_controls]
        set_name = set([obj.Name for obj in obj_list])

        return [self.building.idf.getobject("Construction", name)
                for name in set_name]

    def set_variant(self, name):
        new_window = self.window_variant_dict[name]
        name_to_replace = [obj.Name for obj in self.windows_materials]
        cons_lst = self.windows_constructions + self.shaded_window_constructions

        for construction in cons_lst:
            for field in construction.fieldnames:
                if construction[field] in name_to_replace:
                    construction[field] = new_window["Name"]

        self.building.idf.idfobjects["WindowMaterial:SimpleGlazingSystem"] = [
            win for win in self.building.idf.idfobjects[
                "WindowMaterial:SimpleGlazingSystem"]
            if win not in self.windows_materials]

        self.building.idf.newidfobject(
            key="WindowMaterial:SimpleGlazingSystem", **new_window)


class EnvelopeShadesModifier:
    def __init__(self,
                 building,
                 name,
                 shade_variant_dict,
                 ):
        self.building = building
        self.name = name
        self.shade_variant_dict = shade_variant_dict
        self.resources_idf = pr.get_resources_idf()

    @property
    def windows(self):
        return get_windows_by_boundary_condition(self.building.idf, 'Outdoors')

    @property
    def window_constructions(self):
        win_cons_names = set(
            win.Construction_Name for win in self.windows)
        return [self.building.idf.getobject("Construction", name)
                for name in win_cons_names]

    @property
    def shaded_window_constructions(self):
        obj_list = [obj.get_referenced_object("Construction_with_Shading_Name")
                    for obj in self.shading_control]
        set_name = set([obj.Name for obj in obj_list])

        return [self.building.idf.getobject("Construction", name)
                for name in set_name]

    @property
    def shading_materials(self):
        layer_names = get_constructions_layer_list(
            self.shaded_window_constructions)

        obj_list = [self.building.idf.getobject("WindowMaterial:Shade", name)
                    for name in layer_names
                    if
                    self.building.idf.getobject("WindowMaterial:Shade", name)]

        set_name = set([obj.Name for obj in obj_list])

        return [self.building.idf.getobject("WindowMaterial:Shade", name)
                for name in set_name]

    @property
    def shading_control(self):
        win_names = [win.Name for win in self.windows]
        return [
            obj for obj in self.building.idf.idfobjects["WindowShadingControl"]
            if any(is_list_items_in_list(obj.fieldvalues, win_names))]

    def set_variant(self, variant_name):
        new_shade = self.shade_variant_dict[variant_name]["shading"]

        # Remove Shades
        for shd in self.shading_materials:
            self.building.idf.idfobjects["WindowMaterial:Shade"].remove(shd)
        for cons in self.shaded_window_constructions:
            self.building.idf.idfobjects["Construction"].remove(cons)
        for ctrl in self.shading_control:
            self.building.idf.idfobjects["WindowShadingControl"].remove(ctrl)

        if new_shade:
            # Add shading object
            shade_template = self.resources_idf.getobject(
                key="WINDOWMATERIAL:SHADE",
                name="Shading_template"
            )

            shade_dict = idf_object_to_dict(shade_template)

            for k, v in new_shade.items():
                if k in shade_dict.keys():
                    shade_dict[k] = v

            if "Name" not in new_shade.keys():
                shade_dict["Name"] = f"{variant_name}_shade"

            self.building.idf.newidfobject(**shade_dict)

            for cons in self.window_constructions:
                self.building.idf.copyidfobject(cons)
                new_cons = self.building.idf.idfobjects["Construction"][-1]
                new_cons.Name = f"{cons.Name}_shaded"
                keys = new_cons.fieldnames[2:]
                values = new_cons.fieldvalues[2:]
                values.insert(0, shade_dict["Name"])

                for v, k in zip(values, keys):
                    new_cons[k] = v

            zone_win_dict = {}
            for win in self.windows:
                ref_wall = win.get_referenced_object("Building_Surface_Name")
                ref_zone = ref_wall.get_referenced_object("Zone_Name")
                if ref_zone.Name not in zone_win_dict.keys():
                    zone_win_dict[ref_zone.Name] = [win]
                else:
                    zone_win_dict[ref_zone.Name].append(win)

            ctrl_template = self.resources_idf.getobject(
                "WindowShadingControl", "Shading_ctrl_template")
            ctrl_dict = idf_object_to_dict(ctrl_template)

            for zone in zone_win_dict.keys():
                cons_dict = {}
                for win in zone_win_dict[zone]:
                    cons = win.get_referenced_object("Construction_Name")
                    if cons.Name not in cons_dict.keys():
                        cons_dict[cons.Name] = [win]
                    else:
                        cons_dict[cons.Name].append(win)

                for cons in cons_dict.keys():
                    ctrl = deepcopy(ctrl_dict)
                    ctrl["Name"] = f'{zone}_{cons}_Shading_control'
                    ctrl["Zone_Name"] = zone
                    ctrl["Construction_with_Shading_Name"] = f"{cons}_shaded"
                    for idx, win in enumerate(cons_dict[cons]):
                        ctrl[f'Fenestration_Surface_{idx + 1}_Name'] = win.Name
                    self.building.idf.newidfobject(**ctrl)


class InfiltrationModifier:
    def __init__(self,
                 building,
                 name,
                 infiltration_variant_dict,
                 ):
        self.building = building
        self.name = name
        self.infiltration_variant_dict = infiltration_variant_dict

    @property
    def infiltration_objects(self):
        return self.building.idf.idfobjects[
            'ZoneInfiltration:DesignFlowRate']

    def set_variant(self, variant_name):
        inf = self.infiltration_variant_dict[variant_name]
        self.building.idf.idfobjects['ZoneInfiltration:DesignFlowRate'] = []

        if not self.building.idf.getobject("Schedule:Compact", "On 24/7"):
            self.building.idf.newidfobject(
                key='Schedule:Compact',
                Name='On 24/7',
                Schedule_Type_Limits_Name='Any Number',
                Field_1='Through: 12/31',
                Field_2='For: AllDays',
                Field_3='Until: 24:00',
                Field_4=1
            )

        if "ach" in inf.keys():
            inf_ach = inf["ach"]
        elif "q4pa" in inf.keys():
            inf_ach = calculate_building_infiltration_ach_from_q4(
                self.building.idf,
                **inf)
        else:
            raise ValueError("Invalid infiltration coefficient method. "
                             "Allowed : ach and q4pa")

        for zone in self.building.idf.idfobjects["Zone"]:
            self.building.idf.newidfobject(
                key='ZoneInfiltration:DesignFlowRate',
                Name=f"{zone.Name}_infiltration",
                Zone_or_ZoneList_Name=zone.Name,
                Schedule_Name="On 24/7",
                Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
                Air_Changes_per_Hour=inf_ach,
                Constant_Term_Coefficient=1,
                Temperature_Term_Coefficient=0,
                Velocity_Term_Coefficient=0,
                Velocity_Squared_Term_Coefficient=0
            )


class LightsModifier:
    def __init__(self,
                 building,
                 name,
                 lights_variant_dict,
                 ):
        self.building = building
        self.name = name
        self.lights_variant_dict = lights_variant_dict

    @property
    def lights_objects(self):
        return self.building.idf.idfobjects['Lights']

    def set_variant(self, variant_name):
        power = self.lights_variant_dict[variant_name]

        if self.lights_objects:
            for lig in self.lights_objects:
                lig.Watts_per_Zone_Floor_Area = power
        else:
            raise ValueError("No artificial lighting is defined")



