import pandas as pd

import eppy
from eppy.modeleditor import IDF

import numpy as np

import energytool.epluspreprocess as pr
import energytool.epluspostprocess as po
from energytool.epluspostprocess import variable_contains_regex


class Building:
    def __init__(
            self,
            idf_path,
            month_summer_begins=5,
            month_summer_ends=8,
            summer_comfort_top=28,
            clean_output_variable=True):

        self.idf = IDF(str(idf_path))
        if clean_output_variable:
            self.idf.idfobjects["Output:Variable"].clear()
            self.idf.idfobjects["Output:Meter"].clear()

        self.month_summer_begins = month_summer_begins
        self.month_summer_ends = month_summer_ends
        self.summer_comfort_top = summer_comfort_top
        self.heating_system = {}
        self.cooling_system = {}
        self.ventilation_system = {}
        self.artificial_lighting_system = {}
        self.dwh_system = {}
        self.pv_production = {}
        self.other = {}

        self.energyplus_results = pd.DataFrame()
        self.building_results = pd.DataFrame()
        self.custom_results = pd.DataFrame()

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
    def overshoot_thermal_comfort(self):
        if self.energyplus_results.empty:
            raise ValueError("No energyplus results available")

        year = self.building_results.index[0].year
        begin_loc = f"{year}-{self.month_summer_begins}"
        end_loc = f"{year}-{self.month_summer_ends}"

        zones_top = po.get_output_variable(
            self.energyplus_results,
            "Zone Operative Temperature",
            self.zone_name_list,
        )

        zones_occupation = po.get_output_variable(
            self.energyplus_results,
            "Zone People Occupant Count",
            self.zone_name_list,
        )

        zones_top = zones_top.loc[begin_loc:end_loc, :]
        zones_occupation = zones_occupation.loc[begin_loc:end_loc, :]

        zones_top_hot = zones_top > self.summer_comfort_top
        zones_is_someone = zones_occupation > 0

        shared_zones = list(set(zones_top_hot) & set(zones_is_someone))

        zone_hot_and_someone = np.logical_and(
            zones_top_hot[shared_zones],
            zones_is_someone[shared_zones]
        )

        return (zone_hot_and_someone.sum() / zones_is_someone.sum()) * 100

    @property
    def zone_name_list(self):
        return pr.get_objects_name_list(self.idf, 'Zone')

    @property
    def surface(self):
        return sum(eppy.modeleditor.zonearea(self.idf, z.Name)
                   for z in self.idf.idfobjects['Zone'])

    @property
    def volume(self):
        return sum(eppy.modeleditor.zonevolume(self.idf, z.Name)
                   for z in self.idf.idfobjects['Zone'])

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
