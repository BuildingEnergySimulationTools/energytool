import pandas as pd

import energytool.epluspreprocess as pr
import energytool.epluspostprocess as po
import energytool.tools as tl


class GasBoiler:
    def __init__(self, name, building, zones="*", cop=0.86, energy="gaz",
                 cost=0):
        self.name = name
        self.building = building
        self.cop = cop
        self.energy = energy
        self.cost = cost
        self.zones = zones

    def pre_process(self):
        pr.add_output_zone_variable(
            idf=self.building.idf,
            zones=self.zones,
            variables="Zone Ideal Loads Supply Air Total Heating Energy"
        )

    def post_process(self):
        ideal_heating = po.get_output_zone_variable(
            eplus_res=self.building.energyplus_results,
            zones=self.zones,
            variables="Zone Ideal Loads Supply Air Total Heating Energy"
        )

        system_out = (ideal_heating / self.cop).sum(axis=1)
        system_out.name = f"{self.name}_Energy"

        self.building.building_results = pd.concat([
            self.building.building_results,
            system_out
        ], axis=1)


class AuxiliarySimplified:
    """
    Simplified heating auxiliary component energy consumption.
    multiply ideal heat need by a constant. Default 5%
    """

    def __init__(self, name, building, zones="*", ratio=0.05):
        self.name = name
        self.building = building
        self.zones = zones
        self.ratio = ratio

    def pre_process(self):
        pr.add_output_zone_variable(
            idf=self.building.idf,
            zones=self.zones,
            variables="Zone Ideal Loads Supply Air Total Heating Energy"
        )

    def post_process(self):
        ideal_heating = po.get_output_zone_variable(
            eplus_res=self.building.energyplus_results,
            zones=self.zones,
            variables="Zone Ideal Loads Supply Air Total Heating Energy"
        )

        system_out = (ideal_heating * self.ratio).sum(axis=1)
        system_out.name = f"{self.name}_Energy"

        self.building.building_results = pd.concat([
            self.building.building_results,
            system_out
        ], axis=1)


class AirHandlingUnit:
    """
    If "ach" argument is used, DesignSpecification:OutdoorAir objects Names
    corresponding to specified "zones" must contain zones Name
    in their "Name" field
    """

    def __init__(self,
                 name,
                 building,
                 zones='*',
                 fan_energy_coefficient=0.23, # Wh/m3
                 heat_recovery_efficiency=None,
                 ach=None):

        self.name = name
        self.building = building
        self.zones = zones
        self.ach = ach
        self.fan_energy_coefficient = fan_energy_coefficient
        self.heat_recovery_efficiency = heat_recovery_efficiency

    def pre_process(self):
        pr.add_output_zone_variable(
            idf=self.building.idf,
            zones=self.zones,
            variables=
            "Zone Mechanical Ventilation Standard Density Volume Flow Rate"
        )

        # Modify ACH if necessary
        if self.ach is not None:
            obj_name_arg = tl.select_by_strings(
                items_list=pr.get_objects_name_list(
                    self.building.idf, "DesignSpecification:OutdoorAir"),
                select_by=self.zones
            )

            mod_fields = {
                "Outdoor_Air_Flow_Air_Changes_per_Hour": self.ach,
                "Outdoor_Air_Method": "AirChanges/Hour"
            }

            for field, value in mod_fields.items():
                pr.set_object_field_value(
                    idf=self.building.idf,
                    idf_object="DesignSpecification:OutdoorAir",
                    idf_object_name=obj_name_arg,
                    field_name=field,
                    value=value
                )

        # Modify Heat Recovery if necessary
        if self.heat_recovery_efficiency is not None:
            obj_name_arg = tl.select_by_strings(
                items_list=pr.get_objects_name_list(
                    self.building.idf, "ZoneHVAC:IdealLoadsAirSystem"),
                select_by=self.zones
            )

            mod_fields = {
                "Sensible_Heat_Recovery_Effectiveness": self.heat_recovery_efficiency,
                "Latent_Heat_Recovery_Effectiveness": self.heat_recovery_efficiency,
            }
            for field, value in mod_fields.items():
                pr.set_object_field_value(
                    idf=self.building.idf,
                    idf_object="ZoneHVAC:IdealLoadsAirSystem",
                    idf_object_name=obj_name_arg,
                    field_name=field,
                    value=value
                )

    def post_process(self):
        air_volume = po.get_output_zone_variable(
            eplus_res=self.building.energyplus_results,
            zones=self.zones,
            variables=
            "Zone Mechanical Ventilation Standard Density Volume Flow Rate"
        )

        # Air_volume [m3/s] * 3600 [s] * fan_coef [Wh/m3] * 3600 [J/Wh]
        system_out = (
                air_volume * 3600 * self.fan_energy_coefficient * 3600
        ).sum(axis=1)

        system_out.name = f"{self.name}_Energy"

        self.building.building_results = pd.concat([
            self.building.building_results,
            system_out
        ], axis=1)
