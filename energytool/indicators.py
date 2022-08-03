import energytool.epluspreprocess as pr
import energytool.tools as tl


class AddOutputVariables:
    def __init__(self,
                 name,
                 building,
                 variables,
                 zones='*'):
        self.name = name
        self.building = building
        self.zones = zones
        self.variables = variables

    def pre_process(self):
        vars_to_add = tl.format_input_to_list(self.variables)
        for var in vars_to_add:
            pr.add_output_variable(
                idf=self.building.idf,
                key_values=self.zones,
                variables=var
            )

    def post_process(self):
        pass
