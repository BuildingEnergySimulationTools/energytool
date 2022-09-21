
# -*- coding: utf-8 -*-
"""
Created on Fri Sep 16 11:49:41 2022

@author: p.roger
"""

# =============================================================================
# To do 
# finir data profiler puis graphique
# =============================================================================

import datetime as dt
from copy import deepcopy
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

import energytool.buildingspliter as bs
import energytool.people as cp
from energytool.simulate import Simulation
from energytool.simulate import SimulationsRunner
import energytool.indicators as ind

class Settlement:
    
    def __init__(self,
                 building,
                 nb_iteration,
                 nb_profile
                 ):
        
        self.building = building
        self.nb_iteration = nb_iteration
        self.simulation_list = []
        self.nb_profile = nb_profile
        self.house_compo = {}
        
        self.dict_indicator = {
                "Windows Total Transmitted Solar Radiation"\
                    " Energy [J](Hourly)" : "solar radiation [kWh]",
                "IDEAL LOADS AIR:Zone Ideal Loads Supply Air Total Heating"\
                    " Energy [J](Hourly)" : "heating consumption [kWh]"             
                                }
        
    
    
    def run_simulations(self,
                        epw_file_path,
                        simulation_start=dt.datetime(2009, 1, 1, 0, 0, 0),
                        simulation_stop=dt.datetime(2009, 12, 31, 23, 0, 0),
                        timestep_per_hour=6,
                        run_directory=None,
                        nb_cpus=-1,
                        nb_simu_per_batch=4):
        
        if self.nb_iteration == 0 : 
            raise ValueError(
                'insufficient number of iterations, min. 1'
            )

        self.simulation_list.clear()
        
        for i in range(self.nb_iteration):
            building_tempo = deepcopy(self.building)
            split = bs.Building_spliter(building_tempo,4)
            split.pre_process()
            housing = split.dict_housing
            self.house_compo[f"iteration_{i+1}"] = []

            for j in housing:
                people = cp.People(
                                    building=building_tempo,
                                    density=0.03,
                                    nb_profile=self.nb_profile,
                                    housing=housing[j],
                                    year = 2009
                                    )
                people.pre_process()
                hsg_dscr1 = f"zone {housing[j][0]} {housing[j][2]} virtuosity"\
                            f" rate {housing[j][3]} domotic {housing[j][4]}"
                self.house_compo[f"iteration_{i+1}"].append(hsg_dscr1)
                hsg_dscr2 = f"zone {housing[j][1]} {housing[j][2]} virtuosity"\
                            f" rate {housing[j][3]} domotic {housing[j][4]}"
                self.house_compo[f"iteration_{i+1}"].append(hsg_dscr2)
                
                
            building_tempo.other["heater_test"] = ind.AddOutputVariables(
                name="heater",
                building=building_tempo,
                variables="Zone Ideal Loads Supply Air Total Heating Energy",
                key_value='*'
                                                    )   
            
            self.simulation_list.append(Simulation(
                                            building=building_tempo,
                                            epw_file_path=epw_file_path,
                                            simulation_start=simulation_start,
                                            simulation_stop=simulation_stop,
                                            timestep_per_hour=timestep_per_hour
                                                    ))
        self.simulation_runner = SimulationsRunner(
                                            simu_list=self.simulation_list,
                                            run_dir=run_directory,
                                            nb_cpus=nb_cpus,
                                            nb_simu_per_batch=nb_simu_per_batch
                                            )

        self.simulation_runner.run()
        
    def data_profiler(self,
                      zone="*"): #data = runner.simu_list
        
        result_list = [i.building.energyplus_results.sum() for
                       i in self.simulation_runner.simu_list
                       ]
        
        # Convertion to DataFrame and convertoin in kWh
        self.an_result = pd.concat(result_list, axis=1) / 1000 / 3600
        self.an_result.columns=list(self.house_compo.keys())
        
        # Suppression 
        self.an_result.drop(["Electricity:Facility [J](Hourly)",
                     "DistrictCooling:Facility [J](Hourly)",
                     "DistrictHeating:Facility [J](Hourly)",
                     "Carbon Equivalent:Facility [kg](Hourly)",
                     "Electricity:Facility [J](Daily)",
                     "DistrictCooling:Facility [J](Daily)",
                     "DistrictHeating:Facility [J](Daily)",
                     "Carbon Equivalent:Facility [kg](Daily) "],
                      0,
                      inplace = True)
        
        # creation of a column containing indicators
        list_indicator = [self.dict_indicator[" ".join(i.split()[1:])] 
                          for i in self.an_result.index]
        self.an_result["indicator"] = list_indicator
        self.an_result.index = [
                        list(i.split())[0].replace(":Zone", "", 1) 
                        for i in self.an_result.index
                      ]
        print(list_indicator)
        for i in self.dict_indicator.values():
            
            temp_mask =  self.an_result["indicator"] == i#"heating consumption [kWh]"
            new_df = self.an_result[temp_mask].sum(axis = 0)
            new_df["indicator"] = i
            new_df = pd.DataFrame(new_df).transpose()
            new_df.index = ["Building"]
            self.an_result = self.an_result.append(new_df,
                                                   ignore_index = False)
        
    def histogramme(self,
                    indicator,
                    zone):
        mask1 = self.an_result["indicator"] == indicator
        mask2 = self.an_result.index == zone
        mask = np.logical_and(mask1,mask2)
        value = self.an_result[mask].drop("indicator",axis=1).transpose()
        list_value = value[zone].tolist()
        plt.hist(list_value,density=True)