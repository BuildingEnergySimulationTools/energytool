# -*- coding: utf-8 -*-
"""
Created on Fri Sep  2 09:05:12 2022

@author: p.roger
"""
import energytool.tools as tl
import energytool.epluspreprocess as pr

#%% Thermostat
class Thermostat:
    
    def  __init__(self,
                  building,
                  housing,
                  year,
                  heating_temperature_set,
                  cooling_temperature_set):
        
        self.building = building
        self.idf = building.idf
        self.virtuous_rate = housing[3]
        self.housing = housing
        self.year = year
        self.heating_temperature_set = heating_temperature_set
        self.cooling_temperature_set = cooling_temperature_set

        
    def schedule_generation(self):
        
        h_st_schedule_name = f"{self.housing[0]} {self.housing[2]}"\
                    f" vituouse rate {self.virtuous_rate} heatpoint schedule" 
        h_st_new_schedule = tl.Scheduler(
                                        name=h_st_schedule_name,
                                        year=self.year
                                        )
        
        c_st_schedule_name = f"{self.housing[0]} {self.housing[2]}"\
                    f" vituouse rate {self.virtuous_rate} cooltpoint schedule" 
        c_st_new_schedule = tl.Scheduler(
                                        name=c_st_schedule_name,
                                        year=self.year
                                        )
                                         
        heat_week_day = {
                        7: self.heating_temperature_set[1],
                        18: self.heating_temperature_set[0],
                        24: self.heating_temperature_set[1],
                        }
        
        heat_weekend = {24:self.heating_temperature_set[1]}
        heat_summer = {24: -50}

        h_st_new_schedule.add_day_in_period(
            start=f"{self.year}-01-01",
            end=f"{self.year}-12-31",
            days=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
            hourly_dict=heat_week_day
                                            )

        h_st_new_schedule.add_day_in_period(
            start=f"{self.year}-01-01",
            end=f"{self.year}-12-31",
            days=['Saturday', 'Sunday'],
            hourly_dict=heat_weekend
                                            )
        
        h_st_new_schedule.add_day_in_period(
            start=f"{self.year}-04-01",
            end=f"{self.year}-09-30",
            days=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                  'Saturday', 'Sunday'],
            hourly_dict=heat_summer
                                            )
        
        cool_week_day = {
                        7: self.cooling_temperature_set[1],
                        18: self.cooling_temperature_set[0],
                        24: self.cooling_temperature_set[1],
                        }
        
        cool_weekend = {24:self.cooling_temperature_set[0]}
        cool_winter = {24: +100}

        c_st_new_schedule.add_day_in_period(
            start=f"{self.year}-01-01",
            end=f"{self.year}-12-31",
            days=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
            hourly_dict=cool_week_day
                                            )

        c_st_new_schedule.add_day_in_period(
            start=f"{self.year}-01-01",
            end=f"{self.year}-12-31",
            days=['Saturday', 'Sunday'],
            hourly_dict=cool_weekend
                                            )
        
        c_st_new_schedule.add_day_in_period(
        start=f"{self.year}-01-01",
        end=f"{self.year}-03-31",
        days=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
              'Saturday', 'Sunday'],
        hourly_dict=cool_winter
                                            )
        
        c_st_new_schedule.add_day_in_period(
        start=f"{self.year}-11-01",
        end=f"{self.year}-12-31",
        days=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
              'Saturday', 'Sunday'],
        hourly_dict=cool_winter
                                            )
        
        
        return(h_st_new_schedule.series,
               c_st_new_schedule.series)


    def pre_process(self):
        
        heat_new_schedule,cool_new_schedule = self.schedule_generation()
        
        pr.add_hourly_schedules_from_df(
                                        self.building.idf,
                                        heat_new_schedule,
                                        "Temperature"
                                        )
        
        pr.add_hourly_schedules_from_df(
                                        self.building.idf,
                                        cool_new_schedule,
                                        "Temperature"
                                        )
        
        
        heat_schedule_name = heat_new_schedule.name
        cool_schedule_name = cool_new_schedule.name
        
        obj_name_arg_1 = tl.select_by_strings(
            items_list=pr.get_objects_name_list(
                                        self.idf,
                                        "ThermostatSetpoint:DualSetpoint"
                                                ),
            select_by=self.housing[0]
                                                )

        obj_name_arg_2 = tl.select_by_strings(
            items_list=pr.get_objects_name_list(
                                        self.idf,
                                        "ThermostatSetpoint:DualSetpoint"
                                                ),
            select_by=self.housing[1]
                                                )

        pr.set_objects_field_values(
                    idf=self.idf,
                    idf_object="ThermostatSetpoint:DualSetpoint",
                    idf_object_names=obj_name_arg_1,
                    field_name="Heating_Setpoint_Temperature_Schedule_Name",
                    values=heat_schedule_name
                                    )
        
        pr.set_objects_field_values(
                    idf=self.idf,
                    idf_object="ThermostatSetpoint:DualSetpoint",
                    idf_object_names=obj_name_arg_1,
                    field_name="Cooling_Setpoint_Temperature_Schedule_Name",
                    values=cool_schedule_name
                                    )

        pr.set_objects_field_values(
            idf=self.idf,
            idf_object="ThermostatSetpoint:DualSetpoint",
            idf_object_names=obj_name_arg_2,
            field_name="Heating_Setpoint_Temperature_Schedule_Name",
            values=heat_schedule_name
                                    )
        
        
        pr.set_objects_field_values(
            idf=self.idf,
            idf_object="ThermostatSetpoint:DualSetpoint",
            idf_object_names=obj_name_arg_2,
            field_name="Cooling_Setpoint_Temperature_Schedule_Name",
            values=cool_schedule_name
                                    )


    def post_process(self):
        pass

