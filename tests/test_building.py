from pathlib import Path

from energytool.building import Building

RESOURCES_PATH = Path(__file__).parent / "resources"

Building.set_idd(RESOURCES_PATH)


class TestBuilding:
    def test_load_idf(self):
        test_build = Building(idf_path=RESOURCES_PATH / 'test.idf')

        assert test_build.idf.idfobjects["Building"][0].Name == "Building"
