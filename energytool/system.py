import pandas as pd

from energytool.epluspreprocess import add_output_zone_variable
from energytool.epluspostprocess import get_output_zone_variable


class GasBoiler:
    def __init__(self, name, building, zones="*", cop=0.86, energy="gaz", cost=0):
        self.name = name
        self.building = building
        self.cop = cop
        self.energy = energy
        self.cost = cost
        self.zones = zones

    def pre_process(self):
        add_output_zone_variable(
            idf=self.building.idf,
            zones=self.zones,
            variables="Zone Ideal Loads Supply Air Total Heating Energy"
        )

    def post_process(self):
        ideal_heating = get_output_zone_variable(
            eplus_res=self.building.energyplus_results,
            zones=self.zones,
            variables="Zone Ideal Loads Supply Air Total Heating Energy"
        )

        system_out = (ideal_heating * self.cop).sum(axis=1)
        system_out.name = f"{self.name}_Energy"

        self.building.building_results = pd.concat([
            self.building.building_results,
            system_out
        ], axis=1)




