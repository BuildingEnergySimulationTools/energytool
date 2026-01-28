import eppy
import enum
import platform
import os
import tempfile
import shutil

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

import pandas as pd
from corrai.base.model import Model
from eppy.modeleditor import IDF
from eppy.runner.run_functions import run
import eppy.json_functions as json_functions

import energytool.base.idf_utils
from energytool.base.parse_results import read_eplus_res
from energytool.outputs import get_results
from energytool.system import System, SystemCategories
from energytool.base.idfobject_utils import (
    get_number_of_people,
    set_timestep,
    set_run_period,
)


class ParamCategories(enum.Enum):
    IDF = "idf"
    SYSTEM = "system"
    EPW_FILE = "epw_file"


class SimuOpt(enum.Enum):
    START = "start"
    STOP = "stop"
    TIMESTEP = "timestep"
    OUTPUTS = "outputs"
    EPW_FILE = "epw_file"
    VERBOSE = "verbose"


@contextmanager
def temporary_directory():
    if platform.system() == "Windows":
        user_home = os.path.expanduser("~")
        temp_path = os.path.join(user_home, r"AppData\Local\Temp")
    else:
        temp_path = None
    temp_dir = tempfile.mkdtemp(dir=temp_path)
    try:
        yield temp_dir

    finally:
        shutil.rmtree(temp_dir)


