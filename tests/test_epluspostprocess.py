import numpy as np
import pytest
import pandas as pd
from pathlib import Path
from copy import deepcopy
import datetime as dt

from sklearn.metrics import mean_absolute_error

from energytool.epluspostprocess import zone_contains_regex
from energytool.epluspostprocess import read_eplus_res
from energytool.epluspostprocess import get_output_variable
from energytool.epluspostprocess import get_aggregated_indicator
from energytool.building import Building
from energytool.simulate import Simulation
from energytool.simulate import SimulationsRunner
import energytool.system as st

RESOURCES_PATH = Path(__file__).parent / "resources"

Building.set_idd(RESOURCES_PATH)


@pytest.fixture()
def test_building():
    building = Building(idf_path=RESOURCES_PATH / "test.idf")
    building.heating_system = {
        "Main_boiler": st.HeaterSimple(
            name="Main_boiler", cop=0.5, building=building, zones="*"
        )
    }
    return building


@pytest.fixture()
def expected_res_df():
    to_return = pd.read_csv(
        RESOURCES_PATH / "expected_res.csv",
        index_col=0,
        parse_dates=True,
    )

    to_return.index.freq = "H"

    return to_return


class TestEplusPostProcess:
    def test_zone_contains_regex(self):
        test_list = ["z1", "z2"]

        out = zone_contains_regex(test_list)

        assert out == "z1:.+|z2:.+"

    def test_read_eplus_res(self, expected_res_df):
        res = read_eplus_res(RESOURCES_PATH / "test_res.csv", ref_year=2022)
        res.to_csv(RESOURCES_PATH / "expected_res2.csv")

        pd.testing.assert_frame_equal(res, expected_res_df)

    def test_get_output_zone_variable(self):
        toy_df = pd.DataFrame(
            {
                "ZONE1:Zone Other Equipment Total Heating Energy [J](Hourly)": [1],
                "ZONE2:Zone Other Equipment Total Heating Energy [J](Hourly)": [1],
                "ZONE3:Zone Other Equipment Total Heating Energy [J](Hourly)": [1],
                "ZONE11:Zone Other Equipment Total Heating Energy [J](Hourly)": [1],
                "ZONE1:Zone Ideal Loads Supply Air Total Heating Energy [J](Hourly)": [
                    1
                ],
                "ZONE2:Zone Ideal Loads Supply Air Total Heating Energy [J](Hourly)": [
                    1
                ],
                "ZONE3:Zone Ideal Loads Supply Air Total Heating Energy [J](Hourly)": [
                    1
                ],
                "ZONE11:Zone Ideal Loads Supply Air Total Heating Energy [J](Hourly)": [
                    1
                ],
            }
        )

        pd.testing.assert_frame_equal(
            toy_df.iloc[:, 0].to_frame(),
            get_output_variable(
                eplus_res=toy_df,
                key_values="Zone1",
                variables="Equipment Total Heating Energy",
            ),
        )

        pd.testing.assert_frame_equal(
            toy_df.iloc[:, :2],
            get_output_variable(
                eplus_res=toy_df,
                key_values=["Zone1", "ZONE2"],
                variables="Equipment Total Heating Energy",
            ),
        )

        pd.testing.assert_frame_equal(
            toy_df.iloc[:, :4],
            get_output_variable(
                eplus_res=toy_df,
                key_values="*",
                variables="Equipment Total Heating Energy",
            ),
        )

        pd.testing.assert_frame_equal(
            toy_df.iloc[:, [0, 4]],
            get_output_variable(
                eplus_res=toy_df,
                key_values="Zone1",
                variables=[
                    "Equipment Total Heating Energy",
                    "Ideal Loads Supply Air Total Heating Energy",
                ],
            ),
        )

    def test_get_aggregated_indicator(self, test_building):
        building_1 = deepcopy(test_building)
        building_2 = deepcopy(test_building)

        building_2.heating_system["Main_boiler"].cop = 1

        simulation_list = [
            Simulation(
                building=building_1,
                epw_file_path=RESOURCES_PATH / "Paris_2020.epw",
                simulation_start=dt.datetime(2009, 1, 1, 0, 0, 0),
                simulation_stop=dt.datetime(2009, 1, 1, 23, 0, 0),
            ),
            Simulation(
                building=building_2,
                epw_file_path=RESOURCES_PATH / "Paris_2020.epw",
                simulation_start=dt.datetime(2009, 1, 1, 0, 0, 0),
                simulation_stop=dt.datetime(2009, 1, 1, 23, 0, 0),
            ),
        ]

        simu_runner = SimulationsRunner(simulation_list)
        simu_runner.run()

        y_array = get_aggregated_indicator(
            simulation_list,
            results_group="building_results",
            indicator="Main_boiler_Energy_[J]",
        )

        assert np.allclose(y_array, np.array([1753420223, 876710111]), atol=1)

        reference = pd.Series(
            [
                0,
                33941.2937,
                271975.5795,
                508651.2222,
                717117.1405,
                889580.7383,
                1047162.749,
                17840190.19,
                16346582.77,
                15803795.42,
                15237469.78,
                14719026.81,
                14235868.06,
                13634721.19,
                13005843.81,
                12653528.3,
                12429446.14,
                12197943.51,
                11982514.25,
                11779316.55,
                11562374.54,
                11394573.02,
                11510909.51,
                0,
            ],
            index=pd.date_range("2009-01-01 00:00:00", freq="H", periods=24),
        )

        y_array = get_aggregated_indicator(
            simulation_list,
            results_group="energyplus_results",
            indicator="BLOCK1:APPTX1W IDEAL LOADS AIR:Zone Ideal Loads Supply "
            "Air Total Heating Energy [J](Hourly)",
            reference=reference,
            method=mean_absolute_error,
        )

        assert np.allclose(y_array, np.array([0, 0]), atol=1)
