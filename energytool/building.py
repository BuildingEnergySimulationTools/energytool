import eppy
import pandas as pd
from eppy.modeleditor import IDF
from corrai.base.model import Model

from copy import deepcopy

from pathlib import Path

from eppy.runner.run_functions import run

from energytool.outputs import read_eplus_res

import energytool.epluspreprocess as pr
import tempfile
import shutil
from contextlib import contextmanager

import platform
import os


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

        self.systems = {
            "HEATING": [],
            "COOLING": [],
            "VENTILATION": [],
            "LIGHTING": [],
            "DHW": [],
            "PV": [],
            "OTHER": [],
        }

    @staticmethod
    def set_idd(root_eplus):
        try:
            IDF.setiddname(root_eplus / "Energy+.idd")
        except eppy.modeleditor.IDDAlreadySetError:
            pass

    @property
    def zone_name_list(self):
        return pr.get_objects_name_list(self.idf, "Zone")

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

    def infos(self):
        nb_occupant = pr.get_number_of_people(self.idf)
        print(
            f"==Building==\n"
            f"\n"
            f"Number of occupants : {round(nb_occupant, 2)}\n"
            f"Building surface : {self.surface} m²\n"
            f"Building volume : {self.volume} m3\n"
            f"Zone number : {len(self.zone_name_list)}\n"
            f"\n"
            f"==HVAC systems==\n"
            f"\n"
            f"Heating systems : {[obj.name for obj in self.systems['HEATING']]}\n"
            f"Cooling systems : {[obj.name for obj in self.systems['COOLING']]}\n"
            f"Ventilation system : "
            f"{[obj.name for obj in self.systems['VENTILATION']]}\n"
            f"Artificial lighting system : "
            f"{[obj.name for obj in self.systems['LIGHTING']]}\n"
            f"DHW production : {[obj.name for obj in self.systems['DHW']]}\n"
            f"PV production : {[obj.name for obj in self.systems['PV']]}\n"
            f"Others : {[obj.name for obj in self.systems['OTHERS']]}"
        )

    def simulate(
        self, parameter_dict: dict = None, simulation_options: dict = None
    ) -> pd.DataFrame:
        pass
        working_idf = deepcopy(self.idf)
        # working_syst = deepcopy(self.systems)
        with temporary_directory() as temp_dir:
            working_idf.saveas((Path(temp_dir) / "in.idf").as_posix(), encoding="utf-8")
            idd_ref = working_idf.idd_version
            run(
                idf=working_idf,
                weather=parameter_dict["epw_file"],
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

            return read_eplus_res(Path(temp_dir) / "eplusout.csv")
