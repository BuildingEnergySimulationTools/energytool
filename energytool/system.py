import enum
import json

from abc import ABC, abstractmethod
from pathlib import Path

import eppy.modeleditor
import numpy as np
import pandas as pd
from eppy.modeleditor import IDF

import energytool.base.parse_results
from energytool.base.idf_utils import (
    get_objects_name_list,
    set_named_objects_field_values,
    del_named_objects,
)
from energytool.base.idfobject_utils import (
    get_zones_idealloadsairsystem,
    add_output_variable,
    get_number_of_people,
    add_hourly_schedules_from_df,
    add_natural_ventilation,
    add_obj_from_obj_dict,
)
from energytool.base.parse_results import get_output_variable
from energytool.base.units import Units
from energytool.tools import select_in_list, to_list

resource_path = Path(__file__).parent / "resources/resources.json"
with resource_path.open("r", encoding="utf-8") as f:
    RESOURCE_JSON = json.load(f)


class SystemCategories(enum.Enum):
    HEATING = "HEATING"
    COOLING = "COOLING"
    VENTILATION = "VENTILATION"
    LIGHTING = "LIGHTING"
    AUXILIARY = "AUXILIARY"
    DHW = "DHW"
    PV = "PV"
    SENSOR = "SENSOR"
    OTHER = "OTHER"


class System(ABC):
    def __init__(self, name: str, category: SystemCategories = SystemCategories.OTHER):
        self.name = name
        self.category = category

    def __repr__(self):
        return f"{self.name}"

    @abstractmethod
    def pre_process(self, idf: IDF):
        """Operations happening before the simulation"""
        pass

    @abstractmethod
    def post_process(self, idf: IDF = None, eplus_results: pd.DataFrame = None):
        """Operations happening after the simulation"""
        pass


class Overshoot28(System):
    """
    Represents the thermal discomfort system for zones exceeding a temperature threshold.

    :param name: Name of the system.
    :param zones: Zones or spaces to monitor. Can be "*" for all zones or a list of zones.
    :param temp_threshold: Temperature threshold for thermal discomfort.
    :param occupancy_in_output: Set to True for Zone People Occupant Count in output df.
    """

    def __init__(
        self,
        name: str,
        zones: str | list = "*",
        temp_threshold: float = 28.0,
        occupancy_in_output=False,
    ):
        super().__init__(name=name, category=SystemCategories.SENSOR)
        self.zones = zones
        self.temp_threshold = temp_threshold
        self.occupancy_in_output = occupancy_in_output

    def pre_process(self, idf: IDF):
        """
        Adds the necessary output variables to monitor operative temperature and occupancy.
        """
        # Add output variable for Zone Operative Temperature
        add_output_variable(
            idf=idf,
            key_values=self.zones,
            variables="Zone Operative Temperature",
        )

        # Add output variable for Zone People Occupant Count
        add_output_variable(
            idf=idf,
            key_values=self.zones,
            variables="Zone People Occupant Count",
        )

    def post_process(self, idf: IDF = None, eplus_results: pd.DataFrame = None):
        """
        Calculates thermal discomfort based on operative temperature and occupancy.

        :param idf: The EnergyPlus input data (not used in this method).
        :param eplus_results: DataFrame containing EnergyPlus simulation results.
        :return: DataFrame with additional columns for thermal discomfort.
        """
        operative_temperature = get_output_variable(
            eplus_res=eplus_results,
            key_values=self.zones,
            variables="Zone Operative Temperature",
        )

        occupancy = get_output_variable(
            eplus_res=eplus_results,
            key_values=self.zones,
            variables="Zone People Occupant Count",
        )

        results = pd.DataFrame(index=operative_temperature.index)

        for col in operative_temperature.columns:
            results[f"discomfort_{col}"] = (
                (operative_temperature[col] >= self.temp_threshold)
                & (occupancy[col] > 0)
            ).astype(int)
            if self.occupancy_in_output:
                results[f"occupancy_{col}"] = occupancy[col]

        return results


