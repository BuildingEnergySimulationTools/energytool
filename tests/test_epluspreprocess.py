from io import StringIO
from pathlib import Path

import datetime as dt

import pytest

from eppy.modeleditor import IDF

import energytool.epluspreprocess as pr

RESOURCES_PATH = Path(__file__).parent / "resources"

IDF.setiddname(RESOURCES_PATH / 'Energy+.idd')


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
        pr.add_output_zone_variable(toy_idf, zones='Z1', variables="Conso")

        to_test = [elmt['obj'] for elmt in
                   toy_idf.idfobjects["Output:Variable"]]
        ref = [['OUTPUT:VARIABLE', 'Z1', 'Conso', 'Hourly']]
        assert to_test == ref

        pr.add_output_zone_variable(
            toy_idf, zones=['Z1', 'Z2'], variables="Conso")

        to_test = [elmt['obj'] for elmt in
                   toy_idf.idfobjects["Output:Variable"]]
        ref = [['OUTPUT:VARIABLE', 'Z1', 'Conso', 'Hourly'],
               ['OUTPUT:VARIABLE', 'Z2', 'Conso', 'Hourly']]
        assert to_test == ref

        pr.add_output_zone_variable(
            toy_idf, zones='Z3', variables=["Conso", "Elec"])

        to_test = [elmt['obj'] for elmt in
                   toy_idf.idfobjects["Output:Variable"]]
        ref = [['OUTPUT:VARIABLE', 'Z1', 'Conso', 'Hourly'],
               ['OUTPUT:VARIABLE', 'Z2', 'Conso', 'Hourly'],
               ['OUTPUT:VARIABLE', 'Z3', 'Conso', 'Hourly'],
               ['OUTPUT:VARIABLE', 'Z3', 'Elec', 'Hourly']]
        assert to_test == ref

        pr.add_output_zone_variable(toy_idf, zones='*', variables="Conso")

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

    def test_set_object_field_value(self, toy_idf):
        zone_list = toy_idf.idfobjects["Zone"]

        pr.set_object_field_value(
            idf=toy_idf,
            idf_object="Zone",
            field_name="Floor_Area",
            value=42
        )

        to_test = [z.Floor_Area for z in zone_list]

        # Test for all object
        assert to_test == [42]*10

        # Test by object with a single Name
        pr.set_object_field_value(
            idf=toy_idf,
            idf_object="Zone",
            idf_object_name="Zone_0",
            field_name="Floor_Area",
            value=4.2
        )

        to_test = [z.Floor_Area for z in zone_list]

        assert to_test == [4.2] + [42]*9

        # Test by object with multiple Names
        pr.set_object_field_value(
            idf=toy_idf,
            idf_object="Zone",
            idf_object_name=["Zone_0", "Zone_1"],
            field_name="Floor_Area",
            value=4.2
        )

        to_test = [z.Floor_Area for z in zone_list]

        assert to_test == [4.2, 4.2] + [42]*8

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
