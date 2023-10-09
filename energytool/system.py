import enum

import eppy.modeleditor
import numpy as np
import pandas as pd

from corrai.utils import as_1_column_dataframe

from energytool.base.idf_utils import (
    get_objects_name_list,
    set_named_objects_field_values,
    get_named_objects,
)

from energytool.base.idfobject_utils import (
    get_zones_idealloadsairsystem,
    add_output_variable,
    get_number_of_people,
    get_resources_idf,
    add_hourly_schedules_from_df,
    add_natural_ventilation,
)
import energytool.base.parse_results
from energytool.base.units import Units
from energytool.base.parse_results import get_output_variable
from energytool.tools import select_in_list

from eppy.modeleditor import IDF
from typing import Union

from abc import ABC, abstractmethod


class SystemCategories(enum.Enum):
    HEATING = "HEATING"
    COOLING = "COOLING"
    VENTILATION = "VENTILATION"
    LIGHTING = "LIGHTING"
    AUXILIARY = "AUXILIARY"
    DHW = "DHW"
    PV = "PV"
    OTHER = "OTHER"


class System(ABC):
    def __init__(self, name: str, category: SystemCategories = SystemCategories.OTHER):
        self.name = name
        self.category = category

    @abstractmethod
    def pre_process(self, idf: IDF):
        """Operations happening before the simulation"""
        pass

    @abstractmethod
    def post_process(self, idf: IDF = None, eplus_results: pd.DataFrame = None):
        """Operations happening after the simulation"""
        pass


class HeaterSimple(System):
    """
    Represent a simple heating system with a coefficient of performance COP.
    The class is based on IdealLoadsAirSytem. For each provided zones, it will get the
    "Zone Ideal Loads Supply Air Total Heating Energy" result and divide it by the cop.

    :parameter name(str): name of the system
    :parameter zone(str): idf zones controlled by the system. It must match zones in the idf file
    heated by the IdealLoadsAirSystem
    :parameter cop(float): Coefficient of Performance of the System. Can range from 0 to +infinity

    attribute : category(SystemCategories): SystemCategories.HEATING

    """

    def __init__(
        self,
        name: str,
        zones: Union[str, list] = "*",
        cop=1,
    ):
        super().__init__(name=name, category=SystemCategories.HEATING)
        self.cop = cop
        self.zones = zones
        self.ilas_list = []

    def pre_process(self, idf: IDF):
        self.ilas_list = get_zones_idealloadsairsystem(idf, self.zones)

        add_output_variable(
            idf=idf,
            key_values=[ilas.Name for ilas in self.ilas_list],
            variables="Zone Ideal Loads Supply Air Total Heating Energy",
        )

    def post_process(self, idf: IDF = None, eplus_results: pd.DataFrame = None):
        # Warning, works only if ilas name contains zone name
        ideal_heating = get_output_variable(
            eplus_res=eplus_results,
            key_values=[ilas.Name for ilas in self.ilas_list],
            variables="Zone Ideal Loads Supply Air Total Heating Energy",
        )

        system_out = (ideal_heating / self.cop).sum(axis=1)
        system_out.name = f"{self.name}_{Units.ENERGY.value}"
        return system_out.to_frame()


class HeatingAuxiliary(System):
    """
    A simple way to model heating system auxiliary consumption as a ratio of the total
    heating needs.
    The class is based on IdealLoadsAirSytem. For each provided zones, it will get the
    "Zone Ideal Loads Supply Air Total Heating Energy" result and multiply it by a ratio.

    :parameter name(str): name of the system
    :parameter zone(str): idf zones controlled by the system. It must match zones in the idf file
    heated by the IdealLoadsAirSystem
    :parameter ratio(float): The ratio of auxiliary consumption. Can range from 0 to +infinity

    attribute : category(SystemCategories): SystemCategories.AUXILIARY

    """

    def __init__(
        self,
        name: str,
        zones: Union[str, list] = "*",
        ratio=0.05,
    ):
        super().__init__(name=name, category=SystemCategories.AUXILIARY)
        self.ratio = ratio
        self.zones = zones
        self.ilas_list = []

    def pre_process(self, idf: IDF):
        self.ilas_list = get_zones_idealloadsairsystem(idf, self.zones)

        add_output_variable(
            idf=idf,
            key_values=[ilas.Name for ilas in self.ilas_list],
            variables="Zone Ideal Loads Supply Air Total Heating Energy",
        )

    def post_process(self, idf: IDF = None, eplus_results: pd.DataFrame = None):
        # Warning, works only if ilas name contains zone name
        ideal_heating = get_output_variable(
            eplus_res=eplus_results,
            key_values=[ilas.Name for ilas in self.ilas_list],
            variables="Zone Ideal Loads Supply Air Total Heating Energy",
        )

        system_out = (ideal_heating * self.ratio).sum(axis=1)
        system_out.name = f"{self.name}_{Units.ENERGY.value}"
        return system_out.to_frame()


