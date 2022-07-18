import numpy as np
import pandas as pd

import energytool.epluspreprocess as pr
import energytool.epluspostprocess as po
import energytool.tools as tl


class HeaterSimple:
    def __init__(self, name, building, zones="*", cop=0.86, energy="gaz",
                 cost=0):
        self.name = name
        self.building = building
        self.cop = cop
        self.energy = energy
        self.cost = cost
        self.zones = zones

    def pre_process(self):
        pr.add_output_variable(
            idf=self.building.idf,
            key_values=self.zones,
            variables="Zone Ideal Loads Supply Air Total Heating Energy"
        )

    def post_process(self):
        ideal_heating = po.get_output_zone_variable(
            eplus_res=self.building.energyplus_results,
            zones=self.zones,
            variables="Zone Ideal Loads Supply Air Total Heating Energy"
        )

        system_out = (ideal_heating / self.cop).sum(axis=1)
        self.building.building_results[
            f"{self.name}_Energy"] = system_out


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
        pr.add_output_variable(
            idf=self.building.idf,
            key_values=self.zones,
            variables="Zone Ideal Loads Supply Air Total Heating Energy"
        )

    def post_process(self):
        ideal_heating = po.get_output_zone_variable(
            eplus_res=self.building.energyplus_results,
            zones=self.zones,
            variables="Zone Ideal Loads Supply Air Total Heating Energy"
        )

        system_out = (ideal_heating * self.ratio).sum(axis=1)
        self.building.building_results[f"{self.name}_Energy"] = system_out


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
                 fan_energy_coefficient=0.23,  # Wh/m3
                 heat_recovery_efficiency=None,
                 ach=None):

        self.name = name
        self.building = building
        self.zones = zones
        self.ach = ach
        self.fan_energy_coefficient = fan_energy_coefficient
        self.heat_recovery_efficiency = heat_recovery_efficiency

    def pre_process(self):
        pr.add_output_variable(
            idf=self.building.idf,
            key_values=self.zones,
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
                pr.set_objects_field_values(
                    idf=self.building.idf,
                    idf_object="DesignSpecification:OutdoorAir",
                    idf_object_names=obj_name_arg,
                    field_name=field,
                    values=value
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
                pr.set_objects_field_values(
                    idf=self.building.idf,
                    idf_object="ZoneHVAC:IdealLoadsAirSystem",
                    idf_object_names=obj_name_arg,
                    field_name=field,
                    values=value
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
        self.building.building_results[f"{self.name}_Energy"] = system_out


class DHWIdealExternal:
    def __init__(self,
                 name,
                 building,
                 zones='*',
                 cop=0.95,  # Wh/m3
                 t_dwh_set_point=60,
                 t_cold_water=15,
                 daily_volume_occupant=50,
                 cp_water=4183.2  # J/L.°C
                 ):
        self.name = name
        self.building = building
        self.zones = zones
        self.cop = cop
        self.t_dwh_set_point = t_dwh_set_point
        self.t_cold_water = t_cold_water
        self.daily_volume_occupant = daily_volume_occupant
        self.cp_water = cp_water

    def pre_process(self):
        pass

    def post_process(self):
        nb_people = pr.get_number_of_people(
            self.building.idf, zones=self.zones)

        # 4183.2[J/L.°C]
        daily_cons_per_occupant = (
                self.cp_water *
                (self.t_dwh_set_point - self.t_cold_water) *
                self.daily_volume_occupant
        )

        nb_days = self.building.energyplus_results.resample("D").sum().shape[0]
        nb_entry = self.building.energyplus_results.shape[0]

        dhw_consumption = (
                daily_cons_per_occupant * nb_days * nb_people / self.cop
        )

        self.building.building_results[f"{self.name}_Energy"] = (
            np.ones(nb_entry) * dhw_consumption / nb_entry
        )


class ArtificialLightingSimple:
    def __init__(self,
                 name,
                 building,
                 zones='*',
                 power_ratio=3,  # W/m²
                 cop=1):
        self.name = name
        self.building = building
        self.zones = zones
        self.power_ratio = power_ratio
        self.cop = cop

    def pre_process(self):
        pr.add_output_variable(
            idf=self.building.idf,
            key_values=self.zones,
            variables="Zone Lights Electricity Energy"
        )

        config = {
            "Design_Level_Calculation_Method": "Watts/Area",
            "Watts_per_Zone_Floor_Area": self.power_ratio,
        }
        obj_name_arg = tl.select_by_strings(
            items_list=pr.get_objects_name_list(
                self.building.idf, "Lights"),
            select_by=self.zones
        )

        for field, value in config.items():
            pr.set_objects_field_values(
                idf=self.building.idf,
                idf_object="Lights",
                idf_object_names=obj_name_arg,
                field_name=field,
                values=value
            )

    def post_process(self):
        lighting_consumption = po.get_output_zone_variable(
            eplus_res=self.building.energyplus_results,
            zones=self.zones,
            variables="Zone Lights Electricity Energy"
        )

        lighting_out = (lighting_consumption / self.cop).sum(axis=1)
        self.building.building_results[f"{self.name}_Energy"] = lighting_out


class AHUControl:
    def __init__(self,
                 name,
                 building,
                 zones='*',
                 control_strategy="Schedule",
                 schedule_name="ON_24h24h_FULL_YEAR",
                 data_frame=None):
        self.name = name
        self.building = building
        self.zones = zones
        self.control_strategy = control_strategy
        self.schedule_name = schedule_name
        self.resources_idf = pr.get_resources_idf()

        if data_frame is not None:
            if data_frame.shape[1] > 1:
                raise ValueError("Specify a one columns DataFrame or "
                                 "a Pandas Series")
            to_test = np.logical_or(data_frame < 0, data_frame > 1).to_numpy()
            if to_test.any():
                raise ValueError("Invalid values in DataFrame. Values > 1 "
                                 "or Value < 0")
        self.data_frame = data_frame

    def pre_process(self):
        if self.control_strategy == "Schedule":
            # Get schedule in resources file
            idf_schedules = self.building.idf.idfobjects['Schedule:Compact']
            schedule_to_copy = pr.get_objects_by_names(
                self.resources_idf, "Schedule:Compact", self.schedule_name)

            # Copy in building idf if not already present
            if schedule_to_copy[0].Name not in pr.get_objects_name_list(
                    self.building.idf, 'Schedule:Compact'):
                idf_schedules.append(schedule_to_copy[0])

            schedule_name = schedule_to_copy[0].Name

        elif self.control_strategy == "DataFrame":
            pr.add_hourly_schedules_from_df(self.building.idf, self.data_frame)
            schedule_name = self.data_frame.columns[0]

        else:
            raise ValueError("Specify valid control_strategy")

        # Get Design spec object to modify and set schedule
        obj_name_arg = tl.select_by_strings(
            items_list=pr.get_objects_name_list(
                self.building.idf, "DesignSpecification:OutdoorAir"),
            select_by=self.zones
        )

        pr.set_objects_field_values(
            idf=self.building.idf,
            idf_object="DesignSpecification:OutdoorAir",
            idf_object_names=obj_name_arg,
            field_name="Outdoor_Air_Schedule_Name",
            values=schedule_name
        )

    def post_process(self):
        pass


class NaturalVentilation:
    def __init__(self,
                 name,
                 building,
                 zones='*',
                 ach=0.7,
                 occupancy_schedule=True,
                 ventilation_kwargs=None):
        self.name = name
        self.building = building
        self.zones = zones
        self.ach = ach
        self.occupancy_schedule = occupancy_schedule
        self.ventilation_kwargs = ventilation_kwargs

    def pre_process(self):
        pr.add_natural_ventilation(
            self.building.idf,
            self.ach,
            self.zones,
            self.occupancy_schedule,
            self.ventilation_kwargs)

    def post_process(self):
        pass