#%% Internal_gain_modification
class Internal_gain_modification():
    
    def __init__(self,building,housing,power_density):
        
        self.building = building
        self.housing = housing
        self.power_density = power_density
        

           
    def pre_process(self):
            
            
        obj_name_arg_1 = tl.select_by_strings(
            items_list=pr.get_objects_name_list(
                self.building.idf, "OtherEquipment"),
            select_by=self.housing[0]
        )

        obj_name_arg_2 = tl.select_by_strings(
            items_list=pr.get_objects_name_list(
                self.building.idf, "OtherEquipment"),
            select_by=self.housing[1]
        )

        pr.set_objects_field_values(
            idf=self.building.idf,
            idf_object="OtherEquipment",
            idf_object_names=obj_name_arg_1,
            field_name="Power_per_Zone_Floor_Area",
            values=self.power_density
        )
        
        
        pr.set_objects_field_values(
            idf=self.building.idf,
            idf_object="OtherEquipment",
            idf_object_names=obj_name_arg_2,
            field_name="Power_per_Zone_Floor_Area",
            values=self.power_density
        )
            
    def post_process(self):
        pass

#%% LightModifier
class LightModifier():
    
    def __init__(self,
                 building,
                 housing,
                 ligth_power_density
                 ):
        
        self.building = building
        self.idf = building.idf
        self.housing = housing
        self.ligth_power_density = ligth_power_density
        

    def pre_process(self):
            
            obj_name_arg_1 = tl.select_by_strings(
                items_list=pr.get_objects_name_list(
                    self.building.idf, "Lights"),
                select_by=self.housing[0]
            )
            
            obj_name_arg_2 = tl.select_by_strings(
                items_list=pr.get_objects_name_list(
                    self.building.idf, "Lights"),
                select_by=self.housing[1]
            )
            
            pr.set_objects_field_values(
                idf=self.idf,
                idf_object="Lights",
                idf_object_names=obj_name_arg_1,
                field_name="Watts_per_Zone_Floor_Area",
                values=self.ligth_power_density
            )
            
            pr.set_objects_field_values(
                idf=self.idf,
                idf_object="Lights",
                idf_object_names=obj_name_arg_2,
                field_name="Watts_per_Zone_Floor_Area",
                values=self.ligth_power_density
            )
        
    def post_process(self):
            pass