class AirHandlingUnit(System):
    """
    A simple model for single flow and crossflow air handling units.
    This class is based on DesignSpecification:OutdoorAir objects and provides
    a convenient way to estimate fan energy consumption, set airflow using
    air changes per hour (ACH), and define heat recovery efficiency.

    Parameters:
        name (str): The name of the air handling unit.
        zones (str | List[str]): The name(s) of the zones served by the unit.
        fan_energy_coefficient (float): The fan energy coefficient in Wh/m3,
            used for fan energy consumption estimation.
        ach (float): The air change rate per hour in volume per hour (Vol/h).

    Notes:
    - If you use the "ach" argument, ensure that the DesignSpecification:OutdoorAir
      objects' names corresponding to the specified "zones" contain the zone names
      in their "Name" field.

    - Heat recovery efficiency settings will impact the latent and sensible
      efficiency of the heat exchanger between extracted and blown air.
    """

    def __init__(
        self,
        name: str,
        zones: Union[str, list] = "*",
        fan_energy_coefficient: float = 0.23,
        heat_recovery_efficiency: float = None,
        ach: float = None,
    ):
        super().__init__(name=name, category=SystemCategories.VENTILATION)
        self.zones = zones
        self.ach = ach
        self.fan_energy_coefficient = fan_energy_coefficient
        self.heat_recovery_efficiency = heat_recovery_efficiency

    def pre_process(self, idf: IDF):
        add_output_variable(
            idf=idf,
            key_values=self.zones,
            variables="Zone Mechanical Ventilation Standard Density Volume Flow Rate",
        )

        # Modify ACH if necessary
        if self.ach is not None:
            obj_name_arg = select_in_list(
                target_list=get_objects_name_list(
                    idf, "DesignSpecification:OutdoorAir"
                ),
                target=self.zones,
            )

            mod_fields = {
                "Outdoor_Air_Flow_Air_Changes_per_Hour": self.ach,
                "Outdoor_Air_Method": "AirChanges/Hour",
            }

            for field, value in mod_fields.items():
                energytool.base.idf_utils.set_named_objects_field_values(
                    idf=idf,
                    idf_object="DesignSpecification:OutdoorAir",
                    idf_object_names=obj_name_arg,
                    field_name=field,
                    values=value,
                )

        # Modify Heat Recovery if necessary
        if self.heat_recovery_efficiency is not None:
            obj_name_arg = select_in_list(
                target_list=get_objects_name_list(idf, "ZoneHVAC:IdealLoadsAirSystem"),
                target=self.zones,
            )

            mod_fields = {
                "Heat_Recovery_Type": "Sensible",
                "Sensible_Heat_Recovery_Effectiveness": self.heat_recovery_efficiency,
                "Latent_Heat_Recovery_Effectiveness": self.heat_recovery_efficiency,
            }
            for field, value in mod_fields.items():
                energytool.base.idf_utils.set_named_objects_field_values(
                    idf=idf,
                    idf_object="ZoneHVAC:IdealLoadsAirSystem",
                    idf_object_names=obj_name_arg,
                    field_name=field,
                    values=value,
                )

    def post_process(self, idf: IDF = None, eplus_results: pd.DataFrame = None):
        air_volume = get_output_variable(
            eplus_res=eplus_results,
            key_values=self.zones,
            variables="Zone Mechanical Ventilation Standard Density Volume Flow Rate",
        )

        # Air_volume [m3/s] * 3600 [s] * fan_coef [Wh/m3] * 3600 [J/Wh]
        system_out = (air_volume * 3600 * self.fan_energy_coefficient * 3600).sum(
            axis=1
        )

        system_out.name = f"{self.name}_{Units.ENERGY.value}"
        return system_out.to_frame()