class LightAutonomy(System):
    """
    Represents a system to calculate lighting autonomy per zone.

    :param name: Name of the system.
    :param zones: Zones or spaces to monitor. Can be "*" for all zones or a list of zones.
    :param lux_threshold: Minimum lux level required for lighting autonomy.
    :param light_schedule_name: Name of the light schedule to retrieve from "Schedule Value".
    :param occupancy_in_output: Set to True for Zone People Occupant Count in output df.
    """

    def __init__(
        self,
        name: str,
        zones: str | list = "*",
        lux_threshold: float = 200,
        light_schedule_name: str = None,
        occupancy_in_output=False,
    ):
        super().__init__(name=name, category=SystemCategories.SENSOR)
        self.zones = zones
        self.lux_threshold = lux_threshold
        self.light_schedule_name = light_schedule_name
        self.occupancy_in_output = occupancy_in_output

    def pre_process(self, idf: IDF):
        """
        Adds the necessary output variables for illuminance, occupancy, and light schedule.

        :param idf: The EnergyPlus input data.
        """
        # Add output variable for Daylighting Reference Point Illuminance

        # Add output variable for the specified light schedule
        add_output_variable(
            idf=idf,
            key_values=self.light_schedule_name,
            variables="Schedule Value",
        )

        add_output_variable(
            idf=idf,
            key_values=self.zones,
            variables="Daylighting Reference Point 1 Illuminance",
        )

        # Add output variable for Zone People Occupant Count
        add_output_variable(
            idf=idf,
            key_values=self.zones,
            variables="Zone People Occupant Count",
        )

    def post_process(self, idf: IDF = None, eplus_results: pd.DataFrame = None):
        """
        Calculates lighting autonomy based on illuminance, occupancy, and schedule.

        :param idf: The EnergyPlus input data (not used in this method).
        :param eplus_results: DataFrame containing EnergyPlus simulation results.
        :return: DataFrame with additional columns for lighting autonomy per zone.
        """
        schedule = get_output_variable(
            eplus_res=eplus_results,
            key_values=self.light_schedule_name,
            variables="Schedule Value",
        )

        # Get the occupancy data
        occupancy = get_output_variable(
            eplus_res=eplus_results,
            key_values=self.zones,
            variables="Zone People Occupant Count",
        )

        # Get the illuminance data
        illuminance = get_output_variable(
            eplus_res=eplus_results,
            key_values=self.zones,
            variables="Daylighting Reference Point 1 Illuminance",
        )

        # Calculate lighting autonomy for each zone
        is_occupied = occupancy > 0
        is_schedule_active = schedule > 0

        results = pd.DataFrame(index=illuminance.index)
        for col in illuminance.columns:
            results[f"autonomy_{col}"] = (
                (illuminance[col] >= self.lux_threshold)
                & is_occupied[col]
                & is_schedule_active.squeeze()
            ).astype(int)
            if self.occupancy_in_output:
                results[f"occupancy_{col}"] = occupancy[col]

        return results


class Sensor(System):
    """
    Add output:variables to the idf, get the results in post process.
    :param name(str): Name of the sensor
    :param variables: The names of the variables to output.
    :param key_values: The key values for which to add output variables.
        This can be a single key value (string) or a list of key values
        (list of strings). Default is '*' meaning all the available variables.
    """

    def __init__(self, name: str, variables: str, key_values: str | list[str] = "*"):
        super().__init__(name=name, category=SystemCategories.SENSOR)
        self.variables = variables
        self.key_values = key_values

    def pre_process(self, idf: IDF):
        add_output_variable(
            idf=idf,
            key_values=self.key_values,
            variables=self.variables,
        )

    def post_process(self, idf: IDF = None, eplus_results: pd.DataFrame = None):
        results = get_output_variable(
            eplus_res=eplus_results,
            key_values=self.key_values,
            variables=self.variables,
        )
        results.columns = results.columns + f"_{self.variables}"
        return results


