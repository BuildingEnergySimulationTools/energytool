# -*- coding: utf-8 -*-
"""
Created on Mon Jul 25 17:08:27 2022

@author: p.roger
"""

# =========== V_220831 ============

# vérifier calendrier cooling
# poursuivre thermostat puis people
# pour le moment les profiles ont la même probabilité d'être assignée, = 1/nb_profile

# à voir à quoi sert heating availability

# verifier ques les autres apports interne ont les memes claendriers, pour l'instant pas de modif du schedule
# reste à faire : DWH 
# modifier apport interne + complexe 
# pb dans la multi simulation --> à la main ok, mais pb qd c'est fait automatiquement 
# toujours ajouter la condition de verif de calendrier redondant 
#   Ventil utilise la méthode set object 




import energytool.tools as tl
import energytool.epluspreprocess as pr
import energytool.behaviourmodifier as cm


        
class People:
    
    
    def __init__(self,
                 building,
                 density,
                 nb_profile,
                 housing,
                 year):
        
        """


        Parameters
        ----------
        density : float
            occupancy density of the area.
        occ_schedule : TYPE
            DESCRIPTION.
        virtuous_rate : float
            virtuosity score of people
        housing : string
            housing allocated to people.

        Returns
        -------
        None.

        """
        
        self.building = building
        self.idf = building.idf
        self.density = density
        self.nb_profile=nb_profile
        self.housing = housing
        self.virtuous_rate = self.housing[3]
        self.domotic = self.housing[4]
        self.year = year
        
        self.density_profile = {
                                "profile_1":(0.03),
                                "profile_2":(0.03),
                                "profile_3":(0.045),
                                "profile_4":(0.015),
                                }
        
        
        self.heating_temperature_set = {
                                        "bad":(22,22),
                                        "average":(20,20),
                                        "good":(20,18)
                                        }
        
        self.cooling_temperature_set = {
                                        "bad":(26,26),
                                        "average":(28,28),
                                        "good":(26,28)
                                        }
        
        self.power_density = {
                              "bad":(6),
                              "average":(4),
                              "good":(2)
                              }
        
        self.light_power_density = {
                                    "bad":(6),
                                    "average":(4),
                                    "good":(2)
                                    }
        
        self.store_control = {
                              True:("OnIfHighSolarOnWindow"),
                               False:("OnIfHighZoneAirTemperature")
                              }
        
        self.store_setpoint = {
                               "bad":(28),
                               "average":(26),
                               "good":(24)
                              }
        
        self.opening_window = {
                               "bad":(28,28),
                               "average":(24,24),
                               "good":(24,20)
                              }
    
    
        
    def pre_process(self):
        
        

        obj_name_arg_1 = tl.select_by_strings(
                                items_list=pr.get_objects_name_list(
                                                                    self.idf,
                                                                    "PEOPLE"
                                                                    ),
                                select_by=self.housing[0]
                                                        )
            
            
        pr.set_objects_field_values(
                        idf=self.idf,
                        idf_object="PEOPLE",
                        idf_object_names=obj_name_arg_1,
                        field_name="Number_of_People_Schedule_Name",
                        values=f"Occupancy_Schedule_night_{self.housing[2]}"
                                    )
        
        pr.set_objects_field_values(
                                idf=self.idf,
                                idf_object="PEOPLE",
                                idf_object_names=obj_name_arg_1,
                                field_name="People_per_Zone_Floor_Area",
                                values=self.density_profile[self.housing[2]]
                                    )
        
        
        obj_name_arg_2 = tl.select_by_strings(
                                items_list=pr.get_objects_name_list(
                                                                    self.idf,
                                                                    "PEOPLE"),
                                select_by=self.housing[1]
                                                )
            
            
        pr.set_objects_field_values(
                            idf=self.idf,
                            idf_object="PEOPLE",
                            idf_object_names=obj_name_arg_2,
                            field_name="Number_of_People_Schedule_Name",
                            values=f"Occupancy_Schedule_day_{self.housing[2]}"
                            )
        
        pr.set_objects_field_values(
                                idf=self.idf,
                                idf_object="PEOPLE",
                                idf_object_names=obj_name_arg_2,
                                field_name="People_per_Zone_Floor_Area",
                                values=self.density_profile[self.housing[2]]
                                    )
        
        thermo = cm.Thermostat(
                building=self.building,
                housing=self.housing,
                year=self.year,
                heating_temperature_set = self.heating_temperature_set[
                                                            self.virtuous_rate
                                                                      ],
                cooling_temperature_set = self.cooling_temperature_set[
                                                            self.virtuous_rate
                                                                      ],
                            )
        

        thermo.pre_process()
        
        internal_gain = cm.Internal_gain_modification(
                            building=self.building,
                            housing=self.housing,
                            power_density=self.power_density[
                                                            self.virtuous_rate
                                                            ],
                                                    )

        internal_gain.pre_process()
        
        lights = cm.LightModifier(
                        building=self.building,
                        housing=self.housing,
                        ligth_power_density=self.light_power_density[
                                                        self.virtuous_rate
                                                            ]
                                )
        
        lights.pre_process()
        
        store = cm.StoreModifier(
                        building=self.building,
                                housing=self.housing,
                                year=self.year,
                                store_setpoint=self.store_setpoint[
                                                            self.virtuous_rate 
                                                            ],
                                store_control=self.store_control[
                                                            self.domotic 
                                                            ],
                                )
        
        store.pre_process()
        
        ventil = cm.VentilationModifier(
                                building=self.building,
                                housing=self.housing,
                                opening_window=self.opening_window[
                                                              self.virtuous_rate
                                                                  ],
                                year=self.year
                                        )
        
        ventil.pre_process()
                                       
        
    def post_process(self):
        pass
