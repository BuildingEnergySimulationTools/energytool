import energytool.epluspreprocess as pr
import energytool.epluspostprocess as po
import energytool.tools as tl
import numpy as np


class SummerPercentageDiscomfort:
    def __init__(self,
                 name,
                 building,
                 zones='*',
                 summer_month_begins=5,
                 summer_month_ends=8,
                 temperature_threshold=28):
        self.name = name
        self.building = building
        self.zones = zones
        self.summer_month_begins = summer_month_begins
        self.summer_month_ends = summer_month_ends
        self.temperature_threshold = temperature_threshold

    def pre_process(self):
        pr.add_output_variable(
            idf=self.building.idf,
            key_values=self.zones,
            variables="Zone Operative Temperature"
        )

        pr.add_output_variable(
            idf=self.building.idf,
            key_values=self.zones,
            variables="Zone People Occupant Count"
        )

    def post_process(self):
        year = self.building.building_results.index[0].year
        begin_loc = f"{year}-{self.summer_month_begins}"
        end_loc = f"{year}-{self.summer_month_ends}"

        zones_top = po.get_output_zone_variable(
            self.building.energyplus_results,
            "Zone Operative Temperature",
            self.zones,
        )

        zones_occupation = po.get_output_zone_variable(
            self.building.energyplus_results,
            "Zone People Occupant Count",
            self.zones,
        )

        zones_top = zones_top.loc[begin_loc:end_loc, :]
        zones_occupation = zones_occupation.loc[begin_loc:end_loc, :]

        zones_top_hot = zones_top > self.temperature_threshold
        zones_is_someone = zones_occupation > 0

        shared_zones = list(set(zones_top_hot) & set(zones_is_someone))

        zone_hot_and_someone = np.logical_and(
            zones_top_hot[shared_zones],
            zones_is_someone[shared_zones]
        )

        self.building.thermal_comfort = (
                zone_hot_and_someone.sum() / zones_is_someone.sum()) * 100
