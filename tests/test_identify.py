from pathlib import Path

import pandas as pd
import datetime as dt

import energytool.system as st

from energytool.building import Building
from energytool.parameter import UncertainParameter
from energytool.identify import Identificator
from energytool.identify import error_func_with_gaps

RESOURCES_PATH = Path(__file__).parent / "resources"

Building.set_idd(RESOURCES_PATH)


class TestIdentify:
    def test_error_func_with_gaps(self):
        reference = pd.DataFrame(
            {"ref": [0, 1, 1, 0, 1, 1, 0, 0, 0]},
            index=pd.date_range('2009-01-01 00:00:00', freq="H", periods=9)
        )

        results = pd.DataFrame(
            {"ref": [0, 1, 1, 0, 1, 1, 0, 0, 0]},
            index=pd.date_range('2009-01-01 00:00:00', freq="H", periods=9)
        )

        gaps_list = [('2009-01-01 00:00:00', '2009-01-01 01:00:00'),
                     ('2009-01-01 06:00:00', '2009-01-01 09:00:00')]

        assert error_func_with_gaps(results, reference, gaps_list) == 0

    def test_identificator(self):
        reference = pd.read_csv(
            RESOURCES_PATH / "reference_calibration.csv",
            index_col=0,
            parse_dates=True)

        building = Building(idf_path=RESOURCES_PATH / "test.idf")
        building.heating_system = {
            "Main_heater": st.HeaterSimple("Old_boiler", building, cop=0.5),
        }

        param_list = [
            UncertainParameter(
                name="Boiler_COP",
                bounds=[0.3, 0.9],
                building=building,
                building_parameters=[dict(
                    category="heating_system",
                    element_name="Main_heater",
                    key="cop"
                )],
                absolute=True
            ),
        ]

        id_obj = Identificator(
            building=building,
            parameters=param_list
        )

        gaps_list = [('2009-01-01 00:00:00', '2009-01-01 01:00:00'),
                     ('2009-01-01 06:00:00', '2009-01-01 09:00:00')]

        id_obj.fit(
            reference=reference,
            epw_file_path=RESOURCES_PATH / "Paris_2020.epw",
            simulation_start=dt.datetime(2009, 1, 1, 0, 0, 0),
            simulation_stop=dt.datetime(2009, 1, 1, 23, 0, 0),
            calibration_timestep=dt.timedelta(hours=2),
            indicator='Old_boiler_Energy_[J]',
            error_function=error_func_with_gaps,
            err_func_args={"gaps_list": gaps_list},
            convergence_tolerance=0.2)

        assert round(id_obj.parameters_id_values["Boiler_COP"], 2) == 0.5