class DHWIdealExternal(System):
    """
    A model for simulating an ideal domestic hot water (DHW) system .
    This class represents an idealized DHW system. It allows you to model DHW energy
    consumption based on various parameters and on the number of occupants present in the
    zone(s).

    Parameters:
        name (str): The name of the DHW system.
        zones (str | List[str]): The name(s) of the zones where the DHW system is
            located.
        cop (float): The coefficient of performance (COP) for the DHW system, indicating
            its efficiency.
        t_dwh_set_point (float): The setpoint temperature for domestic hot water
            in degrees Celsius.
        t_cold_water (float): The temperature of the cold water supply in
            degrees Celsius.
        daily_volume_occupant (float): The daily volume of hot water consumed per
            occupant in liters.
        cp_water (float): The specific heat capacity of water in J/L·°C.

    Methods:
        pre_process(idf: IDF): pass.
        post_process(idf: IDF = None, eplus_results: pd.DataFrame = None) -> pd.DataFrame:
        Calculates DHW energy consumption and returns the results as a DataFrame.
    """

    def __init__(
        self,
        name: str,
        zones: Union[str, list] = "*",
        cop: float = 0.95,
        t_dwh_set_point: float = 60.0,
        t_cold_water: float = 15.0,
        daily_volume_occupant: float = 50.0,
        cp_water: float = 4183.2,
    ):
        super().__init__(name, category=SystemCategories.DHW)
        self.name = name
        self.zones = zones
        self.cop = cop
        self.t_dwh_set_point = t_dwh_set_point
        self.t_cold_water = t_cold_water
        self.daily_volume_occupant = daily_volume_occupant
        self.cp_water = cp_water

    def pre_process(self, idf: IDF):
        pass

    def post_process(self, idf: IDF = None, eplus_results: pd.DataFrame = None):
        nb_people = get_number_of_people(idf, zones=self.zones)

        # 4183.2[J/L.°C]
        daily_cons_per_occupant = (
            self.cp_water
            * (self.t_dwh_set_point - self.t_cold_water)
            * self.daily_volume_occupant
        )

        nb_days = eplus_results.resample("D").sum().shape[0]
        nb_entry = eplus_results.shape[0]

        dhw_consumption = daily_cons_per_occupant * nb_days * nb_people / self.cop

        return pd.DataFrame(
            {
                f"{self.name}_{Units.ENERGY.value}": (
                    np.ones(nb_entry) * dhw_consumption / nb_entry
                )
            },
            index=eplus_results.index,
        )


class ArtificialLighting(System):
    """
    A model for simulating artificial lighting systems energy consumption.

    Parameters:
        name (str): The name of the lighting system.
        zones (str | List[str]): The name(s) of the zones where the lighting system is
            present.
        power_ratio (float): The lighting power density in watts per square meter (W/m²).
        cop (float): The coefficient of performance (COP) for lighting system energy
            consumption (default is 1).

    Methods:
        pre_process(idf: IDF): Pre-processes the EnergyPlus IDF file to set
            lighting-related configurations.
        post_process(idf: IDF = None, eplus_results: pd.DataFrame = None) -> pd.DataFrame:
            Calculates lighting energy consumption and returns the results as a DataFrame.
    """

    def __init__(
        self,
        name: str,
        zones: Union[str, list] = "*",
        power_ratio: float = 3.0,
        cop: float = 1,
    ):  # W/m²
        super().__init__(name, category=SystemCategories.LIGHTING)
        self.name = name
        self.zones = zones
        self.power_ratio = power_ratio
        self.cop = cop

    def pre_process(self, idf: IDF):
        add_output_variable(
            idf=idf,
            key_values=self.zones,
            variables="Zone Lights Electricity Energy",
        )

        config = {
            "Design_Level_Calculation_Method": "Watts/Area",
            "Watts_per_Zone_Floor_Area": self.power_ratio,
        }
        obj_name_arg = select_in_list(
            target_list=get_objects_name_list(idf, "Lights"),
            target=self.zones,
        )

        for field, value in config.items():
            set_named_objects_field_values(
                idf=idf,
                idf_object="Lights",
                idf_object_names=obj_name_arg,
                field_name=field,
                values=value,
            )

    def post_process(self, idf: IDF = None, eplus_results: pd.DataFrame = None):
        lighting_consumption = get_output_variable(
            eplus_res=eplus_results,
            key_values=self.zones,
            variables="Zone Lights Electricity Energy",
        )

        lighting_out = (lighting_consumption / self.cop).sum(axis=1)
        lighting_out.name = f"{self.name}_{Units.ENERGY.value}"
        return lighting_out.to_frame()


