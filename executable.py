# -*- coding: utf-8 -*-
"""
Created on Fri Sep  9 15:15:53 2022

@author: p.roger
"""
import energytool.system as st
import energytool.epluspreprocess as pr
import energytool.epluspostprocess as po
import energytool.indicators as ind
from pathlib import Path
import datetime as dt
import pandas as pd
from copy import deepcopy
from energytool.simulate import Simulation
from energytool.simulate import SimulationsRunner
from energytool.building import Building

import energytool.people as cp
import energytool.buildingspliter as bs

idf_path = Path(r"C:\Users\p.roger\Desktop\Nobatek-INF4\FiabGP\class_people\idfmodifie01.idf")
epw_path = Path(r"C:\Users\p.roger\Desktop\Nobatek-INF4\FiabGP\Energy plus batiment test\batiment lheers\suite_fiabgp\simulation_via_python\Lille_2020_wt1b.epw")
eplus_root = Path(r"C:\EnergyPlusV9-4-0")

Building.set_idd(eplus_root)
building = Building(idf_path=idf_path)
simulation_list=[]
for j in range(1):

    building_tempo = deepcopy(building)
    split = bs.Building_spliter(building_tempo,4)
    split.pre_process()
    housing = split.dict_housing

    print (f"building itération n°{j+1}")
    for i in housing:
        print (f"     {i}")
        people = cp.People(building_tempo,0.03,4,housing=housing[i],year = 2002)
        people.pre_process()
        
    #people.idf.saveas('sorit01.idf', encoding='utf-8')
    ind.AddOutputVariables(
                            name="Lighting",
                            building=building_tempo,
                            variables="Zone Lights Convective Heating Energy",
                            key_value='*'
    
    
    )
    simulation_list.append(Simulation(
                building=building_tempo,
                epw_file_path=epw_path,
                simulation_start=dt.datetime(2002, 5, 1, 0, 0, 0),
                simulation_stop=dt.datetime(2002, 10, 31, 23, 0, 0),
                timestep_per_hour=2
            ))


# run_dir = r"C:\Users\p.roger\Desktop\Nobatek-INF4\FiabGP\result"
# runner = SimulationsRunner(
#     simulation_list,
#     run_dir=Path(run_dir),
#     nb_cpus=2,
#     nb_simu_per_batch=4
#     )
# runner.run()