class Building(Model):
    """
    The Building class represents a building model. It is based on an EnergyPlus
    simulation file.

    :param idf_path: The path to the EnergyPlus IDF file that defines the building model.

    Attributes:
        idf: An EnergyPlus IDF object representing the building's configuration.
        systems: A dictionary that stores various categories of
        energytool HVAC systems associated with the building.

    Methods:
        set_idd(root_eplus): Sets the EnergyPlus IDD file used for parsing the IDF file.
        zone_name_list: Returns a list of names of zones defined in the building model.
        surface: Calculates and returns the total surface area of the building in square meters.
        volume: Calculates and returns the total volume of the building in cubic meters.
        add_system(system): Adds an HVAC system to the building's systems.
        del_system(system_name): Deletes an HVAC system from the building's systems by name.
        simulate(property_dict, simulation_options): Simulates the building model with
        specified parameters and simulation options, returning the simulation results
        as a pandas DataFrame.
    """

    def __init__(self, idf_path):
        super().__init__(is_dynamic=True)
        self.idf = IDF(str(idf_path))
        self._idf_path = str(idf_path)
        self.systems = {category: [] for category in SystemCategories}

    def get_property_values(self, property_list: list[str]) -> list[str | int | float]:
        return self.get_param_init_value(property_list)

    @staticmethod
    def set_idd(root_eplus):
        try:
            IDF.setiddname(root_eplus / "Energy+.idd")
        except eppy.modeleditor.IDDAlreadySetError:
            pass

    @property
    def zone_name_list(self):
        return energytool.base.idf_utils.get_objects_name_list(self.idf, "Zone")

    @property
    def surface(self):
        return sum(
            eppy.modeleditor.zonearea(self.idf, z.Name)
            for z in self.idf.idfobjects["Zone"]
        )

    @property
    def volume(self):
        return sum(
            eppy.modeleditor.zonevolume(self.idf, z.Name)
            for z in self.idf.idfobjects["Zone"]
        )

    def __repr__(self):
        return f"""==Building==
Number of occupants: {round(get_number_of_people(self.idf), 2)}
Building surface: {self.surface} m²
Building volume: {self.volume} m3
Zone number: {len(self.zone_name_list)}

==HVAC systems==
Heating systems: {[obj.name for obj in self.systems[SystemCategories.HEATING]]}
Auxiliary: {[obj.name for obj in self.systems[SystemCategories.AUXILIARY]]}
Cooling systems: {[obj.name for obj in self.systems[SystemCategories.COOLING]]}
Ventilation system: {[obj.name for obj in self.systems[SystemCategories.VENTILATION]]}
Artificial lighting system: {[obj.name for obj in self.systems[SystemCategories.LIGHTING]]}
DHW production: {[obj.name for obj in self.systems[SystemCategories.DHW]]}
PV production: {[obj.name for obj in self.systems[SystemCategories.PV]]}
Sensors: {[obj.name for obj in self.systems[SystemCategories.SENSOR]]}
Others: {[obj.name for obj in self.systems[SystemCategories.OTHER]]}
"""

    def add_system(self, system: System):
        self.systems[system.category].append(system)

    def del_system(self, system_name: str):
        for cat in SystemCategories:
            for i, sys in enumerate(self.systems[cat]):
                if sys.name == system_name:
                    del self.systems[cat][i]

    def get_param_init_value(
        self,
        parameter_name_list: str | list[str] = None,
    ):
        """
        Returns the initial value(s) of one or more parameters of the model.

        :param parameter_name_list: A string or list of parameter names (str), like
            "idf.Material.SomeMat.Thickness" or "system.heating.Heater.cop"
        :return: a list of values if input is a list, or a single value if input is a string
        """
        if isinstance(parameter_name_list, str):
            is_single = True
            parameter_name_list = [parameter_name_list]
        else:
            is_single = False

        working_idf = deepcopy(self.idf)
        values = []

        for full_key in parameter_name_list:
            split_key = full_key.split(".")

            if split_key[0] == ParamCategories.IDF.value:
                if "*" in split_key:
                    is_single = False

                    object_type = split_key[1]
                    field_name = split_key[-1]

                    objs = working_idf.idfobjects[object_type.upper()]
                    for obj in objs:
                        values.append(getattr(obj, field_name))
                else:
                    value = energytool.base.idf_utils.getidfvalue(working_idf, full_key)
                    values.append(value)

            elif split_key[0] == ParamCategories.SYSTEM.value:
                if split_key[1].upper() in [sys.value for sys in SystemCategories]:
                    sys_category = SystemCategories(split_key[1].upper())
                    system_obj = self.systems[sys_category][split_key[2]]
                    value = getattr(system_obj, split_key[3])
                    values.append(value)
                else:
                    raise ValueError(f"Unknown system category in key: {full_key}")

            elif split_key[0] == ParamCategories.EPW_FILE.value:
                values.append(str(self.weather.epw_path))

            else:
                raise ValueError(f"Unsupported parameter category in key: {full_key}")

        return values[0] if is_single else values

    def simulate(
        self,
        property_dict=None,
        simulation_options=None,
        idf_save_path=None,
        **simulation_kwargs,
    ) -> pd.DataFrame:
        """
        Simulate the building model with specified parameters and simulation options.

        :param property_dict: A dictionary containing key-value pairs representing
            parameters to be modified in the building model.
            These parameters can include changes to the IDF file, energytool HVAC system
            settings, or weather file.
            The key must represent the "path" to the parameter. "dots" must be separator.
            "idf" at the beginning of the path indicates a modification in the idf file
            "system" indicates a modification at energytool system level
            "epw_file" the path to epw file.
            see ParamCategories for allowed prefix

        :param simulation_options: A dictionary of simulation options that control
            the behavior of the EnergyPlus simulation.
            These options can include the choice of weather file, run period,
            time step, and desired outputs.
            See SimuOpt enum for allowed simulation options

        :param idf_save_path: (Optional) A Path where the modified
        IDF (Input Data File) will be saved after applying the specified
        parameter changes.
        If not provided, the modified IDF will not be saved separately.

        :return: A pandas DataFrame containing the simulation results, which may
            include energy consumption, indoor conditions, and other relevant data
            based on the specified outputs.

        The `simulate` method allows you to customize and run an EnergyPlus simulation
        for the building model. It provides the flexibility to modify various
        parameters and specify simulation options. It returns the results in a
        structured DataFrame

        Usage:
        # Example usage of the simulate method
        parameter_changes = {
            "idf.material.Urea Formaldehyde Foam_.1327.Conductivity": 0.05,
            "system.heating.Heater.cop": 0.5,
        }
        simulation_options = {
            'EPW_FILE': 'path/to/weather.epw',
            'START': '2023-01-01 00:00:00',
            'STOP': '2023-01-31 23:59:59',
            'TIMESTEP': 900
        }
        results = building.simulate(property_dict=parameter_changes,
        simulation_options=simulation_options)

        """
        self.idf_save_path = idf_save_path

        working_idf = deepcopy(self.idf)
        working_syst = deepcopy(self.systems)

        epw_path = None
        if property_dict is None:
            property_dict = {}

        for key in property_dict:
            split_key = key.split(".")

            # IDF modification
            if split_key[0] == ParamCategories.IDF.value:
                if "*" in split_key:
                    object_type = split_key[1]
                    field_name = split_key[-1]
                    value = property_dict[key]

                    objs = working_idf.idfobjects[object_type.upper()]
                    for obj in objs:
                        setattr(obj, field_name, value)
                else:
                    json_functions.updateidf(working_idf, {key: property_dict[key]})

            # In case it's a SYSTEM parameter, retrieve it in dict by category and name
            elif split_key[0] == ParamCategories.SYSTEM.value:
                if split_key[1].upper() in [sys.value for sys in SystemCategories]:
                    sys_key = SystemCategories(split_key[1].upper())
                else:
                    raise ValueError(
                        f"{split_key[1].upper()} is not part of SystemCategories"
                        f"choose one of {[elmt.value for elmt in SystemCategories]}"
                    )
                for syst in working_syst[sys_key]:
                    if syst.name == split_key[2]:
                        setattr(syst, split_key[3], property_dict[key])

            # Meteo file
            elif split_key[0] == ParamCategories.EPW_FILE.value:
                epw_path = property_dict[key]
            else:
                raise ValueError(
                    f"{split_key[0]} was not recognize as a valid parameter category"
                )

        # Simulation options
        if epw_path is None:
            try:
                epw_path = simulation_options[SimuOpt.EPW_FILE.value]
            except KeyError:
                raise ValueError(
                    "'epw_path' not found in property_dict nor in simulation_options"
                )
        elif SimuOpt.EPW_FILE.value in list(simulation_options.keys()):
            raise ValueError(
                "'epw_path' have been used in both property_dict and "
                "simulation_options"
            )
        ref_year = None
        if SimuOpt.START.value in simulation_options.keys():
            start = pd.to_datetime(simulation_options[SimuOpt.START.value])
            ref_year = start.year
            try:
                end = pd.to_datetime(simulation_options[SimuOpt.STOP.value])
            except KeyError:
                raise ValueError(
                    "Cannot set run period. Only start value was found "
                    "in simulation_options dict"
                )
            set_run_period(working_idf, start, end)

        if SimuOpt.TIMESTEP.value in simulation_options.keys():
            # timestep is supposed to be set in seconds
            set_timestep(
                working_idf,
                nb_timestep_per_hour=int(
                    3600 / simulation_options[SimuOpt.TIMESTEP.value]
                ),
            )

        # PRE-PROCESS
        system_list = [sys for sublist in working_syst.values() for sys in sublist]
        for system in system_list:
            system.pre_process(working_idf)

        # DEFAULT VERBOSE
        if SimuOpt.VERBOSE.value not in simulation_options.keys():
            simulation_options[SimuOpt.VERBOSE.value] = "v"

        # SIMULATE
        with temporary_directory() as temp_dir:
            working_idf.saveas((Path(temp_dir) / "in.idf").as_posix(), encoding="utf-8")
            idd_ref = working_idf.idd_version
            run(
                idf=working_idf,
                weather=epw_path,
                output_directory=temp_dir.replace("\\", "/"),
                annual=False,
                design_day=False,
                idd=None,
                epmacro=False,
                expandobjects=False,
                readvars=True,
                output_prefix=None,
                output_suffix=None,
                version=False,
                verbose=simulation_options[SimuOpt.VERBOSE.value],
                ep_version=f"{idd_ref[0]}-{idd_ref[1]}-{idd_ref[2]}",
            )

            eplus_res = read_eplus_res(
                Path(temp_dir) / "eplusout.csv", ref_year=ref_year
            )

            # Save IDF file after pre-process
            if self.idf_save_path:
                working_idf.save(idf_save_path)

            # POST-PROCESS
            return get_results(
                idf=working_idf,
                eplus_res=eplus_res,
                systems=working_syst,
                outputs=simulation_options[SimuOpt.OUTPUTS.value],
            )

    def save(self, file_path: Path):
        """
        Save the current parameters of the model to a file.

        :param file_path: The file path where the parameters will be saved.
        """
        self.idf.saveas(file_path.as_posix(), encoding="utf-8")
