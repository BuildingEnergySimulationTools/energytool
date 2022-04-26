from io import StringIO
from pathlib import Path

import datetime as dt

import pytest

from eppy.modeleditor import IDF

from energytool.epluspreprocess import add_output_zone_variable
from energytool.epluspreprocess import set_run_period
from energytool.epluspreprocess import set_timestep
from energytool.epluspreprocess import set_object_field_value

RESOURCES_PATH = Path(__file__).parent / "resources"

IDF.setiddname(RESOURCES_PATH / 'Energy+.idd')


@pytest.fixture(scope="session")
def toy_idf(tmp_path_factory):
    empty_idf = ""
    handle = StringIO(empty_idf)
    return IDF(handle)


class TestEplusPreProcess:
    def test_add_output_zone_variable(self, toy_idf):

        add_output_zone_variable(toy_idf, zones='Z1', variables="Conso")

        to_test = [elmt['obj'] for elmt in
                   toy_idf.idfobjects["Output:Variable"]]
        ref = [['OUTPUT:VARIABLE', 'Z1', 'Conso', 'Hourly']]
        assert to_test == ref

        add_output_zone_variable(
            toy_idf, zones=['Z1', 'Z2'], variables="Conso")

        to_test = [elmt['obj'] for elmt in
                   toy_idf.idfobjects["Output:Variable"]]
        ref = [['OUTPUT:VARIABLE', 'Z1', 'Conso', 'Hourly'],
               ['OUTPUT:VARIABLE', 'Z2', 'Conso', 'Hourly']]
        assert to_test == ref

        add_output_zone_variable(
            toy_idf, zones='Z3', variables=["Conso", "Elec"])

        to_test = [elmt['obj'] for elmt in
                   toy_idf.idfobjects["Output:Variable"]]
        ref = [['OUTPUT:VARIABLE', 'Z1', 'Conso', 'Hourly'],
               ['OUTPUT:VARIABLE', 'Z2', 'Conso', 'Hourly'],
               ['OUTPUT:VARIABLE', 'Z3', 'Conso', 'Hourly'],
               ['OUTPUT:VARIABLE', 'Z3', 'Elec', 'Hourly']]
        assert to_test == ref

        add_output_zone_variable(toy_idf, zones='*', variables="Conso")

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

        set_run_period(
            toy_idf,
            simulation_start=dt.datetime(2009, 1, 1, 0, 0, 0),
            simulation_stop=dt.datetime(2009, 12, 31, 23, 0, 0)
        )

        to_test = toy_idf.idfobjects["RunPeriod"][0]

        assert to_test.fieldvalues == ref

    def test_set_timestep(self, toy_idf):

        ref = ['TIMESTEP', 6]

        set_timestep(toy_idf, nb_timestep_per_hour=6)
        to_test = toy_idf.idfobjects["Timestep"][0].fieldvalues

        assert to_test == ref

    def test_set_object_field_value(self, toy_idf):
        zone_list = toy_idf.idfobjects["Zone"]

        for toy_zone in range(2):
            toy_idf.newidfobject("Zone")
            zone_list[-1]["Name"] = f"Zone_{toy_zone}"

        set_object_field_value(
            idf=toy_idf,
            idf_object="Zone",
            field_name="Floor_Area",
            value=42
        )

        to_test = [z.Floor_Area for z in zone_list]

        # Test for all object
        assert to_test == [42, 42]

        # Test by object with a single Name
        set_object_field_value(
            idf=toy_idf,
            idf_object="Zone",
            idf_object_name="Zone_0",
            field_name="Floor_Area",
            value=4.2
        )

        to_test = [z.Floor_Area for z in zone_list]

        assert to_test == [4.2, 42]

        # Test by object with multiple Names
        set_object_field_value(
            idf=toy_idf,
            idf_object="Zone",
            idf_object_name=["Zone_0", "Zone_1"],
            field_name="Floor_Area",
            value=4.2
        )

        to_test = [z.Floor_Area for z in zone_list]

        assert to_test == [4.2, 4.2]