class AHUControl(System):
    """
    Represents an Air Handling Unit (AHU) control system for building energy modeling.
    This class is designed to model the control of an AHU system within a building
    energy model. It provides options for controlling the AHU based on either a
    predefined schedule or user-supplied data in the form of a Pandas DataFrame or
    Series.

    :param name: The name of the AHU control system.
    :param zones: The zones or spaces associated with the AHU control
        (default is "*," indicating all zones).
    :param control_strategy: The control strategy for the AHU, either "Schedule" or
        "DataFrame" (default is "Schedule").
    :param schedule_name: The name of the predefined schedule to use if the control
        strategy is "Schedule" (default is "ON_24h24h_FULL_YEAR").
    :param data_frame: A Pandas DataFrame or Series containing user-defined control data
        (used when control_strategy is "DataFrame"). Default is None.

    :raises ValueError: If an invalid control strategy is specified.
    """

    def __init__(
        self,
        name: str,
        zones: Union[str, list] = "*",
        control_strategy: str = "Schedule",
        schedule_name: str = "ON_24h24h_FULL_YEAR",
        data_frame: Union[pd.DataFrame, pd.Series] = None,
    ):
        super().__init__(name, category=SystemCategories.VENTILATION)
        self.name = name
        self.zones = zones
        self.control_strategy = control_strategy
        self.schedule_name = schedule_name
        self.resources_idf = get_resources_idf()
        if data_frame is not None:
            self.data_frame = as_1_column_dataframe(data_frame)

    def pre_process(self, idf: IDF):
        if self.control_strategy == "Schedule":
            # Get schedule in resources file
            idf_schedules = idf.idfobjects["Schedule:Compact"]
            schedule_to_copy = get_named_objects(
                self.resources_idf, "Schedule:Compact", self.schedule_name
            )

            # Copy in building idf if not already present
            if schedule_to_copy[0].Name not in get_objects_name_list(
                idf, "Schedule:Compact"
            ):
                idf_schedules.append(schedule_to_copy[0])

            schedule_name = schedule_to_copy[0].Name

        elif self.control_strategy == "DataFrame":
            add_hourly_schedules_from_df(idf, self.data_frame)
            schedule_name = self.data_frame.columns[0]

        else:
            raise ValueError("Specify valid control_strategy")

        # Get Design spec object to modify and set schedule
        obj_name_arg = select_in_list(
            target_list=get_objects_name_list(idf, "DesignSpecification:OutdoorAir"),
            target=self.zones,
        )

        set_named_objects_field_values(
            idf=idf,
            idf_object="DesignSpecification:OutdoorAir",
            idf_object_names=obj_name_arg,
            field_name="Outdoor_Air_Schedule_Name",
            values=schedule_name,
        )

    def post_process(self, idf: IDF = None, eplus_results: pd.DataFrame = None):
        pass


class NaturalVentilation(System):
    def __init__(
        self,
        name: str,
        zones: Union[str, list] = "*",
        ach=0.7,
        occupancy_schedule=True,
        ventilation_kwargs=None,
    ):
        super().__init__(name=name, category=SystemCategories.VENTILATION)
        self.name = name
        self.zones = zones
        self.ach = ach
        self.occupancy_schedule = occupancy_schedule
        self.ventilation_kwargs = ventilation_kwargs

    def pre_process(self, idf: IDF):
        add_natural_ventilation(
            idf,
            ach=self.ach,
            zones=self.zones,
            occupancy_schedule=self.occupancy_schedule,
            kwargs=self.ventilation_kwargs,
        )

    def post_process(self, idf: IDF = None, eplus_results: pd.DataFrame = None):
        pass


