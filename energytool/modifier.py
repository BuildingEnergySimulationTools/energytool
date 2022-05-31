import energytool.epluspreprocess as pr


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
