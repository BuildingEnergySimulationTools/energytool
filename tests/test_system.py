from pathlib import Path
import numpy as np

from energytool.building import Building
from energytool.epluspostprocess import read_eplus_res
from energytool.system import GasBoiler

RESOURCES_PATH = Path(__file__).parent / "resources"

Building.set_idd(RESOURCES_PATH)


class TestSystems:
    def test_gas_boiler(self):
        building = Building(idf_path=RESOURCES_PATH / "test.idf")
        gas_boiler = GasBoiler(
            name="Main_boiler", cop=0.5, building=building, zones='*')
        building.heating_system = {gas_boiler.name: gas_boiler}

        building.energyplus_results = read_eplus_res(
            RESOURCES_PATH / "test_res.csv")

        building.post_process()

        to_test = building.building_results.sum().to_numpy()[0]

        assert np.floor(to_test) == np.floor(1957968532.1269674)