#%% StoreModifier
class StoreModifier:
    
    
    def __init__(self,
                 building,
                 housing,
                 year,
                 store_setpoint,
                 store_control):
        '''
        

        Parameters
        ----------
        building : Building E+
            .
        housing : Dict
            .
        store_setpoint : float
            .
        store_control : str
            .

        Returns
        -------
        None.

        '''
        
        self.building = building
        self.idf = building.idf
        self.housing = housing
        self.domotic = housing[4]
        self.year = year
        self.store_setpoint = store_setpoint
        self.store_control = store_control
        
    def schedule_generation(self):
              
        summer_on_name = "summer_on"
        summer_on = tl.Scheduler(
                                 name=summer_on_name,
                                 year=self.year
                                 )
        
        summer_on_winter = {24:0} #off on winter
        summer_on_summer = {24:1} #on on summer
        
        summer_on.add_day_in_period(
                start=f"{self.year}-01-01",
                end=f"{self.year}-12-31",
                days=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                      'Saturday', 'Sunday'],
                hourly_dict=summer_on_winter
                                   )
        
        summer_on.add_day_in_period(
            start=f"{self.year}-05-01",
            end=f"{self.year}-09-30",
            days=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                  'Saturday', 'Sunday'],
            hourly_dict=summer_on_summer
                                     )
                
        return(summer_on.series)
    
    
    def pre_process(self):
        
        dict_temp = {}
        for i in (self.idf.idfobjects["WindowShadingControl"]):
            dict_temp[i.Zone_Name] = i.Name
            
        summer_on = self.schedule_generation()
        
        sch_already_existing = [
                           i.Name for i in self.idf.idfobjects["Schedule:File"]
                               ]
        if not summer_on.name in sch_already_existing:
            
            pr.add_hourly_schedules_from_df(
                                            self.building.idf,
                                            summer_on,
                                            "Fraction"
                                            )

        obj_name_arg_1 = tl.select_by_strings(
                                        items_list=pr.get_objects_name_list(
                                                        self.idf,
                                                        "WindowShadingControl"
                                                                            ),
                                        select_by=dict_temp[self.housing[0]]
                                             )
        
        obj_name_arg_2 = tl.select_by_strings(
                                        items_list=pr.get_objects_name_list(
                                                        self.idf,
                                                        "WindowShadingControl"
                                                                            ),
                                        select_by=dict_temp[self.housing[1]]
                                             )
        
