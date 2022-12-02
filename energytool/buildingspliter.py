# -*- coding: utf-8 -*-
"""
Created on Wed Aug 31 11:59:14 2022

@author: p.roger
"""
import random as rd
import energytool.epluspreprocess as pr

class Building_spliter:
    
    """ 
    class which allows the building to be divided into housing
    each housing consists of {- Day zone
                              - Night zone
                              - An occupancy profile
                              - A virtuosity coefficient
                              - A home automation coefficient}  
    
    """
    def  __init__(self,
                  building,
                  nb_profile,
                  chose_profile=False,
                  fixe_building=False):
        
        self.building = building
        self.nb_profile = nb_profile
        self.dict_profile = {}
        self.chose_profile = chose_profile
        self.fixe_building=fixe_building
        
    def spliter(self):
        
        """
        

        Returns
        -------
        a dictionary of housings grouped by zone based
        on the names assigned to the zones.

        """
        
        
        self.dict_housing = {}
        
        list_int = [
                    i.Name for i in self.building.idf.idfobjects["ZONE"]
                    if "Apprtmnt" in i.Name
                    ]

        
        nb_appartement = len(list_int) / 2
        
        for i in range(int(nb_appartement)):

            self.dict_housing[f"Apprtmnt{i+1}"] = [
                        k.Name for k in self.building.idf.idfobjects["ZONE"]
                        if f"Apprtmnt{i+1}" in k.Name
                                                    ]

    def profile_assignation(self):
        """
        

        Returns
        -------
        a dictionary of flats grouped by zone,
        with a randomly or chosen assigned occupancy profile.

        """
        
            
        if not self.chose_profile:
            
            compt = 0
            for i in range(self.nb_profile):
                compt = compt + 1/self.nb_profile
                self.dict_profile[round(compt,1)] = f"profile_{i+1}"
        
        else:
            compt = 0
            for i in range(self.nb_profile):
                compt = compt + 1/self.nb_profile
                self.dict_profile[round(compt,1)] = self.chose_profile
            
        if self.fixe_building:
            for i in self.dict_housing:
                
                if i.upper() in self.fixe_building[0] :
                    n = rd.choice(list(self.dict_profile.keys()))
                    self.dict_housing[i].append(self.dict_profile[n])
                    
                else:
                    self.dict_housing[i].append(self.fixe_building[1])
                    
        else:
            for i in self.dict_housing:
                n = rd.choice(list(self.dict_profile.keys()))
                self.dict_housing[i].append(self.dict_profile[n])
            
    def virtuosity_assignation(self):
        """
        

        Returns
        -------
        a dictionary of flats grouped by zone,
        with a randomly assigned occupancy profile and virtuosity coefficient.

        """
        if self.fixe_building:
            for i in self.dict_housing:
                if i.upper() in self.fixe_building[0]:
                    n = rd.random()
                    if n < 1/3:
                        self.dict_housing[i].append("bad")
                    
                    elif n > 2/3: 
                        self.dict_housing[i].append("good")
                        
                    else:
                        self.dict_housing[i].append("average")
                else:
                    self.dict_housing[i].append(self.fixe_building[2])
        
        else:
            for i in self.dict_housing:
                n = rd.random()
                if n < 1/3:
                    self.dict_housing[i].append("bad")
                
                elif n > 2/3: 
                    self.dict_housing[i].append("good")
                    
                else:
                    self.dict_housing[i].append("average")
    
    def domotic_assignation(self):           
        """
        

        Returns
        -------
        a dictionary of flats grouped by zone,
        with a randomly assigned:
            - occupancy profile 
            - virtuosity coefficient
            - domotic utilisation parameter (True or falsle)

        """
        
        if self.fixe_building:
            for i in self.dict_housing:
                if i.upper() in self.fixe_building[0]:
                    n = rd.random()
                    if n < 1/2:
                        self.dict_housing[i].append(False)
                    
                    elif n > 1/2 : 
                        self.dict_housing[i].append(True)
                else:
                    self.dict_housing[i].append(self.fixe_building[3])
        else: 
            for i in self.dict_housing:
                n = rd.random()
                if n < 1/2:
                    self.dict_housing[i].append(False)
                
                elif n > 1/2 : 
                    self.dict_housing[i].append(True)
                    
    def pre_process(self):

        idf_schedules = self.building.idf.idfobjects['Schedule:Compact']
        resource = pr.get_resources_idf()
        for i in range(self.nb_profile):
            
            self.schedule_name_day = f"Occupancy_Schedule_day_profile_{i+1}"
            self.schedule_name_night = f"Occupancy_Schedule_night_profile_{i+1}"
            schedule_to_copy_day = pr.get_objects_by_names(
                                                    resource,
                                                    "Schedule:Compact",
                                                    self.schedule_name_day
                                                          )
            
            if schedule_to_copy_day[0].Name not in pr.get_objects_name_list(
                                                            self.building.idf,
                                                            'Schedule:Compact'
                                                                        ):
                idf_schedules.append(schedule_to_copy_day[0])

            
            schedule_to_copy_night = pr.get_objects_by_names(
                                                    resource,
                                                    "Schedule:Compact",
                                                    self.schedule_name_night
                                                            )
            if schedule_to_copy_night[0].Name not in pr.get_objects_name_list(
                                                            self.building.idf,
                                                            'Schedule:Compact'
                                                                        ):
                idf_schedules.append(schedule_to_copy_night[0])
            
        idf_schedules = self.building.idf.idfobjects['Schedule:Compact']
       


        self.spliter()
        self.profile_assignation()
        self.virtuosity_assignation()
        self.domotic_assignation()
        
    def post_process(self):
        pass