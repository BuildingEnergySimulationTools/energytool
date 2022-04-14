from io import StringIO
from pathlib import Path

import datetime as dt

from eppy.modeleditor import IDF

from energytool.epluspreprocess import add_output_zone_variable
from energytool.epluspreprocess import set_run_period
from energytool.epluspreprocess import set_timestep

RESOURCES_PATH = Path(__file__).parent / "resources"

IDF.setiddname(RESOURCES_PATH / 'Energy+.idd')


class TestEplusPreProcess:
    def test_add_output_zone_variable(self):
        empty_idf = ""
        handle = StringIO(empty_idf)
        toy_idf = IDF(handle)

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

    def test_set_run_period(self):
        empty_idf = ""
        handle = StringIO(empty_idf)
        toy_idf = IDF(handle)

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

    def test_set_timestep(self):
        empty_idf = ""
        handle = StringIO(empty_idf)
        toy_idf = IDF(handle)

        ref = ['TIMESTEP', 6]

        set_timestep(toy_idf, nb_timestep_per_hour=6)
        to_test = toy_idf.idfobjects["Timestep"][0].fieldvalues

        assert to_test == ref
