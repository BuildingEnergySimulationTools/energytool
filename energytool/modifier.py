import energytool.epluspreprocess as pr
from energytool.tools import format_input_to_list
from energytool.tools import is_list_items_in_list
from copy import deepcopy


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

    def set_variant(self, name):
        new_window = self.window_variant_dict[name]
        name_to_replace = [obj.Name for obj in self.windows_materials]

        for construction in self.windows_constructions:
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
    def windows_constructions(self):
        win_cons_names = set(
            win.Construction_Name for win in self.windows)
        return [self.building.idf.getobject("Construction", name)
                for name in win_cons_names]

    @property
    def shading_materials(self):
        materials_name_list = get_constructions_layer_list(
            self.windows_constructions)

        return [self.building.idf.getobject(
            "WindowMaterial:Shade", name)
            for name in set(materials_name_list)
            if self.building.idf.getobject(
                "WindowMaterial:Shade", name) is not None
        ]

    @property
    def shading_control(self):
        return self.building.idf.idfobjects["WindowShadingControl"]

    def set_variant(self, variant_name):
        new_shade = self.shade_variant_dict[variant_name]["shading"]
        shade_names_to_remove = [obj.Name for obj in self.shading_materials]

        for sch in [obj.Name for obj in self.shading_materials]:
            pr.del_obj_by_names(
                self.building.idf, "WindowMaterial:Shade", sch)

        remove_layer_from_constructions(self.building, shade_names_to_remove)

        win_names = [win.Name for win in self.windows]
        self.building.idf.idfobjects["WindowShadingControl"] = [
            obj for obj in self.shading_control
            if not any(is_list_items_in_list(obj.fieldvalues, win_names))
        ]

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

            for cons in self.windows_constructions:
                keys = cons.fieldnames[2:]
                values = cons.fieldvalues[2:]
                values.insert(0, shade_dict["Name"])

                for v, k in zip(values, keys):
                    cons[k] = v

            zone_win_dict = {}
            for win in self.windows:
                ref_wall = win.get_referenced_object("Building_Surface_Name")
                ref_zone = ref_wall.get_referenced_object("Zone_Name")
                if ref_zone.Name not in zone_win_dict.keys():
                    zone_win_dict[ref_zone.Name] = [win.Name]
                else:
                    zone_win_dict[ref_zone.Name].append(win.Name)

            ctrl_template = self.resources_idf.getobject(
                "WindowShadingControl", "Shading_ctrl_template")
            ctrl_dict = idf_object_to_dict(ctrl_template)

            for zone in zone_win_dict.keys():
                ctrl = deepcopy(ctrl_dict)
                ctrl["Name"] = f'{zone}_Shading_control'
                ctrl["Zone_Name"] = zone
                ctrl["Shading_Device_Material_Name"] = shade_dict["Name"]
                for idx, win_name in enumerate(zone_win_dict[zone]):
                    ctrl[f'Fenestration_Surface_{idx + 1}_Name'] = win_name
                self.building.idf.newidfobject(**ctrl)


class WindowsAndShadingModifier:
    def __init__(self,
                 building,
                 name,
                 window_variant_dict,
                 ):
        self.building = building
        self.name = name
        self.window_variant_dict = window_variant_dict
        self.resources_idf = pr.get_resources_idf()
        # Patch because of issue. See later in shade
        # https://github.com/santoshphilip/eppy/issues/275
        self.resources_idf.idfname = None

    def set_variant(self, name):
        window_variant = self.window_variant_dict[name]

        # Look for duplicates
        pr.del_obj_by_names(
            self.building.idf,
            "WindowMaterial:SimpleGlazingSystem",
            window_variant["window"]["Name"]
        )

        pr.del_obj_by_names(
            self.building.idf,
            "Construction",
            f"{name}_External_windows"
        )

        construction_dict = {
            "key": "Construction",
            "Name": f"{name}_External_windows",
        }

        self.building.idf.newidfobject(
            key="WindowMaterial:SimpleGlazingSystem",
            **window_variant["window"]
        )

        # Copy and edit shading from resources
        shade = window_variant["shading"]
        if shade:
            # Add shading object
            shade_template = self.resources_idf.getobject(
                key="WINDOWMATERIAL:SHADE",
                name="Shading_template"
            )

            shade_dict = {
                key: value
                for key, value in zip(
                    shade_template.fieldnames, shade_template.fieldvalues)
            }

            shade_dict["Name"] = f'{name}_shade'

            if isinstance(shade, dict):
                for field in shade.keys():
                    shade_dict[field] = shade[field]

            pr.del_obj_by_names(self.building.idf, "WINDOWMATERIAL:SHADE",
                                shade_dict["Name"])

            self.building.idf.newidfobject(**shade_dict)

            construction_dict["Outside_Layer"] = shade_dict["Name"]
            construction_dict[
                "Layer_2"] = window_variant["window"]["Name"]

            # If schedule, copy from resources
            if window_variant["shading_schedule"]:
                schedule_name = window_variant["shading_schedule"]
            else:
                schedule_name = "ON_24h24h_FULL_YEAR"
            schedule = self.resources_idf.getobject(
                key="Schedule:Compact",
                name=schedule_name)

            if schedule_name not in pr.get_objects_name_list(
                    self.building.idf, "Schedule:Compact"):
                self.building.idf.idfobjects["Schedule:Compact"].append(
                    schedule)

        else:
            construction_dict[
                "Outside_Layer"] = window_variant["window"]["Name"]

        # Combine elements in a construction
        self.building.idf.newidfobject(**construction_dict)

        zones_win_dict = {zone: [] for zone in self.building.zone_name_list}
        for win in self.building.idf.idfobjects[
            "FenestrationSurface:Detailed"]:
            ref_surface_name = win.Building_Surface_Name
            ref_surface = self.building.idf.getobject(
                "BuildingSurface:Detailed", ref_surface_name)
            if ref_surface.Outside_Boundary_Condition == "Outdoors":
                win.Construction_Name = construction_dict["Name"]
                zones_win_dict[ref_surface.Zone_Name].append(win.Name)

        if shade:
            zone_ctrl_list = [z_name for z_name in zones_win_dict.keys()
                              if zones_win_dict[z_name]]
            ctrl_template = self.resources_idf.getobject(
                "WindowShadingControl", "Shading_ctrl_template")
            # Use dictionary because of deepcopy issue
            # https://github.com/santoshphilip/eppy/issues/275
            ctrl_dict = {
                key: value
                for key, value in zip(
                    ctrl_template.fieldnames, ctrl_template.fieldvalues)
            }
            for zone in zone_ctrl_list:
                ctrl = deepcopy(ctrl_dict)
                ctrl["Name"] = f'{zone}_Shading_control'
                ctrl["Zone_Name"] = zone
                ctrl["Construction_with_Shading_Name"] = 'External_windows'
                for idx, win_name in enumerate(zones_win_dict[zone]):
                    ctrl[f'Fenestration_Surface_{idx + 1}_Name'] = win_name
                self.building.idf.newidfobject(**ctrl)
