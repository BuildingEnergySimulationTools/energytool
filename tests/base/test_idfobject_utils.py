import pytest
from io import StringIO
from eppy.modeleditor import IDF

from energytool.base.idfobject_utils import add_output_variable


@pytest.fixture(scope="session")
def toy_idf(tmp_path_factory):
    empty_idf = ""
    handle = StringIO(empty_idf)
    toy_idf = IDF(handle)

    for toy_zone in range(10):
        toy_idf.newidfobject("Zone", Name=f"Zone_{toy_zone}", Floor_Area=10)

    return toy_idf


class TestIdfObjectUtils:
    def test_add_output_zone_variable(self, toy_idf):
        add_output_variable(toy_idf, key_values="Zone_1", variables="Conso")

        to_test = [elmt["obj"] for elmt in toy_idf.idfobjects["Output:Variable"]]
        ref = [["OUTPUT:VARIABLE", "Zone_1", "Conso", "Hourly"]]
        assert to_test == ref

        add_output_variable(toy_idf, key_values=["Zone_1", "Zone_2"], variables="Conso")

        to_test = [elmt["obj"] for elmt in toy_idf.idfobjects["Output:Variable"]]
        ref = [
            ["OUTPUT:VARIABLE", "Zone_1", "Conso", "Hourly"],
            ["OUTPUT:VARIABLE", "Zone_2", "Conso", "Hourly"],
        ]
        assert to_test == ref

        add_output_variable(toy_idf, key_values="Zone_3", variables=["Conso", "Elec"])

        to_test = [elmt["obj"] for elmt in toy_idf.idfobjects["Output:Variable"]]
        ref = [
            ["OUTPUT:VARIABLE", "Zone_1", "Conso", "Hourly"],
            ["OUTPUT:VARIABLE", "Zone_2", "Conso", "Hourly"],
            ["OUTPUT:VARIABLE", "Zone_3", "Conso", "Hourly"],
            ["OUTPUT:VARIABLE", "Zone_3", "Elec", "Hourly"],
        ]
        assert to_test == ref

        add_output_variable(toy_idf, key_values="*", variables="Conso")

        to_test = [elmt["obj"] for elmt in toy_idf.idfobjects["Output:Variable"]]
        ref = [
            ["OUTPUT:VARIABLE", "Zone_3", "Elec", "Hourly"],
            ["OUTPUT:VARIABLE", "*", "Conso", "Hourly"],
        ]
        assert to_test == ref
