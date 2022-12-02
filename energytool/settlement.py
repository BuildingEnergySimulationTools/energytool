
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

import plotly.express as px

import energytool.buildingspliter as bs
import energytool.people as cp
from energytool.simulate import Simulation
from energytool.simulate import SimulationsRunner
import energytool.indicators as ind

class Settlement:
    
    def __init__(self,
                 building,
                 nb_iteration,
                 nb_profile,
                 chose_profile=False,
                 fixe_building=False
                 ):
        
        self.building = building
        self.nb_iteration = nb_iteration
        self.simulation_list = []
        self.nb_profile = nb_profile
        self.house_compo = {}
        self.chose_profile=chose_profile
        self.fixe_building=fixe_building
        
        self.dict_indicator = {
                "Windows Total Transmitted Solar Radiation"\
                    " Energy [J](Hourly)" : "solar radiation [kWh]",
                "IDEAL LOADS AIR:Zone Ideal Loads Supply Air Total Heating"\
                    " Energy [J](Hourly)" : "heating consumption [kWh]",
                "IDEAL LOADS AIR:Zone Ideal Loads Supply Air Total Cooling"\
                    " Energy [J](Hourly)" : "cooling consumption [kWh]",
                "Zone Infiltration Volume [m3](Hourly)":"natural airflow [m3]",
                "Operative Temperature [C](Hourly)":"operatice temperature[°C]",
                
                                    
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
            split = bs.Building_spliter(building_tempo,
                                        self.nb_profile,
                                        self.chose_profile,
                                        self.fixe_building)
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
            
            building_tempo.other["cooler_test"] = ind.AddOutputVariables(
                name="cooler",
                building=building_tempo,
                variables="Zone Ideal Loads Supply Air Total Cooling Energy",
                key_value='*'
                                                    )
            
            building_tempo.other["sun_test"] = ind.AddOutputVariables(
                    name="sun",
                    building=building_tempo,
                    variables="Zone Windows Total Transmitted Solar Radiation Energy",
                    key_value='*'
                                                        )
                                
            building_tempo.other["nat_vent_gain"] = ind.AddOutputVariables(
                    name="vent_vol",
                    building=building_tempo,
                    variables="AFN Zone Infiltration Volume",
                    key_value='*'   
                                                        )
            building_tempo.other["temp_room"] = ind.AddOutputVariables(
                    name="temp_room",
                    building=building_tempo,
                    variables="Zone Operative Temperature",
                    key_value='*'   
                                                        )
            
            
            
            # building_tempo.other["nat_vent_loss"] = ind.AddOutputVariables(
            #         name="vent_loss",
            #         building=building_tempo,
            #         variables="Zone Ventilation Sensible Heat Loss Energy",
            #         key_value='*'
            #                                             )    
            
            
            
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
        
    def combination_catalog(self):
        dict_temp = {
                    "profile":[],
                    "virtuosity":[],
                    "domotic":[]
                    }
        multi_ind = [[],[]]
         
        for i in self.house_compo.keys():
            for j in self.house_compo[i]:
                multi_ind[0].append(i)
                multi_ind[1].append(j.split()[1])
                dict_temp["profile"].append(j.split()[2])
                dict_temp["virtuosity"].append(j.split()[5])
                dict_temp["domotic"].append(j.split()[7])
                
        self.catalog = pd.DataFrame(
                                    dict_temp, 
                                    index=multi_ind
                                    )
    
    def data_profiler(self,
                      zone="*"): #data = runner.simu_list
        
        unwant_info = [
                "Electricity:Facility [J](Hourly)",
                 "DistrictCooling:Facility [J](Hourly)",
                 "DistrictHeating:Facility [J](Hourly)",
                 "Carbon Equivalent:Facility [kg](Hourly)",
                 "Electricity:Facility [J](Daily)",
                 "DistrictCooling:Facility [J](Daily)",
                 "DistrictHeating:Facility [J](Daily)",
                 "Carbon Equivalent:Facility [kg](Daily) "
                     ]
# =============================================================================        
#    creation of a dataframe with the results for each zone and each iteration
# =============================================================================
        time_list = [deepcopy(i.building.energyplus_results) 
                                 for i in self.simulation_runner.simu_list]
        self.time_list = time_list
        
        [i.drop(unwant_info,
                axis=1,
                inplace = True)
                for i in time_list]
        
        for j in time_list:
            a=[]
            a = [
                i.replace(k,self.dict_indicator[k],1).replace(":Zone","", 1).replace(":AFN","", 1)
                for i in j.columns
                for k in (
                    n
                    for n in set(self.dict_indicator.keys())
                    if n in i
                          )
                ]

            j.columns = a
            
        # Convertion to DataFrame and convertion in kWh for Joules unit
        temp = pd.concat(time_list,
                            axis=1,
                            keys=list(self.house_compo.keys())
                            ) 
        
        self.time_result = pd.DataFrame(
                                        columns=pd.MultiIndex.from_tuples(
                                            temp.columns)
                                        )
        
        for (colname,colval) in temp.iteritems():
                
                if "[kWh]" in colname[1]:                    
                    self.time_result.loc[
                                        :,(colname[0],colname[1])
                                        ] = colval / 3600 / 1000
                else : 
                    self.time_result.loc[
                                        :,(colname[0],colname[1])
                                        ] = colval 

        
# =============================================================================        
#    creation of a dataframe with the annual results
# =============================================================================
         
        annual_list = [i.building.energyplus_results.sum() for
                       i in self.simulation_runner.simu_list
                       ]                      
        # Convertion to DataFrame and convertion in kWh for Joules unit
        temp_an = pd.concat(annual_list,
                            axis=1)
        temp_an.columns=list(self.house_compo.keys())
        self.an_result = pd.DataFrame(columns=temp_an.columns)
        
        for name_index in temp_an.index:
                if "[J]" in name_index:
                    self.an_result.loc[name_index,:] = [ i/3600/1000  for i in 
                                                       temp_an.loc[
                                                           name_index,:
                                                                   ]
                                                       ] 
                else : 
                    self.an_result.loc[name_index,:] = [ i for i in 
                                                       temp_an.loc[
                                                           name_index,:
                                                                   ]
                                                       ] 
                    

        
        # Suppression 
        self.an_result.drop(unwant_info,
                            axis=0,
                            inplace = True)
        
        # creation of a column containing indicators
        list_indicator = [self.dict_indicator[" ".join(i.split()[1:])] 
                          for i in self.an_result.index]
        self.an_result["indicator"] = list_indicator
        self.an_result.index = [
                        list(i.split())[0].replace(":Zone","", 1).replace(":AFN","", 1)
                        for i in self.an_result.index
                      ]
        
        
        for i in self.dict_indicator.values():
            
            temp_mask =  self.an_result["indicator"] == i
            new_df = self.an_result[temp_mask].sum(axis = 0)
            new_df["indicator"] = i
            new_df = pd.DataFrame(new_df).transpose()
            new_df.index = ["Building"]
            pd.concat([self.an_result,new_df],
                      ignore_index = False)
        
    def histogramme(self,
                    indicator,
                    zone):
        
        mask1 = self.an_result["indicator"] == indicator
        mask2 = self.an_result.index == zone
        mask = np.logical_and(mask1,mask2)
        value = self.an_result[mask].drop("indicator",axis=1).transpose()
        fig = px.histogram(value,x=value[zone],nbins=40)
        fig.update_layout(
                            title=zone,
                            xaxis_title="Combination",
                            yaxis_title=indicator,
                            )
        fig.show()
        
    def bar_analysis(self,
                     indicator,
                     zone):
 
        mask1 = self.an_result["indicator"] == indicator
        mask2 = self.an_result.index == zone.upper()
        mask = np.logical_and(mask1,mask2)
        value = self.an_result[mask].drop("indicator",axis=1).transpose()
        value["combination"] = [
                    " ".join(self.catalog.loc[i,zone]) 
                    for i in value.index
                                ]
        value=value.reset_index(drop=True)
        value.set_index("combination", 
                        inplace = True)
        
        value = value.sort_values(by=[zone.upper()])
        value = value.groupby(value.index).mean()
        
        #value.groupby(value.index).mean()
        self.value = value

        fig = px.bar(value,x=value.index,y=value[zone.upper()])
        fig.update_layout(
                            title=zone,
                            xaxis_title="Combination",
                            yaxis_title=indicator,
                            )
        fig.show()
        
    def time_analysis(self,
                      indicator,
                      zone):
        
        self.combination_catalog()
        zone_name = zone
        indicator = indicator
        
        
        want_to_show = zone_name.upper() + " " + indicator
        want_list = [i for i in  self.time_result.columns if want_to_show in i]
        legend_list= [' '.join(list(
            self.catalog.loc[(i[0],zone_name)]))
                     for i in want_list]
        df_temp = self.time_result.loc[:, want_list].reset_index(level=[0])
        df_temp.set_index("Date/Time",inplace = True)
        df_temp.columns = legend_list
        df_temp = df_temp.loc[:,~df_temp.columns.duplicated()]
        fig = px.line(df_temp)
        
        fig.update_layout(
                            title=zone_name,
                            xaxis_title="Date",
                            yaxis_title=indicator,
                            legend_title="Combination",
                            )

        fig.show()

                                
                
        



    