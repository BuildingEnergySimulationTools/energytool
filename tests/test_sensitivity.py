from pathlib import Path

import numpy as np
from corrai.sensitivity import SAnalysis

from energytool.building import Building
from energytool.system import HeaterSimple

RESOURCES_PATH = Path(__file__).parent / "resources"

Building.set_idd(RESOURCES_PATH)


class TestSensitivity:
    def test_sanalysis(self):
        building = Building(idf_path=RESOURCES_PATH / "test.idf")
        building.add_system(HeaterSimple(name="Main_boiler"))

        param_list = [
            {
                "name": "idf.material.Cast Concrete_.1.Specific_Heat",
                "interval": (800, 1200),
                "type": "Real",
            },
            {
                "name": "idf.material.Urea Formaldehyde Foam_.1327.Conductivity",
                "interval": (0.03, 0.05),
                "type": "Real",
            },
            {
                "name": "system.HEATING.Main_boiler.cop",
                "interval": (0.8, 1.2),
                "type": "Real",
            },
        ]

        simulation_options = {
            "epw_file": (RESOURCES_PATH / "Paris_2020.epw").as_posix(),
            "outputs": "SYSTEM",
        }

        sa_analysis = SAnalysis(
            method="Sobol",
            parameters_list=param_list,
        )

        sa_analysis.draw_sample(n=1)

        sa_analysis.evaluate(building, simulation_options=simulation_options, n_cpu=4)

        to_test = [elmt[2].sum().to_dict() for elmt in sa_analysis.sample_results]

        assert to_test == [
            {
                "HEATING_Energy_[J]": 62845042135.51034,
                "TOTAL_SYSTEM_Energy_[J]": 62845042135.51034,
            },
            {
                "HEATING_Energy_[J]": 62830504218.79953,
                "TOTAL_SYSTEM_Energy_[J]": 62830504218.79953,
            },
            {
                "HEATING_Energy_[J]": 62779352830.81906,
                "TOTAL_SYSTEM_Energy_[J]": 62779352830.81906,
            },
            {
                "HEATING_Energy_[J]": 52260613986.37176,
                "TOTAL_SYSTEM_Energy_[J]": 52260613986.37176,
            },
            {
                "HEATING_Energy_[J]": 52205988143.52323,
                "TOTAL_SYSTEM_Energy_[J]": 52205988143.52323,
            },
            {
                "HEATING_Energy_[J]": 52248524560.89646,
                "TOTAL_SYSTEM_Energy_[J]": 52248524560.89646,
            },
            {
                "HEATING_Energy_[J]": 62767419874.76175,
                "TOTAL_SYSTEM_Energy_[J]": 62767419874.76175,
            },
            {
                "HEATING_Energy_[J]": 52196064948.486084,
                "TOTAL_SYSTEM_Energy_[J]": 52196064948.486084,
            },
        ]

        sa_analysis.analyze(indicator="TOTAL_SYSTEM_Energy_[J]", agg_method=np.sum)

        # just check if it runs and if it gives a result. SAnalysis tests are in corrai
        assert sa_analysis.sensitivity_results is not None