class SimplifiedChiller(System):
    """
    Represent a simplified chilling system with a coefficient of performance COP.
    The class is based on IdealLoadsAirSytem. For each provided zones, it will get the
    "Zone Ideal Loads Supply Air Total Cooling Energy" result and divide it by the cop.

    :parameter name(str): name of the system
    :parameter zone(str): idf zones controlled by the system. It must match zones in
        the idf file
    heated by the IdealLoadsAirSystem
    :parameter cop(float): Coefficient of Performance of the System. Can range from 0
        to +infinity

    attribute : category(SystemCategories): SystemCategories.COOLING

    """

    def __init__(
        self,
        name: str,
        zones: str | list = "*",
        cop=2.5,
    ):
        super().__init__(name=name, category=SystemCategories.COOLING)
        self.cop = cop
        self.zones = zones
        self.ilas_list = []

    def pre_process(self, idf: IDF):
        self.ilas_list = get_zones_idealloadsairsystem(idf, self.zones)

        add_output_variable(
            idf=idf,
            key_values=[ilas.Name for ilas in self.ilas_list],
            variables="Zone Ideal Loads Supply Air Total Cooling Energy",
        )

    def post_process(self, idf: IDF = None, eplus_results: pd.DataFrame = None):
        # Warning, works only if ilas name contains zone name
        ideal_cooling = get_output_variable(
            eplus_res=eplus_results,
            key_values=[ilas.Name for ilas in self.ilas_list],
            variables="Zone Ideal Loads Supply Air Total Cooling Energy",
        )

        system_out = (ideal_cooling / self.cop).sum(axis=1)
        system_out.name = f"{self.name}_{Units.ENERGY.value}"
        return system_out.to_frame()


