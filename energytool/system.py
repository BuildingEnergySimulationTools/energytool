import eppy.modeleditor
import numpy as np
import pandas as pd

import energytool.epluspreprocess as pr
import energytool.epluspostprocess as po
import energytool.tools as tl


class HeaterSimple:
    def __init__(self, name, building, zones="*", cop=0.86):
        self.name = name
        self.building = building
        self.cop = cop
        if zones == '*':
            self.zones = self.building.zone_name_list
        else:
            self.zones = tl.format_input_to_list(zones)

        # Find IdealLoadsAirSystem name list
        self.ilas_list = []
        for zone in self.zones:
            equip_con = building.idf.getobject(
                'ZONEHVAC:EQUIPMENTCONNECTIONS', zone)
            # If zone has hvac equipments
            if not equip_con:
                raise ValueError(f"{zone} doesn't have an IdealLoadAirSystem")

            equip_list = equip_con.get_referenced_object(
                'Zone_Conditioning_Equipment_List_Name')
            for i in range(18):
                # 18 seem to be the max allowed (eppy)
                hvac_obj = equip_list.get_referenced_object(
                        f'Zone_Equipment_{i + 1}_Name')
                if hvac_obj:
                    if hvac_obj.key == 'ZoneHVAC:IdealLoadsAirSystem':
                        self.ilas_list.append(hvac_obj)

    @property
    def ilas_name_list(self):
        return [ilas.Name for ilas in self.ilas_list]

    def pre_process(self):
        pr.add_output_variable(
            idf=self.building.idf,
            key_values=self.ilas_name_list,
            variables="Zone Ideal Loads Supply Air Total Heating Energy"
        )

    def post_process(self):
        # Warning, works only if ilas name contains zone name
        ideal_heating = po.get_output_variable(
            eplus_res=self.building.energyplus_results,
            key_values=self.ilas_name_list,
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

    def __init__(self, name, building=None, zones="*", ratio=0.05):
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
        ideal_heating = po.get_output_variable(
            eplus_res=self.building.energyplus_results,
            key_values=self.zones,
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
                 building=None,
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
                "Heat_Recovery_Type": "Sensible",
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
        air_volume = po.get_output_variable(
            eplus_res=self.building.energyplus_results,
            key_values=self.zones,
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
                 building=None,
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
                 building=None,
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
        lighting_consumption = po.get_output_variable(
            eplus_res=self.building.energyplus_results,
            key_values=self.zones,
            variables="Zone Lights Electricity Energy"
        )

        lighting_out = (lighting_consumption / self.cop).sum(axis=1)
        self.building.building_results[f"{self.name}_Energy"] = lighting_out


class AHUControl:
    def __init__(self,
                 name,
                 building=None,
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
                 building=None,
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


class OtherEquipment:
    def __init__(self,
                 name,
                 building=None,
                 zones='*',
                 distribute_load=False,
                 cop=1,
                 design_level_power=None,
                 fraction_radiant=0.2,
                 compact_schedule_name=None,
                 series_schedule=None,
                 add_output_variables=False):
        self.name = name
        self.cop = cop
        self.building = building
        self.design_level_power = design_level_power
        self.add_output_variables = add_output_variables
        self.resources_idf = pr.get_resources_idf()
        self.distribute_load = distribute_load
        self.fraction_radiant = fraction_radiant

        if zones == '*':
            self.zones = self.building.zone_name_list
        else:
            self.zones = tl.format_input_to_list(zones)

        if series_schedule is None:
            if compact_schedule_name is None:
                self.schedule_name = "ON_24h24h_FULL_YEAR"

                # Get schedule in resources file
                schedule_to_copy = self.resources_idf.getobject(
                    "Schedule:Compact", self.schedule_name)

                # Copy in building idf if not already present
                idf_schedules = self.building.idf.idfobjects[
                    'Schedule:Compact']
                if schedule_to_copy.Name not in pr.get_objects_name_list(
                        self.building.idf, 'Schedule:Compact'):
                    idf_schedules.append(schedule_to_copy)

            elif not self.building.idf.getobject(
                    'Schedule:Compact', compact_schedule_name):
                raise ValueError(f"{compact_schedule_name} not found in"
                                 f"Schedule:Compact objects")
            else:
                self.schedule_name = compact_schedule_name
        else:
            if compact_schedule_name:
                raise ValueError("Both schedule name and series schedule "
                                 "can not be specified")

            if not isinstance(series_schedule, pd.Series):
                raise ValueError("series_schedule must be a Pandas Series")

            pr.del_obj_by_names(
                self.building.idf, "Schedule:File", series_schedule.name)

            pr.add_hourly_schedules_from_df(
                idf=building.idf, data=series_schedule)
            self.schedule_name = series_schedule.name

        self.pre_process()

    def pre_process(self):
        equipment_name_list = []
        if self.distribute_load:
            surf_arr = np.array([
                eppy.modeleditor.zonearea(self.building.idf, z)
                for z in self.zones])
            surf_ratio = surf_arr / np.sum(surf_arr)
        else:
            surf_ratio = np.array([1] * len(self.zones))

        for i, zone in enumerate(self.zones):
            equipment_name = f'{zone}_{self.name}_equipment'
            equipment_name_list.append(equipment_name)
            pr.del_obj_by_names(
                self.building.idf, "OtherEquipment", equipment_name)

            self.building.idf.newidfobject(
                "OtherEquipment",
                Name=equipment_name,
                Zone_or_ZoneList_Name=zone,
                Schedule_Name=self.schedule_name,
                Design_Level_Calculation_Method="EquipmentLevel",
                Design_Level=surf_ratio[
                                 i] * self.design_level_power * self.cop,
                Fraction_Radiant=self.fraction_radiant
            )

        if self.add_output_variables:
            pr.add_output_variable(
                self.building.idf,
                key_values=equipment_name_list,
                variables="Other Equipment Total Heating Energy"
            )

    def post_process(self):
        pass


class ZoneThermostat:
    def __init__(self,
                 name,
                 building,
                 zones,
                 heating_compact_schedule_name=None,
                 heating_series_schedule=None,
                 cooling_compact_schedule_name=None,
                 cooling_series_schedule=None,
                 add_schedules_output_variables=False,
                 ):

        self.name = name
        self.building = building
        self.zones = zones
        self.add_schedules_output_variables = add_schedules_output_variables
        self.resources_idf = pr.get_resources_idf()

        if zones == '*':
            self.zones = self.building.zone_name_list
        else:
            self.zones = tl.format_input_to_list(zones)

        if heating_series_schedule is None:
            if heating_compact_schedule_name is None:
                pr.copy_object_from_idf(
                    self.resources_idf, building.idf, 'Schedule:Compact',
                    '-60C_heating_setpoint')
                self.heating_schedule_name = '-60C_heating_setpoint'
            elif not self.building.idf.getobject(
                    'Schedule:Compact', heating_compact_schedule_name):
                raise ValueError(
                    f"{heating_compact_schedule_name} not found in"
                    f"Schedule:Compact objects")
            else:
                self.heating_schedule_name = heating_compact_schedule_name
        else:
            if heating_compact_schedule_name:
                raise ValueError("Both schedule name and series schedule "
                                 "can not be specified")
            if not isinstance(heating_series_schedule, pd.Series):
                raise ValueError("series_schedule must be a Pandas Series")

            pr.del_obj_by_names(
                self.building.idf, "Schedule:File",
                heating_series_schedule.name)
            pr.add_hourly_schedules_from_df(
                idf=building.idf, data=heating_series_schedule)
            self.heating_schedule_name = heating_series_schedule.name

        if cooling_series_schedule is None:
            if cooling_compact_schedule_name is None:
                pr.copy_object_from_idf(
                    self.resources_idf, building.idf, 'Schedule:Compact',
                    '100C_cooling_setpoint')
                self.cooling_schedule_name = "100C_cooling_setpoint"
            elif not self.building.idf.getobject(
                    'Schedule:Compact', cooling_compact_schedule_name):
                raise ValueError(
                    f"{cooling_compact_schedule_name} not found in"
                    f"Schedule:Compact objects")
            else:
                self.cooling_schedule_name = cooling_compact_schedule_name
        else:
            if cooling_compact_schedule_name:
                raise ValueError("Both schedule name and series schedule "
                                 "can not be specified")
            if not isinstance(cooling_series_schedule, pd.Series):
                raise ValueError("series_schedule must be a Pandas Series")

            pr.del_obj_by_names(
                self.building.idf, "Schedule:File",
                cooling_series_schedule.name)
            pr.add_hourly_schedules_from_df(
                idf=building.idf, data=cooling_series_schedule)
            self.cooling_schedule_name = cooling_series_schedule.name

    def pre_process(self):
        thermos_name_list = pr.get_objects_name_list(
            self.building.idf, "ThermostatSetpoint:DualSetpoint")

        thermos_to_keep = tl.select_by_strings(thermos_name_list, self.zones)

        pr.set_objects_field_values(
            idf=self.building.idf,
            idf_object="ThermostatSetpoint:DualSetpoint",
            field_name="Heating_Setpoint_Temperature_Schedule_Name",
            idf_object_names=thermos_to_keep,
            values=self.heating_schedule_name
        )

        pr.set_objects_field_values(
            idf=self.building.idf,
            idf_object="ThermostatSetpoint:DualSetpoint",
            field_name="Cooling_Setpoint_Temperature_Schedule_Name",
            idf_object_names=thermos_to_keep,
            values=self.cooling_schedule_name
        )

        if self.add_schedules_output_variables:
            pr.add_output_variable(
                self.building.idf,
                key_values=[self.heating_schedule_name,
                            self.cooling_schedule_name],
                variables="Schedule Value"
            )

    def post_process(self):
        pass
