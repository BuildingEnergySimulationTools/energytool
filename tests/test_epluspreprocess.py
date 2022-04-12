from io import StringIO
from pathlib import Path

from eppy.modeleditor import IDF

from energytool.epluspreprocess import add_output_zone_variable

RESOURCES_PATH = Path(__file__).parent / "resources"

IDF.setiddname(RESOURCES_PATH / 'Energy+.idd')


class TestEplusPreProcess:
    def test_add_output_zone_variable(self):
        empty_idf = ""
        fhandle = StringIO(empty_idf)
        toy_idf = IDF(fhandle)

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
