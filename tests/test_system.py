from pathlib import Path
import numpy as np

import pytest

from energytool.building import Building
from energytool.epluspostprocess import read_eplus_res
from energytool.simulate import Simulation, SimulationsRunner
import energytool.system as sys

RESOURCES_PATH = Path(__file__).parent / "resources"


Building.set_idd(RESOURCES_PATH)


@pytest.fixture(scope="session")
def building(tmp_path_factory):
    building = Building(idf_path=RESOURCES_PATH / "test.idf")

    return building


class TestSystems:
    def test_gas_boiler(self, building):
        gas_boiler = sys.GasBoiler(
            name="Main_boiler", cop=0.5, building=building, zones='*')
        building.heating_system = {gas_boiler.name: gas_boiler}

        building.energyplus_results = read_eplus_res(
            RESOURCES_PATH / "test_res.csv")

        building.post_process()

        to_test = building.building_results.sum().to_numpy()[0]

        assert np.floor(to_test) == np.floor(1957968532.1269674)

    def test_ahu(self, building):
        cta = sys.AirHandlingUnit(
            name="AHU",
            building=building,
            zones=['Block1:ApptX1W', 'Block1:ApptX1E'],
            ach=0.7,
            heat_recovery_efficiency=0.8
        )

        building.ventilation_system = {
            cta.name: cta
        }

        simu = Simulation(
            building, epw_file_path=RESOURCES_PATH / "Paris_2020.epw")
        runner = SimulationsRunner([simu])
        runner.run()

        # Preprocess test
        ilas_list = building.idf.idfobjects["ZoneHVAC:IdealLoadsAirSystem"]

        assert [
                   ilas.Sensible_Heat_Recovery_Effectiveness
                   for ilas in ilas_list
               ] == [0.8, 0.8, '', '']

        assert [
                   ilas.Latent_Heat_Recovery_Effectiveness
                   for ilas in ilas_list
               ] == [0.8, 0.8, '', '']

        design_list = building.idf.idfobjects["DesignSpecification:OutdoorAir"]

        assert [
                   design.Outdoor_Air_Flow_Air_Changes_per_Hour
                   for design in design_list
               ] == [0.7, 0.7, 3., 3.]

        # Post Process tests
        assert simu.results.AHU_Energy.sum() == 634902466.3027192
