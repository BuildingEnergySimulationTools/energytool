import pandas as pd

import eppy
from eppy.modeleditor import IDF

import energytool.epluspreprocess as pr
from energytool.epluspostprocess import variable_contains_regex


class Building:
    def __init__(self, idf_path, clean_output_variable=True):

        self.idf = IDF(str(idf_path))
        if clean_output_variable:
            self.idf.idfobjects["Output:Variable"].clear()
            self.idf.idfobjects["Output:Meter"].clear()

        self.heating_system = {}
        self.cooling_system = {}
        self.ventilation_system = {}
        self.artificial_lighting_system = {}
        self.dwh_system = {}
        self.pv_production = {}
        self.other = {}

        self.energyplus_results = pd.DataFrame()
        self.building_results = pd.DataFrame()
        self.thermal_comfort = pd.DataFrame()

    @staticmethod
    def set_idd(root_eplus):
        try:
            IDF.setiddname(root_eplus / "Energy+.idd")
        except eppy.modeleditor.IDDAlreadySetError:
            pass

    @property
    def process_objects_list(self):
        system_list = [
            self.heating_system,
            self.cooling_system,
            self.ventilation_system,
            self.artificial_lighting_system,
            self.dwh_system,
            self.pv_production,
            self.other]

        proc_list = []
        for build_sys in system_list:
            for sys in build_sys.values():
                proc_list.append(sys)

        return proc_list

    @property
    def system_energy_results(self):
        system_dict = {
            "Heating": self.heating_system,
            "Cooling": self.cooling_system,
            "Ventilation": self.ventilation_system,
            "Lighting": self.artificial_lighting_system,
            "DHW": self.dwh_system,
            "Local_production": self.pv_production,
        }

        sys_nrj_res = pd.DataFrame(columns=system_dict.keys())
        if self.building_results.empty:
            return sys_nrj_res

        for header, systems in system_dict.items():
            if systems:
                to_find = variable_contains_regex(
                    [sys.name for sys in systems.values()])
                mask = self.building_results.columns.str.contains(
                    to_find)
                res = self.building_results.loc[:, mask]
                sys_nrj_res[header] = res.sum(axis=1)
            else:
                sys_nrj_res[header] = pd.Series(
                    self.building_results.shape[0] * [0.0],
                    index=self.building_results.index
                )
        sys_nrj_res["Total"] = sys_nrj_res.sum(axis=1)
        return sys_nrj_res

    @property
    def zone_name_list(self):
        return pr.get_objects_name_list(self.idf, 'Zone')

    @property
    def surface(self):
        return sum(z.Floor_Area for z in self.idf.idfobjects['Zone'])

    @property
    def volume(self):
        return sum(z.Volume for z in self.idf.idfobjects['Zone'])

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
            f"Heating systems : {list(self.heating_system.keys())}\n"
            f"Cooling systems : {list(self.cooling_system.keys())}\n"
            f"Ventilation system : "
            f"{list(self.ventilation_system.keys())}\n"
            f"Artificial lighting system : "
            f"{list(self.artificial_lighting_system.keys())}\n"
            f"DHW production : {list(self.dwh_system.keys())}\n"
            f"PV production : {list(self.pv_production.keys())}\n"
            f"Others : {list(self.other.keys())}"
        )

    def pre_process(self):
        self.energyplus_results = pd.DataFrame()

        for sys in self.process_objects_list:
            sys.pre_process()

    def post_process(self):
        self.building_results = pd.DataFrame()
        self.building_results.index = self.energyplus_results.index

        for sys in self.process_objects_list:
            sys.post_process()