# =============================================================================
#         tke into account of home automation via the avaibility schedule &
#                                 control type
# =============================================================================

        if self.domotic: 
            # if domotic factor True ==> always available
            #                        ==> control type = OnIfHighSolarOnWindow

            pr.set_objects_field_values(
                idf=self.idf,
                idf_object="WindowShadingControl",
                idf_object_names=obj_name_arg_1,
                field_name="Shading_Control_Type",
                values=self.store_control
            )
            
            pr.set_objects_field_values(
                idf=self.idf,
                idf_object="WindowShadingControl",
                idf_object_names=obj_name_arg_1,
                field_name="Schedule_Name",
                values=summer_on.name
            )
            
            pr.set_objects_field_values(
                idf=self.idf,
                idf_object="WindowShadingControl",
                idf_object_names=obj_name_arg_1,
                field_name="Setpoint",
                values=500
            )
            
            pr.set_objects_field_values(
                idf=self.idf,
                idf_object="WindowShadingControl",
                idf_object_names=obj_name_arg_2,
                field_name="Shading_Control_Type",
                values=self.store_control
            )
            
            pr.set_objects_field_values(
                idf=self.idf,
                idf_object="WindowShadingControl",
                idf_object_names=obj_name_arg_2,
                field_name="Schedule_Name",
                values=summer_on.name
            )
            
            pr.set_objects_field_values(
                idf=self.idf,
                idf_object="WindowShadingControl",
                idf_object_names=obj_name_arg_2,
                field_name="Setpoint",
                values=500
            )
            
        else: 
            # if domotic factor False ==> available if people present
            #                     ==> control type = OnIfHighZoneAirTemperature
            pr.set_objects_field_values(
                idf=self.idf,
                idf_object="WindowShadingControl",
                idf_object_names=obj_name_arg_1,
                field_name="Shading_Control_Type",
                values=self.store_control
            )
            
            pr.set_objects_field_values(
                idf=self.idf,
                idf_object="WindowShadingControl",
                idf_object_names=obj_name_arg_1,
                field_name="Setpoint",
                values=self.store_setpoint
            )
            
            
            if "XnX" in obj_name_arg_1: #is a night zone ? 
                sch = f"Occupancy_Schedule_night_{self.housing[2]}"
                
                pr.set_objects_field_values(
                    idf=self.idf,
                    idf_object="WindowShadingControl",
                    idf_object_names=obj_name_arg_1,
                    field_name="Schedule_Name",
                    values=sch
                )
                                                        
            else:
                sch = f"Occupancy_Schedule_day_{self.housing[2]}"
                pr.set_objects_field_values(
                    idf=self.idf,
                    idf_object="WindowShadingControl",
                    idf_object_names=obj_name_arg_1,
                    field_name="Schedule_Name",
                    values=sch
                )
                
            if "XnX" in obj_name_arg_2: #is a night zone ? 
                sch = f"Occupancy_Schedule_night_{self.housing[2]}"
                
                pr.set_objects_field_values(
                    idf=self.idf,
                    idf_object="WindowShadingControl",
                    idf_object_names=obj_name_arg_2,
                    field_name="Schedule_Name",
                    values=sch
                )
                                                        
            else:
                sch = f"Occupancy_Schedule_day_{self.housing[2]}"
                pr.set_objects_field_values(
                    idf=self.idf,
                    idf_object="WindowShadingControl",
                    idf_object_names=obj_name_arg_2,
                    field_name="Schedule_Name",
                    values=sch
                )
            
            pr.set_objects_field_values(
                idf=self.idf,
                idf_object="WindowShadingControl",
                idf_object_names=obj_name_arg_2,
                field_name="Shading_Control_Type",
                values=self.store_control
            )
            
            pr.set_objects_field_values(
                idf=self.idf,
                idf_object="WindowShadingControl",
                idf_object_names=obj_name_arg_2,
                field_name="Setpoint",
                values=self.store_setpoint
            )
            
    def post_process(self):
        pass
    