class OtherEquipment:
    def __init__(
        self,
        name,
        building=None,
        zones="*",
        distribute_load=False,
        cop=1,
        design_level_power=None,
        fraction_radiant=0.2,
        compact_schedule_name=None,
        series_schedule=None,
        add_output_variables=False,
    ):
        self.name = name
        self.cop = cop
        self.building = building
        self.design_level_power = design_level_power
        self.add_output_variables = add_output_variables
        self.resources_idf = energytool.base.epluspreprocess.get_resources_idf()
        self.distribute_load = distribute_load
        self.fraction_radiant = fraction_radiant

        if zones == "*":
            self.zones = self.building.zone_name_list
        else:
            self.zones = tl.to_list(zones)

        if series_schedule is None:
            if compact_schedule_name is None:
                self.schedule_name = "ON_24h24h_FULL_YEAR"

                # Get schedule in resources file
                schedule_to_copy = self.resources_idf.getobject(
                    "Schedule:Compact", self.schedule_name
                )

                # Copy in building idf if not already present
                idf_schedules = self.building.idf.idfobjects["Schedule:Compact"]
                if (
                    schedule_to_copy.Name
                    not in energytool.base.idf_utils.get_objects_name_list(
                        self.building.idf, "Schedule:Compact"
                    )
                ):
                    idf_schedules.append(schedule_to_copy)

            elif not self.building.idf.getobject(
                "Schedule:Compact", compact_schedule_name
            ):
                raise ValueError(
                    f"{compact_schedule_name} not found in" f"Schedule:Compact objects"
                )
            else:
                self.schedule_name = compact_schedule_name
        else:
            if compact_schedule_name:
                raise ValueError(
                    "Both schedule name and series schedule " "can not be specified"
                )

            if not isinstance(series_schedule, pd.Series):
                raise ValueError("series_schedule must be a Pandas Series")

            energytool.base.idf_utils.del_named_objects(
                self.building.idf, "Schedule:File", series_schedule.name
            )

            pr.add_hourly_schedules_from_df(idf=building.idf, data=series_schedule)
            self.schedule_name = series_schedule.name

        self.pre_process()

    def pre_process(self):
        equipment_name_list = []
        if self.distribute_load:
            surf_arr = np.array(
                [eppy.modeleditor.zonearea(self.building.idf, z) for z in self.zones]
            )
            surf_ratio = surf_arr / np.sum(surf_arr)
        else:
            surf_ratio = np.array([1] * len(self.zones))

        for i, zone in enumerate(self.zones):
            equipment_name = f"{zone}_{self.name}_equipment"
            equipment_name_list.append(equipment_name)
            energytool.base.idf_utils.del_named_objects(
                self.building.idf, "OtherEquipment", equipment_name
            )

            self.building.idf.newidfobject(
                "OtherEquipment",
                Name=equipment_name,
                Zone_or_ZoneList_Name=zone,
                Schedule_Name=self.schedule_name,
                Design_Level_Calculation_Method="EquipmentLevel",
                Design_Level=surf_ratio[i] * self.design_level_power * self.cop,
                Fraction_Radiant=self.fraction_radiant,
            )

        if self.add_output_variables:
            pr.add_output_variable(
                self.building.idf,
                key_values=equipment_name_list,
                variables="Other Equipment Total Heating Energy",
            )

    def post_process(self):
        pass


