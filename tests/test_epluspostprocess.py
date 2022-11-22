import pytest
import pandas as pd
from pathlib import Path

from energytool.epluspostprocess import zone_contains_regex
from energytool.epluspostprocess import read_eplus_res
from energytool.epluspostprocess import get_output_variable

RESOURCES_PATH = Path(__file__).parent / "resources"


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
        res = read_eplus_res(
            RESOURCES_PATH / "test_res.csv",
            ref_year=2022
        )
        res.to_csv(Path(r'C:\Users\bdurandestebe\PycharmProjects\energytool\tests\resources\expected_res2.csv'))

        pd.testing.assert_frame_equal(res, expected_res_df)

    def test_get_output_zone_variable(self):
        toy_df = pd.DataFrame({
            'ZONE1:Zone Other Equipment Total Heating Energy [J](Hourly)': [1],
            'ZONE2:Zone Other Equipment Total Heating Energy [J](Hourly)': [1],
            'ZONE3:Zone Other Equipment Total Heating Energy [J](Hourly)': [1],
            'ZONE11:Zone Other Equipment Total Heating Energy [J](Hourly)': [1],
            'ZONE1:Zone Ideal Loads Supply Air Total Heating Energy [J](Hourly)': [1],
            'ZONE2:Zone Ideal Loads Supply Air Total Heating Energy [J](Hourly)': [1],
            'ZONE3:Zone Ideal Loads Supply Air Total Heating Energy [J](Hourly)': [1],
            'ZONE11:Zone Ideal Loads Supply Air Total Heating Energy [J](Hourly)': [
                1],
        })

        pd.testing.assert_frame_equal(
            toy_df.iloc[:, 0].to_frame(),
            get_output_variable(
                eplus_res=toy_df,
                key_values='Zone1',
                variables='Equipment Total Heating Energy'
            )
        )

        pd.testing.assert_frame_equal(
            toy_df.iloc[:, :2],
            get_output_variable(
                eplus_res=toy_df,
                key_values=['Zone1', 'ZONE2'],
                variables='Equipment Total Heating Energy'
            )
        )

        pd.testing.assert_frame_equal(
            toy_df.iloc[:, :4],
            get_output_variable(
                eplus_res=toy_df,
                key_values="*",
                variables='Equipment Total Heating Energy'
            )
        )

        pd.testing.assert_frame_equal(
            toy_df.iloc[:, [0, 4]],
            get_output_variable(
                eplus_res=toy_df,
                key_values='Zone1',
                variables=[
                    'Equipment Total Heating Energy',
                    "Ideal Loads Supply Air Total Heating Energy"
                ]
            )
        )
