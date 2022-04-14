import pandas as pd
from eppy.modeleditor import IDF


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

        self.zone_name_list = [z.Name for z in self.idf.idfobjects['Zone']]
        self.surface = sum(z.Floor_Area for z in self.idf.idfobjects['Zone'])
        self.volume = sum(z.Volume for z in self.idf.idfobjects['Zone'])

        self.energyplus_results = []
        self.building_results = pd.DataFrame()

    # TODO write __copy__ method

    @staticmethod
    def set_idd(root_eplus):
        IDF.setiddname(root_eplus / "Energy+.idd")

    def pre_process(self):
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
        system_dict = (
            self.heating_system |
            self.cooling_system |
            self.ventilation_system |
            self.dwh_system |
            self.pv_production
        )

        for build_sys in system_dict.values():
            build_sys.post_process()