#%% VentilationModifier
class VentilationModifier:
    
    def __init__(self,
                  building,
                  housing,
                  opening_window,
                  year):
        
        self.building = building
        self.idf = building.idf
        self.housing = housing
        self.virtuous_rate = housing[3]
        self.domotic = housing[4]
        self.opening_window = opening_window
        self.year = year
    
    def schedule_generation(self):

        t_schedule_name = f"vituouse rate {self.virtuous_rate} window temperature schedule" 
        t_new_schedule = tl.Scheduler(
                                      name=t_schedule_name,
                                      year=self.year
                                      )
        
        # ventilation temperature set fonction of virtuosity
        

        
        vent_week_summer = {
                        7: self.opening_window[1],
                        17: self.opening_window[0],
                        24: self.opening_window[1],
                        }
        
        # ventilation temperature set fonction of virtuosity
        vent_week_winter = {24:100}


        t_new_schedule.add_day_in_period(
                start=f"{self.year}-01-01",
                end=f"{self.year}-12-31",
                days=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                      'Saturday', 'Sunday'],
                hourly_dict=vent_week_winter
                                        )
        
        t_new_schedule.add_day_in_period(
            start=f"{self.year}-05-01",
            end=f"{self.year}-09-30",
            days=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                  'Saturday', 'Sunday'],
            hourly_dict=vent_week_summer
                                            )
               
        summer_on_name = "summer_on"
        summer_on = tl.Scheduler(
                                 name=summer_on_name,
                                 year=self.year
                                 )
        
        summer_on_winter = {24:0} #off on winter
        summer_on_summer = {24:1} #on on summer
        
        summer_on.add_day_in_period(
                start=f"{self.year}-01-01",
                end=f"{self.year}-12-31",
                days=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                      'Saturday', 'Sunday'],
                hourly_dict=summer_on_winter
                                   )
        
        summer_on.add_day_in_period(
            start=f"{self.year}-05-01",
            end=f"{self.year}-09-30",
            days=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                  'Saturday', 'Sunday'],
            hourly_dict=summer_on_summer
                                     )
                
        return(t_new_schedule.series,
               summer_on.series)
    
    def pre_process(self):
        
        # t_schedule_name = f"vituouse rate {self.virtuous_rate} window temperature schedule"
     
        temperature_schedule,summer_on = self.schedule_generation()
        sch_already_existing = [i.Name for i in self.idf.idfobjects["Schedule:File"]]
        
        if not summer_on.name in sch_already_existing:
            
            pr.add_hourly_schedules_from_df(
                                            self.building.idf,
                                            summer_on,
                                            "Fraction"
                                            )
        if not temperature_schedule.name in sch_already_existing:
            
            pr.add_hourly_schedules_from_df(
                                            self.building.idf,
                                            temperature_schedule,
                                            "Temperature"
                                            )
  
        obj1_surface = [i for i in  self.idf.idfobjects[
                                            "AirflowNetwork:MultiZone:Surface"
                                               ] 
                if self.housing[0] in i.Surface_Name
                and "Win" in i.Surface_Name
                ]
                
        obj1_zone = [i for i in  self.idf.idfobjects[
                                            "AirflowNetwork:MultiZone:Zone"
                                               ]
                if self.housing[0] in i.Zone_Name
                ]
        
        obj2_surface = [i for i in  self.idf.idfobjects[
                                            "AirflowNetwork:MultiZone:Surface"
                                               ] 
                if self.housing[1] in i.Surface_Name
                and "Win" in i.Surface_Name]
        
        obj2_zone = [i for i in  self.idf.idfobjects[
                                            "AirflowNetwork:MultiZone:Zone"
                                               ]
                if self.housing[1] in i.Zone_Name
                ]
# =============================================================================
#         tke into account of home automation via the avaibility schedule  
# =============================================================================

        if self.domotic:
            #if domotic True ==> always available
            obj1_zone[0].Venting_Availability_Schedule_Name = summer_on.name 
                                                               
            for i in obj1_surface:
                i.Venting_Availability_Schedule_Name = summer_on.name
            
            obj2_zone[0].Venting_Availability_Schedule_Name = summer_on.name 
                                                               
            for i in obj2_surface:
                i.Venting_Availability_Schedule_Name = summer_on.name
                
        else :
            #if domotic False ==> only if people present
            if "XnX" in obj1_zone[0].Zone_Name: #is a night zone ? 
                sch = f"Occupancy_Schedule_night_{self.housing[2]}"
                obj1_zone[0].Venting_Availability_Schedule_Name = sch
                                                        
            else:
                sch = f"Occupancy_Schedule_day_{self.housing[2]}"
                obj1_zone[0].Venting_Availability_Schedule_Name = sch
                
            if "XnX" in obj2_zone[0].Zone_Name: #is a night zone ? 
                sch = f"Occupancy_Schedule_night_{self.housing[2]}"
                obj1_zone[0].Venting_Availability_Schedule_Name = sch
                                                        
            else:
                sch = f"Occupancy_Schedule_day_{self.housing[2]}"
                obj2_zone[0].Venting_Availability_Schedule_Name = sch
                
            for i in obj1_surface:
                if "XnX" in i.Surface_Name: #is a night zone ? 
                    sch = f"Occupancy_Schedule_night_{self.housing[2]}"
                    i.Venting_Availability_Schedule_Name = sch 
                    
                else:
                    sch = f"Occupancy_Schedule_day_{self.housing[2]}"
                    i.Venting_Availability_Schedule_Name = sch 
                
            for i in obj2_surface:
                if "XnX" in i.Surface_Name: #is a night zone ? 
                    sch = f"Occupancy_Schedule_night_{self.housing[2]}"
                    i.Venting_Availability_Schedule_Name = sch 
                    
                else:
                    sch = f"Occupancy_Schedule_day_{self.housing[2]}"
                    i.Venting_Availability_Schedule_Name = sch 
                    