class ZoneThermostat:
    def __init__(
        self,
        name,
        building,
        zones,
        heating_compact_schedule_name=None,
        heating_series_schedule=None,
        cooling_compact_schedule_name=None,
        cooling_series_schedule=None,
        add_schedules_output_variables=False,
        overwrite_heating_availability=False,
        overwrite_cooling_availability=False,
    ):
        self.name = name
        self.building = building
        self.zones = zones
        self.add_schedules_output_variables = add_schedules_output_variables
        self.resources_idf = energytool.base.epluspreprocess.get_resources_idf()
        self.overwrite_heating_availability = overwrite_heating_availability
        self.overwrite_cooling_availability = overwrite_cooling_availability

        if zones == "*":
            self.zones = self.building.zone_name_list
        else:
            self.zones = tl.to_list(zones)

        self.ilas_list = pr.get_zones_idealloadsairsystem(building.idf, self.zones)

        if heating_series_schedule is None:
            if heating_compact_schedule_name is None:
                energytool.base.idf_utils.copy_named_object_from_idf(
                    self.resources_idf,
                    building.idf,
                    "Schedule:Compact",
                    "-60C_heating_setpoint",
                )
                self.heating_schedule_name = "-60C_heating_setpoint"
            elif not self.building.idf.getobject(
                "Schedule:Compact", heating_compact_schedule_name
            ):
                raise ValueError(
                    f"{heating_compact_schedule_name} not found in"
                    f"Schedule:Compact objects"
                )
            else:
                self.heating_schedule_name = heating_compact_schedule_name
        else:
            if heating_compact_schedule_name:
                raise ValueError(
                    "Both schedule name and series schedule " "can not be specified"
                )
            if not isinstance(heating_series_schedule, pd.Series):
                raise ValueError("series_schedule must be a Pandas Series")

            energytool.base.idf_utils.del_named_objects(
                self.building.idf, "Schedule:File", heating_series_schedule.name
            )
            pr.add_hourly_schedules_from_df(
                idf=building.idf, data=heating_series_schedule
            )
            self.heating_schedule_name = heating_series_schedule.name

        if cooling_series_schedule is None:
            if cooling_compact_schedule_name is None:
                energytool.base.idf_utils.copy_named_object_from_idf(
                    self.resources_idf,
                    building.idf,
                    "Schedule:Compact",
                    "100C_cooling_setpoint",
                )
                self.cooling_schedule_name = "100C_cooling_setpoint"
            elif not self.building.idf.getobject(
                "Schedule:Compact", cooling_compact_schedule_name
            ):
                raise ValueError(
                    f"{cooling_compact_schedule_name} not found in"
                    f"Schedule:Compact objects"
                )
            else:
                self.cooling_schedule_name = cooling_compact_schedule_name
        else:
            if cooling_compact_schedule_name:
                raise ValueError(
                    "Both schedule name and series schedule " "can not be specified"
                )
            if not isinstance(cooling_series_schedule, pd.Series):
                raise ValueError("series_schedule must be a Pandas Series")

            energytool.base.idf_utils.del_named_objects(
                self.building.idf, "Schedule:File", cooling_series_schedule.name
            )
            pr.add_hourly_schedules_from_df(
                idf=building.idf, data=cooling_series_schedule
            )
            self.cooling_schedule_name = cooling_series_schedule.name

    def pre_process(self):
        if self.overwrite_heating_availability or self.overwrite_cooling_availability:
            energytool.base.idf_utils.copy_named_object_from_idf(
                self.resources_idf,
                self.building.idf,
                "Schedule:Compact",
                "ON_24h24h_FULL_YEAR",
            )

        if self.overwrite_heating_availability:
            energytool.base.idf_utils.set_named_objects_field_values(
                idf=self.building.idf,
                idf_object="ZONEHVAC:IDEALLOADSAIRSYSTEM",
                field_name="Heating_Availability_Schedule_Name",
                idf_object_names=[ilas.Name for ilas in self.ilas_list],
                values="ON_24h24h_FULL_YEAR",
            )

        if self.overwrite_cooling_availability:
            energytool.base.idf_utils.set_named_objects_field_values(
                idf=self.building.idf,
                idf_object="ZONEHVAC:IDEALLOADSAIRSYSTEM",
                field_name="Cooling_Availability_Schedule_Name",
                idf_object_names=[ilas.Name for ilas in self.ilas_list],
                values="ON_24h24h_FULL_YEAR",
            )

        thermos_name_list = energytool.base.idf_utils.get_objects_name_list(
            self.building.idf, "ThermostatSetpoint:DualSetpoint"
        )

        thermos_to_keep = tl.select_in_list(thermos_name_list, self.zones)

        energytool.base.idf_utils.set_named_objects_field_values(
            idf=self.building.idf,
            idf_object="ThermostatSetpoint:DualSetpoint",
            field_name="Heating_Setpoint_Temperature_Schedule_Name",
            idf_object_names=thermos_to_keep,
            values=self.heating_schedule_name,
        )

        energytool.base.idf_utils.set_named_objects_field_values(
            idf=self.building.idf,
            idf_object="ThermostatSetpoint:DualSetpoint",
            field_name="Cooling_Setpoint_Temperature_Schedule_Name",
            idf_object_names=thermos_to_keep,
            values=self.cooling_schedule_name,
        )

        if self.add_schedules_output_variables:
            pr.add_output_variable(
                self.building.idf,
                key_values=[self.heating_schedule_name, self.cooling_schedule_name],
                variables="Schedule Value",
            )

    def post_process(self):
        pass
