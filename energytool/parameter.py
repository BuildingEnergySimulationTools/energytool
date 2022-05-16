import energytool.epluspreprocess as pr


class UncertainParameter:
    def __init__(self,
                 name,
                 building,
                 bounds,
                 idf_parameters=None,
                 building_parameters=None):
        self.name = name
        self.building = building
        self.bounds = bounds
        self.idf_parameters = idf_parameters
        self.building_parameters = building_parameters

    def set_value(self, value):
        if self.idf_parameters is not None:
            for element in self.idf_parameters:
                pr.set_objects_field_values(
                    self.building.idf,
                    idf_object=element["idf_object"],
                    idf_object_names=element["names"],
                    field_name=element["field"],
                    values=value
                )
        if self.building_parameters is not None:
            for element in self.building_parameters:
                setattr(element["category"][element["element_name"]],
                        element["key"], value)