class HeaterSimple(System):
    """
    Represent a simple heating system with a coefficient of performance COP.
    The class is based on IdealLoadsAirSytem. For each provided zones, it will get the
    "Zone Ideal Loads Supply Air Total Heating Energy" result and divide it by the cop.

    :parameter name(str): name of the system
    :parameter zone(str): idf zones controlled by the system. It must match zones in
        the idf file
    heated by the IdealLoadsAirSystem
    :parameter cop(float): Coefficient of Performance of the System. Can range from 0
        to +infinity

    attribute : category(SystemCategories): SystemCategories.HEATING

    """

    def __init__(
        self,
        name: str,
        zones: str | list = "*",
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
    "Zone Ideal Loads Supply Air Total Heating Energy" result and multiply it by a
     ratio.

    :parameter name(str): name of the system
    :parameter zone(str): idf zones controlled by the system. It must match zones in
        the idf file
    heated by the IdealLoadsAirSystem
    :parameter ratio(float): The ratio of auxiliary consumption. Can range from 0 to
        +infinity

    attribute : category(SystemCategories): SystemCategories.AUXILIARY

    """

    def __init__(
        self,
        name: str,
        zones: str | list = "*",
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
        zones: str | list = "*",
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
    consumption based on various parameters and on the number of occupants present in
    the zone(s).

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
        post_process(idf: IDF = None, eplus_results: pd.DataFrame = None)
            -> pd.DataFrame:
        Calculates DHW energy consumption and returns the results as a DataFrame.
    """

    def __init__(
        self,
        name: str,
        zones: str | list = "*",
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
        power_ratio (float): The lighting power density in watts per square meter
            (W/m²).
        cop (float): The coefficient of performance (COP) for lighting system energy
            consumption (default is 1).

    Methods:
        pre_process(idf: IDF): Pre-processes the EnergyPlus IDF file to set
            lighting-related configurations.
        post_process(idf: IDF = None, eplus_results: pd.DataFrame = None)
            -> pd.DataFrame:
            Calculates lighting energy consumption and returns the results as a
            DataFrame.
    """

    def __init__(
        self,
        name: str,
        zones: str | list = "*",
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
    :param time_series: A Pandas DataFrame or Series containing user-defined control
        data (used when control_strategy is "DataFrame"). Default is None.

    :raises ValueError: If an invalid control strategy is specified.
    """

    def __init__(
        self,
        name: str,
        zones: str | list = "*",
        control_strategy: str = "Schedule",
        schedule_name: str = "ON_24h24h_FULL_YEAR",
        time_series: pd.DataFrame | pd.Series = None,
    ):
        super().__init__(name, category=SystemCategories.VENTILATION)
        self.name = name
        self.zones = zones
        self.control_strategy = control_strategy
        self.schedule_name = schedule_name
        if time_series is not None:
            self.data_frame = time_series.to_frame()

    def pre_process(self, idf: IDF):
        if self.control_strategy == "Schedule":
            try:
                add_obj_from_obj_dict(
                    idf, RESOURCE_JSON, "Schedule:Compact".upper(), self.schedule_name
                )
            except ValueError:
                pass

        elif self.control_strategy == "DataFrame":
            add_hourly_schedules_from_df(idf, self.data_frame)
            self.schedule_name = self.data_frame.columns[0]

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
            values=self.schedule_name,
        )

    def post_process(self, idf: IDF = None, eplus_results: pd.DataFrame = None):
        pass


class NaturalVentilation(System):
    def __init__(
        self,
        name: str,
        zones: str | list = "*",
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


class OtherEquipment(System):
    def __init__(
        self,
        name,
        zones: str | list = "*",
        distribute_load: bool = False,
        cop: float = 1.0,
        design_level_power: float = None,
        fraction_radiant: float = 0.2,
        compact_schedule_name: str = None,
        time_series: pd.Series = None,
        add_output_variables: bool = False,
    ):
        """
        This class is designed to model loads or heat source using other equipment
        systems within a building energy model. It provides options for specifying
        equipment parameters, distribution across zones, and scheduling methods.

        :param name: The name of the other equipment system.
        :param zones: The zones or spaces where the other equipment is located
            (default is "*," indicating all zones).
        :param distribute_load: If True, the equipment load is distributed based on
            zone areas. If False, the load is evenly distributed across specified zones
            (default is False).
        :param cop: The Coefficient of Performance (COP) for the equipment
            (default is 1.0). (eg. To model HP heating from compressor energy
            measurements)
        :param design_level_power: The design-level power of the equipment
            (if None, a predefined schedule is used for power levels).
        :param fraction_radiant: The fraction of radiant energy emitted by the
            equipment (default is 0.2).
        :param compact_schedule_name: The name of a predefined compact schedule to use
            for equipment operation (if None, a default schedule is used).
        :param time_series: A Pandas Series containing time-series data for equipment
            operation (if provided, it takes precedence over the compact_schedule_name).
        :param add_output_variables: If True, output variables for equipment heating
            energy are added to the EnergyPlus IDF (default is False).
        """
        super().__init__(name=name, category=SystemCategories.OTHER)
        self.cop = cop
        self.design_level_power = design_level_power
        self.add_output_variables = add_output_variables
        self.distribute_load = distribute_load
        self.fraction_radiant = fraction_radiant
        if time_series is not None:
            self.time_series = time_series.to_frame()
        else:
            self.time_series = None
        self.compact_schedule_name = compact_schedule_name
        self.schedule_name = None
        self.zones = zones

    def pre_process(self, idf: IDF):
        if self.zones == "*":
            self.zones = get_objects_name_list(idf, "Zone")
        else:
            self.zones = to_list(self.zones)

        # No time series was passed
        if self.time_series is None:
            # No compact schedule name is provided
            if self.compact_schedule_name is None:
                self.schedule_name = "ON_24h24h_FULL_YEAR"
                try:
                    add_obj_from_obj_dict(
                        idf,
                        RESOURCE_JSON,
                        "Schedule:Compact".upper(),
                        self.schedule_name,
                    )
                except ValueError:
                    pass

            # Compact schedule name is provided, but it can't be found
            elif not idf.getobject("Schedule:Compact", self.compact_schedule_name):
                raise ValueError(
                    f"{self.compact_schedule_name} not found inSchedule:Compact objects"
                )
            # Correct name has been given
            else:
                self.schedule_name = self.compact_schedule_name
        # Ime series was passed
        else:
            if self.compact_schedule_name:
                raise ValueError(
                    "Both compact_schedule_name and time_series were specified"
                )

            del_named_objects(idf, "Schedule:File", self.time_series.columns[0])
            add_hourly_schedules_from_df(idf=idf, data=self.time_series)
            self.schedule_name = self.time_series.columns[0]

        equipment_name_list = []
        if self.distribute_load:
            surf_arr = np.array([eppy.modeleditor.zonearea(idf, z) for z in self.zones])
            surf_ratio = surf_arr / np.sum(surf_arr)
        else:
            surf_ratio = np.array([1] * len(self.zones))

        for i, zone in enumerate(self.zones):
            equipment_name = f"{zone}_{self.name}_equipment"
            del_named_objects(idf, "OtherEquipment", equipment_name)
            equipment_name_list.append(equipment_name)

            idf.newidfobject(
                "OtherEquipment",
                Name=equipment_name,
                Zone_or_ZoneList_Name=zone,
                Schedule_Name=self.schedule_name,
                Design_Level_Calculation_Method="EquipmentLevel",
                Design_Level=surf_ratio[i] * self.design_level_power * self.cop,
                Fraction_Radiant=self.fraction_radiant,
            )

        if self.add_output_variables:
            add_output_variable(
                idf,
                key_values=equipment_name_list,
                variables="Other Equipment Total Heating Energy",
            )

    def post_process(self, idf: IDF = None, eplus_results: pd.DataFrame = None):
        pass


class ZoneThermostat(System):
    def __init__(
        self,
        name: str,
        zones: str | list = "*",
        heating_compact_schedule_name: str = None,
        heating_time_series: pd.Series = None,
        cooling_compact_schedule_name: str = None,
        cooling_time_series: pd.Series = None,
        add_schedules_output_variables: bool = False,
        overwrite_heating_availability: bool = False,
        overwrite_cooling_availability: bool = False,
    ):
        """
        The ZoneThermostat class is designed to simplify the process of managing
        thermostat settings and schedule. It allows users to define thermostat
        configurations for specific zones or all zones in a building specifying
        compact schedule, or using Pandas Series.

        :param name: Name of the ZoneThermostat.
        :param zones: Zones to apply the thermostat settings to. "*" for all zones or
           a list of zone names.
        :param heating_compact_schedule_name: Name of the heating compact schedule.
           If not provided, and no time_series is given. The heating is artificially
            set to Off using a constant -60°C schedule.

        :param heating_time_series: Heating time series data as a pandas Series.
           If provided, this time series will be used for heating setpoint schedules,
            and any provided heating_compact_schedule_name will be ignored.

        :param cooling_compact_schedule_name: Name of the cooling compact schedule.
           If not provided, and no time_series is given. The cooling is artificially
            set to Off using a constant 100°C schedule.

        :param cooling_time_series: Cooling time series data as a pandas Series.
           If provided, this time series will be used for cooling setpoint schedules,
           and any provided cooling_compact_schedule_name will be ignored.

        :param add_schedules_output_variables: Whether to add schedules as output
           variables in the idf. This can be useful for analysis and
           visualization.

        :param overwrite_heating_availability: Whether to overwrite heating
           availability schedules for the specified zones.

        :param overwrite_cooling_availability: Whether to overwrite cooling availability
            schedules for the specified zones.
        """
        super().__init__(name=name, category=SystemCategories.OTHER)
        self.zones = zones
        self.add_schedules_output_variables = add_schedules_output_variables
        self.overwrite_heating_availability = overwrite_heating_availability
        self.overwrite_cooling_availability = overwrite_cooling_availability
        self.heating_compact_schedule_name = heating_compact_schedule_name
        self.heating_time_series = heating_time_series
        self.cooling_compact_schedule_name = cooling_compact_schedule_name
        self.cooling_time_series = cooling_time_series
        self.heating_schedule_name = None
        self.cooling_schedule_name = None

    def pre_process(self, idf: IDF):
        if self.zones == "*":
            self.zones = get_objects_name_list(idf, "Zone")
        else:
            self.zones = to_list(self.zones)

        ilas_list = get_zones_idealloadsairsystem(idf, self.zones)

        if self.heating_time_series is None:
            if self.heating_compact_schedule_name is None:
                self.heating_schedule_name = "-60C_heating_setpoint"
                try:
                    add_obj_from_obj_dict(
                        idf,
                        RESOURCE_JSON,
                        "Schedule:Compact".upper(),
                        self.heating_schedule_name,
                    )
                except ValueError:
                    pass

            elif not idf.getobject(
                "Schedule:Compact", self.heating_compact_schedule_name
            ):
                raise ValueError(
                    f"{self.heating_compact_schedule_name} not found in"
                    f"Schedule:Compact objects"
                )
            else:
                self.heating_schedule_name = self.heating_compact_schedule_name
        else:
            if self.heating_compact_schedule_name:
                raise ValueError("Both schedule name and time_series were specified")

            del_named_objects(idf, "Schedule:File", self.heating_time_series.name)

            add_hourly_schedules_from_df(
                idf=idf, data=self.heating_time_series.to_frame()
            )
            self.heating_schedule_name = self.heating_time_series.name

        if self.cooling_time_series is None:
            if self.cooling_compact_schedule_name is None:
                self.cooling_schedule_name = "100C_cooling_setpoint"
                try:
                    add_obj_from_obj_dict(
                        idf,
                        RESOURCE_JSON,
                        "Schedule:Compact".upper(),
                        self.cooling_schedule_name,
                    )
                except ValueError:
                    pass

            elif not idf.getobject(
                "Schedule:Compact", self.cooling_compact_schedule_name
            ):
                raise ValueError(
                    f"{self.cooling_compact_schedule_name} not found in"
                    f"Schedule:Compact objects"
                )
            else:
                self.cooling_schedule_name = self.cooling_compact_schedule_name
        else:
            if self.cooling_compact_schedule_name:
                raise ValueError(
                    "Both schedule name and time_series cannot be specified"
                )

            del_named_objects(idf, "Schedule:File", self.cooling_time_series.name)
            add_hourly_schedules_from_df(
                idf=idf, data=self.cooling_time_series.to_frame()
            )
            self.cooling_schedule_name = self.cooling_time_series.name

        if self.overwrite_heating_availability or self.overwrite_cooling_availability:
            self.cooling_schedule_name = "100C_cooling_setpoint"
            try:
                add_obj_from_obj_dict(
                    idf,
                    RESOURCE_JSON,
                    "Schedule:Compact".upper(),
                    "ON_24h24h_FULL_YEAR",
                )
            except ValueError:
                pass

        if self.overwrite_heating_availability:
            set_named_objects_field_values(
                idf=idf,
                idf_object="ZONEHVAC:IDEALLOADSAIRSYSTEM",
                field_name="Heating_Availability_Schedule_Name",
                idf_object_names=[ilas.Name for ilas in ilas_list],
                values="ON_24h24h_FULL_YEAR",
            )

        if self.overwrite_cooling_availability:
            set_named_objects_field_values(
                idf=idf,
                idf_object="ZONEHVAC:IDEALLOADSAIRSYSTEM",
                field_name="Cooling_Availability_Schedule_Name",
                idf_object_names=[ilas.Name for ilas in ilas_list],
                values="ON_24h24h_FULL_YEAR",
            )

        thermos_name_list = get_objects_name_list(
            idf, "ThermostatSetpoint:DualSetpoint"
        )

        thermos_to_keep = select_in_list(thermos_name_list, self.zones)

        set_named_objects_field_values(
            idf=idf,
            idf_object="ThermostatSetpoint:DualSetpoint",
            field_name="Heating_Setpoint_Temperature_Schedule_Name",
            idf_object_names=thermos_to_keep,
            values=self.heating_schedule_name,
        )

        set_named_objects_field_values(
            idf=idf,
            idf_object="ThermostatSetpoint:DualSetpoint",
            field_name="Cooling_Setpoint_Temperature_Schedule_Name",
            idf_object_names=thermos_to_keep,
            values=self.cooling_schedule_name,
        )

        if self.add_schedules_output_variables:
            add_output_variable(
                idf=idf,
                key_values=[self.heating_schedule_name, self.cooling_schedule_name],
                variables="Schedule Value",
            )

    def post_process(self, idf: IDF = None, eplus_results: pd.DataFrame = None):
        pass
