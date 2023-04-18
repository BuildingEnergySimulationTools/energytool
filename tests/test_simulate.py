from pathlib import Path
import numpy as np
from copy import deepcopy

from energytool.building import Building
from energytool.simulate import Simulation
from energytool.simulate import SimulationsRunner
from energytool.system import HeaterSimple

RESOURCES_PATH = Path(__file__).parent / "resources"

Building.set_idd(RESOURCES_PATH)


class TestSimulate:
    def test_simulation_runner(self):
        building = Building(idf_path=RESOURCES_PATH / "test.idf")
        gas_boiler = HeaterSimple(
            name="Main_boiler", cop=0.5, building=building, zones="*"
        )
        building.heating_system = {gas_boiler.name: gas_boiler}

        simu = Simulation(
            building=building,
            epw_file_path=RESOURCES_PATH / "Paris_2020.epw",
        )

        simu_runner = SimulationsRunner(simu_list=[simu])

        simu_runner.run()

        to_test = simu.building.building_results.sum().to_numpy()[0]

        # Single run
        assert np.floor(to_test) == np.floor(124267494239.0)

        # Multirun
        building2 = deepcopy(building)

        building2.heating_system["Main_boiler"].cop = 1

        simu2 = Simulation(
            building=building2,
            epw_file_path=RESOURCES_PATH / "Paris_2020.epw",
        )

        simu_runner = SimulationsRunner(simu_list=[simu, simu2], nb_simu_per_batch=1)

        simu_runner.run()

        to_test1 = simu.building.building_results.sum().to_numpy()[0]
        to_test2 = simu2.building.building_results.sum().to_numpy()[0]

        assert np.floor(to_test1) == np.floor(124267494239.0)
        assert np.floor(to_test2) == np.floor(62133747119.00)