# =============================================================================
#         tke into account of virtuosity via the temperature schedule  
# =============================================================================                    
        name = temperature_schedule.name
        for i in obj1_surface:
            i.Ventilation_Control_Zone_Temperature_Setpoint_Schedule_Name = name
            
        for i in obj2_surface:
            i.Ventilation_Control_Zone_Temperature_Setpoint_Schedule_Name = name
        
        obj1_zone[0].Ventilation_Control_Zone_Temperature_Setpoint_Schedule_Name = name
        obj2_zone[0].Ventilation_Control_Zone_Temperature_Setpoint_Schedule_Name = name
        
    def post_process(self):
        pass        

#%% MechanicalVentilationModifier
class MechanicalVentilationModifier:
    
    def __init__(self,
                  building,
                  housing,
                  opening_window,
                  year):
        
        self.building = building
        self.idf = building.idf
        self.housing = housing
        self.virtuous_rate = housing[3]
        self.domotic = housing[4]
        self.opening_window = opening_window
        self.year = year
                
    def pre_process(self):
        

        obj_name_arg_1 = tl.select_by_strings(
            items_list=pr.get_objects_name_list(
                                        self.idf,
                                        "DesignSpecification:OutdoorAir"
                                                ),
            select_by=self.housing[0]
                                                )

        obj_name_arg_2 = tl.select_by_strings(
            items_list=pr.get_objects_name_list(
                                        self.idf,
                                        "DesignSpecification:OutdoorAir"
                                                ),
            select_by=self.housing[1]
                                                )

        pr.set_objects_field_values(
                    idf=self.idf,
                    idf_object="DesignSpecification:OutdoorAir",
                    idf_object_names=obj_name_arg_1,
                    field_name="Outdoor_Air_Method",
                    values="Sum"
                                    )
        
        pr.set_objects_field_values(
                    idf=self.idf,
                    idf_object="DesignSpecification:OutdoorAir",
                    idf_object_names=obj_name_arg_2,
                    field_name="Outdoor_Air_Method",
                    values="Sum"
                                    )
        
        pr.set_objects_field_values(
                    idf=self.idf,
                    idf_object="DesignSpecification:OutdoorAir",
                    idf_object_names=obj_name_arg_1,
                    field_name="Outdoor_Airflow_per_person",
                    values=0.00416
                                    )
        
        pr.set_objects_field_values(
                    idf=self.idf,
                    idf_object="DesignSpecification:OutdoorAir",
                    idf_object_names=obj_name_arg_2,
                    field_name="Outdoor_Airflow_per_Person",
                    values=0.00416
                                    )
        
        pr.set_objects_field_values(
                    idf=self.idf,
                    idf_object="DesignSpecification:OutdoorAir",
                    idf_object_names=obj_name_arg_1,
                    field_name="Outdoor_Airflow_per_Zone_Floor_Area",
                    values=0.0007
                                    )
        
        pr.set_objects_field_values(
                    idf=self.idf,
                    idf_object="DesignSpecification:OutdoorAir",
                    idf_object_names=obj_name_arg_2,
                    field_name="Outdoor_Airflow_per_Zone_Floor_Area",
                    values=0.0007
                                    )

    def post_process(self):
        pass
    