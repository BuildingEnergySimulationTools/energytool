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
                                    housing=housing[i],
                                    year = 2009
                                    )
                people.pre_process()
                hsg_dscr1 = f"zone {housing[i][0]} {housing[i][2]} virtuosity"\
                            f" rate {housing[i][3]} domotic {housing[i][4]}"
                self.house_compo[f"iteration_{j+1}"].append(hsg_dscr1)
                hsg_dscr2 = f"zone {housing[i][1]} {housing[i][2]} virtuosity"\
                            f" rate {housing[i][3]} domotic {housing[i][4]}"
                self.house_compo[f"iteration_{j+1}"].append(hsg_dscr2)
                
                
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
        simulation_runner = SimulationsRunner(
                                            simu_list=self.simulation_list,
                                            run_dir=run_directory,
                                            nb_cpus=nb_cpus,
                                            nb_simu_per_batch=nb_simu_per_batch
                                            )

        simulation_runner.run()
        
        def data_profiler(data): #data = runner.simu_list
            pass