import eppy
import pandas as pd
from eppy.modeleditor import IDF
from corrai.base.model import Model

from copy import deepcopy

from pathlib import Path

from eppy.runner.run_functions import run
import eppy.json_functions as json_functions
import enum

import energytool.base.idf_utils
from energytool.base.parse_results import read_eplus_res
from energytool.outputs import get_systems_results
from energytool.system import System, SystemCategories
from energytool.base.idfobject_utils import get_number_of_people

import tempfile
import shutil
from contextlib import contextmanager

import platform
import os


class ParamCategories(enum.Enum):
    IDF = "idf"
    SYSTEM = "system"
    EPW_FILE = "epw_file"


class SimuOpt(enum.Enum):
    START = "start"
    STOP = "stop"
    TIMESTEP = "timestep"
    OUTPUTS = "outputs"


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
    def __init__(
        self,
        idf_path,
    ):
        self.idf = IDF(str(idf_path))
        self.systems = {category: [] for category in SystemCategories}

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
Number of occupants : {round(get_number_of_people(self.idf), 2)}
Building surface : {self.surface} m²
Building volume : {self.volume} m3
Zone number : {len(self.zone_name_list)}

==HVAC systems==
Heating systems : {[obj.name for obj in self.systems[SystemCategories.HEATING]]}
Cooling systems : {[obj.name for obj in self.systems[SystemCategories.COOLING]]}
Ventilation system : {[obj.name for obj in self.systems[SystemCategories.VENTILATION]]}
Artificial lighting system : {[obj.name for obj in self.systems[SystemCategories.LIGHTING]]}
DHW production : {[obj.name for obj in self.systems[SystemCategories.DHW]]}
PV production : {[obj.name for obj in self.systems[SystemCategories.PV]]}
Others : {[obj.name for obj in self.systems[SystemCategories.OTHER]]}
"""

    def add_system(self, system: System):
        self.systems[system.category].append(system)

    def simulate(
        self, parameter_dict: dict = None, simulation_options: dict = None
    ) -> pd.DataFrame:
        working_idf = deepcopy(self.idf)
        working_syst = deepcopy(self.systems)

        epw_path = None
        for key in parameter_dict:
            split_key = key.split(".")

            # IDF modification
            if split_key[0] == ParamCategories.IDF.value:
                json_functions.updateidf(working_idf, {key: parameter_dict[key]})

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
                        setattr(syst, split_key[3], parameter_dict[key])

            # Meteo file
            elif split_key[0] == ParamCategories.EPW_FILE.value:
                epw_path = parameter_dict[key]
            else:
                raise ValueError(
                    f"{split_key[0]} was not recognize as a valid parameter category"
                )

        if epw_path is None:
            raise ValueError("'epw_path' not found in parameter_dict")

        system_list = [sys for sublist in working_syst.values() for sys in sublist]
        for system in system_list:
            system.pre_process(working_idf)

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
                verbose="v",
                ep_version=f"{idd_ref[0]}-{idd_ref[1]}-{idd_ref[2]}",
            )

            eplus_res = read_eplus_res(Path(temp_dir) / "eplusout.csv")

            return get_systems_results(
                eplus_res,
                simulation_options[SimuOpt.OUTPUTS],
                working_idf,
                systems=working_syst,
            )
