from eppy.modeleditor import IDF


class Building:
    def __init__(
            self,
            idf_path,
            heating_system=None,
            cooling_system=None,
            ventilation_system=None,
            dwh_system=None,
            pv_production=None,):

        self.idf = IDF(str(idf_path))
        self.heating_system = heating_system
        self.cooling_system = cooling_system
        self.ventilation_system = ventilation_system
        self.dwh_system = dwh_system
        self.pv_production = pv_production

    @staticmethod
    def set_idd(root_eplus):
        IDF.setiddname(root_eplus / "Energy+.idd")
