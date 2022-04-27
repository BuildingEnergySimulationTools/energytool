import pandas as pd
from eppy.modeleditor import IDF

import energytool.epluspreprocess as pr


class Building:
    def __init__(self, idf_path, clean_output_variable=True):

        self.idf = IDF(str(idf_path))
        if clean_output_variable:
            self.idf.idfobjects["Output:Variable"].clear()

        self.heating_system = {}
        self.cooling_system = {}
        self.ventilation_system = {}
        self.dwh_system = {}
        self.pv_production = {}

        self.zone_name_list = pr.get_objects_name_list('Zone')
        self.surface = sum(z.Floor_Area for z in self.idf.idfobjects['Zone'])
        self.volume = sum(z.Volume for z in self.idf.idfobjects['Zone'])

        self.energyplus_results = pd.DataFrame()
        self.building_results = pd.DataFrame()

    @staticmethod
    def set_idd(root_eplus):
        IDF.setiddname(root_eplus / "Energy+.idd")

    def infos(self):
        print(
            f"==Building geometry==\n"
            f"\n"
            f"Building surface : {self.surface} m²\n"
            f"Building volume : {self.volume} m3\n"
            f"Zone number : {len(self.zone_name_list)}\n"
            f"\n"
            f"==HVAC systems==\n"
            f"\n"
            f"Heating systems : {[n for n in self.heating_system.keys()]}\n"
            f"Cooling systems : {[n for n in self.cooling_system.keys()]}\n"
            f"Ventilation system : {[n for n in self.ventilation_system.keys()]}\n"
            f"DHW production : {[n for n in self.dwh_system.keys()]}\n"
            f"PV production : {[n for n in self.pv_production.keys()]}\n"
        )

    def pre_process(self):
        self.energyplus_results = pd.DataFrame()

        system_dict = (
                self.heating_system |
                self.cooling_system |
                self.ventilation_system |
                self.dwh_system |
                self.pv_production
        )

        for build_sys in system_dict.values():
            build_sys.pre_process()

    def post_process(self):
        self.building_results = pd.DataFrame()

        system_dict = (
                self.heating_system |
                self.cooling_system |
                self.ventilation_system |
                self.dwh_system |
                self.pv_production
        )

        for build_sys in system_dict.values():
            build_sys.post_process()
