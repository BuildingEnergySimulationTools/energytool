from io import StringIO
from pathlib import Path

import datetime as dt

import pandas as pd
import numpy as np
import pytest
import eppy

from eppy.modeleditor import IDF
from energytool.simulate import Simulation
from energytool.simulate import SimulationsRunner
from energytool.building import Building

import energytool.epluspreprocess as pr
import energytool.epluspostprocess as po

RESOURCES_PATH = Path(__file__).parent / "resources"

try:
    IDF.setiddname(RESOURCES_PATH / 'Energy+.idd')
except eppy.modeleditor.IDDAlreadySetError:
    pass


@pytest.fixture(scope="session")
def toy_idf(tmp_path_factory):
    empty_idf = ""
    handle = StringIO(empty_idf)
    toy_idf = IDF(handle)

    for toy_zone in range(10):
        toy_idf.newidfobject(
            "Zone",
            Name=f"Zone_{toy_zone}",
            Floor_Area=10
        )

    return toy_idf


class TestEplusPreProcess:
    def test_get_objects_name_list(self, toy_idf):

        to_test = pr.get_objects_name_list(toy_idf, "Zone")
        assert to_test == [f"Zone_{i}" for i in range(10)]

    def test_add_output_zone_variable(self, toy_idf):
        pr.add_output_variable(toy_idf, key_values='Z1', variables="Conso")

        to_test = [elmt['obj'] for elmt in
                   toy_idf.idfobjects["Output:Variable"]]
        ref = [['OUTPUT:VARIABLE', 'Z1', 'Conso', 'Hourly']]
        assert to_test == ref

        pr.add_output_variable(
            toy_idf, key_values=['Z1', 'Z2'], variables="Conso")

        to_test = [elmt['obj'] for elmt in
                   toy_idf.idfobjects["Output:Variable"]]
        ref = [['OUTPUT:VARIABLE', 'Z1', 'Conso', 'Hourly'],
               ['OUTPUT:VARIABLE', 'Z2', 'Conso', 'Hourly']]
        assert to_test == ref

        pr.add_output_variable(
            toy_idf, key_values='Z3', variables=["Conso", "Elec"])

        to_test = [elmt['obj'] for elmt in
                   toy_idf.idfobjects["Output:Variable"]]
        ref = [['OUTPUT:VARIABLE', 'Z1', 'Conso', 'Hourly'],
               ['OUTPUT:VARIABLE', 'Z2', 'Conso', 'Hourly'],
               ['OUTPUT:VARIABLE', 'Z3', 'Conso', 'Hourly'],
               ['OUTPUT:VARIABLE', 'Z3', 'Elec', 'Hourly']]
        assert to_test == ref

        pr.add_output_variable(toy_idf, key_values='*', variables="Conso")

        to_test = [elmt['obj'] for elmt in
                   toy_idf.idfobjects["Output:Variable"]]
        ref = [['OUTPUT:VARIABLE', 'Z3', 'Elec', 'Hourly'],
               ['OUTPUT:VARIABLE', '*', 'Conso', 'Hourly']]
        assert to_test == ref

    def test_set_run_period(self, toy_idf):
        toy_idf.newidfobject("RunPeriod")

        ref = [
            'RUNPERIOD',
            'run_period',
            1,
            1,
            2009,
            12,
            31,
            2009,
            'Thursday',
            'No',
            'No',
            'Yes',
            'Yes',
            'Yes',
            'No'
        ]

        pr.set_run_period(
            toy_idf,
            simulation_start=dt.datetime(2009, 1, 1, 0, 0, 0),
            simulation_stop=dt.datetime(2009, 12, 31, 23, 0, 0)
        )

        to_test = toy_idf.idfobjects["RunPeriod"][0]

        assert to_test.fieldvalues == ref

    def test_set_timestep(self, toy_idf):
        ref = ['TIMESTEP', 6]

        pr.set_timestep(toy_idf, nb_timestep_per_hour=6)
        to_test = toy_idf.idfobjects["Timestep"][0].fieldvalues

        assert to_test == ref

    def test_set_objects_field_values(self, toy_idf):
        zone_list = toy_idf.idfobjects["Zone"]

        pr.set_objects_field_values(
            idf=toy_idf,
            idf_object="Zone",
            field_name="Floor_Area",
            values=42
        )

        to_test = [z.Floor_Area for z in zone_list]

        # Test for all object
        assert to_test == [42] * 10

        # Test by object with a single Name
        pr.set_objects_field_values(
            idf=toy_idf,
            idf_object="Zone",
            idf_object_names="Zone_0",
            field_name="Floor_Area",
            values=4.2
        )

        to_test = [z.Floor_Area for z in zone_list]

        assert to_test == [4.2] + [42] * 9

        # Test by object with multiple Names
        pr.set_objects_field_values(
            idf=toy_idf,
            idf_object="Zone",
            idf_object_names=["Zone_0", "Zone_1"],
            field_name="Floor_Area",
            values=4.2
        )

        to_test = [z.Floor_Area for z in zone_list]

        assert to_test == [4.2, 4.2] + [42] * 8

        # Test by object with multiple Names multiple values
        pr.set_objects_field_values(
            idf=toy_idf,
            idf_object="Zone",
            idf_object_names=["Zone_0", "Zone_1"],
            field_name="Floor_Area",
            values=[33, 33]
        )

        to_test = [z.Floor_Area for z in zone_list]

        assert to_test == [33, 33] + [42] * 8

    def test_get_number_of_people(self, toy_idf):
        configurations = [
            [
                ("Number_of_People_Calculation_Method", "People/Area"),
                ("People_per_Zone_Floor_Area", 0.5)
            ],
            [
                ("Number_of_People_Calculation_Method", "People",),
                ("Number_of_People", 2)
            ],
            [
                ("Number_of_People_Calculation_Method", "Area/Person"),
                ("Zone_Floor_Area_per_Person", 2)
            ],
        ]

        for z in toy_idf.idfobjects["Zone"]:
            z.Floor_Area = 10

        zone_name_iterator = (z.Name for z in toy_idf.idfobjects["Zone"])

        for config in configurations:
            zne = next(zone_name_iterator)
            new_people = toy_idf.newidfobject(
                "People",
                Name=f"People_{zne}",
                Zone_or_ZoneList_Name=zne,
            )
            new_people[config[0][0]] = config[0][1]
            new_people[config[1][0]] = config[1][1]

        assert pr.get_number_of_people(toy_idf) == 12.

        assert pr.get_number_of_people(
            toy_idf, zones=["Zone_1", "Zone_2"]) == 7.

    def test_get_objects_by_names(self, toy_idf):
        res_to_test = pr.get_objects_by_names(
            toy_idf, "Zone", ["Zone_0", "Zone_1"])

        ref = toy_idf.idfobjects["Zone"][:2]

        assert res_to_test == ref

    def test_add_hourly_schedules_from_df(self):
        building = Building(idf_path=RESOURCES_PATH / 'test.idf')

        data_frame = pd.DataFrame({
            "schedule_1": [1] * 8760,
            "schedule_2": [2] * 8760,
        }, index=pd.date_range("2009-01-01", freq="H", periods=8760))

        pr.add_hourly_schedules_from_df(building.idf, data_frame)

        pr.add_output_variable(
            idf=building.idf,
            key_values=list(data_frame.columns),
            variables="Schedule Value")

        simu = Simulation(building,
                          epw_file_path=RESOURCES_PATH / "Paris_2020.epw")
        runner = SimulationsRunner([simu])
        runner.run()

        output = po.get_output_zone_variable(
            simu.building.energyplus_results,
            "Schedule Value",
            list(data_frame.columns),
        )

        np.testing.assert_equal(output.to_numpy(), data_frame.to_numpy())

    def test_get_objects_field_values(self):
        building = Building(idf_path=RESOURCES_PATH / 'test.idf')

        all_materials_test = pr.get_objects_field_values(
            idf=building.idf,
            idf_object="Material",
            field_name="Conductivity"
        )

        assert all_materials_test == [0.04, 1.13, 0.41, 1.4, 0.25, 0.51,
                                      0.04, 0.7, 0.04, 0.25]

        three_materials_test = pr.get_objects_field_values(
            idf=building.idf,
            idf_object="Material",
            field_name="Conductivity",
            idf_object_names=[
                'Floor/Roof Screed_.03',
                'Cast Concrete (Dense)_.1',
                'Gypsum Plasterboard_.025'
            ]
        )

        assert three_materials_test == [0.41, 1.4, 0.25]