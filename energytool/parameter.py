import energytool.epluspreprocess as pr


class UncertainParameter:
    def __init__(self,
                 name,
                 building,
                 bounds,
                 idf_parameters=None,
                 building_parameters=None,
                 absolute=False):
        self.name = name
        self.building = building
        self.bounds = bounds
        self.idf_parameters = idf_parameters
        self.building_parameters = building_parameters
        self.absolute = absolute
        if idf_parameters is not None:
            self.idf_nominal_values = [
                pr.get_objects_field_values(
                    idf=self.building.idf,
                    idf_object=element["idf_object"],
                    idf_object_names=element["names"],
                    field_name=element["field"]
                )
                for element in idf_parameters
            ]
        else:
            self.idf_nominal_values = []

        if building_parameters is not None:
            self.building_nominal_values = [
                getattr(
                    getattr(building, element['category'])[element["element_name"]],
                    element["key"])
                for element in building_parameters
            ]
        else:
            self.building_nominal_values = []

    def set_value(self, value):
        if self.idf_parameters is not None:
            for element, nominal_values in zip(
                    self.idf_parameters, self.idf_nominal_values):
                if not self.absolute:
                    values_to_set = [val * value for val in nominal_values]
                else:
                    values_to_set = value

                pr.set_objects_field_values(
                    self.building.idf,
                    idf_object=element["idf_object"],
                    idf_object_names=element["names"],
                    field_name=element["field"],
                    values=values_to_set
                )
        if self.building_parameters is not None:
            for element, nominal_value in zip(
                    self.building_parameters, self.building_nominal_values):
                if not self.absolute:
                    value_to_set = value * nominal_value
                else:
                    value_to_set = value
                setattr(getattr(self.building, element["category"])[
                            element["element_name"]],
                        element["key"],
                        value_to_set)
