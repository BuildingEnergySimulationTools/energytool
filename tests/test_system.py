from pathlib import Path
import pandas as pd
import numpy as np

import pytest
from eppy.modeleditor import IDF
from copy import deepcopy

from energytool.base.idf_utils import get_named_objects_field_values
from energytool.base.idfobject_utils import get_objects_name_list
from energytool.base.parse_results import read_eplus_res
from energytool.building import Building
from energytool.system import (
    SystemCategories,
    HeaterSimple,
    HeatingAuxiliary,
    AirHandlingUnit,
    DHWIdealExternal,
    ArtificialLighting,
    AHUControl,
    OtherEquipment,
)

RESOURCES_PATH = Path(__file__).parent / "resources"

Building.set_idd(RESOURCES_PATH)


@pytest.fixture(scope="session")
def idf(tmp_path_factory):
    return IDF((RESOURCES_PATH / "test.idf").as_posix())


class TestSystems:
    def test_heater_simple(self, idf):
        gas_boiler = HeaterSimple(
            name="Main_boiler",
            cop=0.5,
            zones=["Block1:ApptX1W", "Block1:ApptX1E"],
        )
        gas_boiler.pre_process(idf)

        assert idf.model.dt["output:variable".upper()] == [
            [
                "OUTPUT:VARIABLE",
                "*",
                "Zone Other Equipment Total Heating Energy",
                "Hourly",
            ],
            [
                "OUTPUT:VARIABLE",
                "Block1:ApptX1W Ideal Loads Air",
                "Zone Ideal Loads Supply Air Total Heating Energy",
                "Hourly",
            ],
            [
                "OUTPUT:VARIABLE",
                "Block1:ApptX1E Ideal Loads Air",
                "Zone Ideal Loads Supply Air Total Heating Energy",
                "Hourly",
            ],
        ]

        energyplus_results = read_eplus_res(RESOURCES_PATH / "test_res.csv")

        res = gas_boiler.post_process(eplus_results=energyplus_results)

        pd.testing.assert_series_equal(
            res.sum(), pd.Series({"Main_boiler_Energy_[J]": 978973922.4169228})
        )

    def test_heating_auxiliary(self):
        idf = IDF((RESOURCES_PATH / "test.idf").as_posix())

        aux = HeatingAuxiliary(name="Heating_aux", zones="Block1:ApptX1W")

        aux.pre_process(idf)

        assert idf.model.dt["output:variable".upper()] == [
            [
                "OUTPUT:VARIABLE",
                "*",
                "Zone Other Equipment Total Heating Energy",
                "Hourly",
            ],
            [
                "OUTPUT:VARIABLE",
                "Block1:ApptX1W Ideal Loads Air",
                "Zone Ideal Loads Supply Air Total Heating Energy",
                "Hourly",
            ],
        ]
        energyplus_results = read_eplus_res(RESOURCES_PATH / "test_res.csv")

        res = aux.post_process(eplus_results=energyplus_results)

        pd.testing.assert_series_equal(
            res.sum(), pd.Series({"Heating_aux_Energy_[J]": 12234297.18460})
        )

    def test_ahu(self):
        building = Building(idf_path=RESOURCES_PATH / "test.idf")
        building.add_system(
            AirHandlingUnit(
                name="AHU",
                zones=["Block1:ApptX1W", "Block1:ApptX1E"],
                ach=0.7,
                heat_recovery_efficiency=0.8,
            )
        )

        building.systems[SystemCategories.VENTILATION][0].pre_process(building.idf)

        # Preprocess test
        ilas_list = building.idf.idfobjects["ZoneHVAC:IdealLoadsAirSystem"]

        assert [ilas.Heat_Recovery_Type for ilas in ilas_list] == [
            "Sensible",
            "Sensible",
            "None",
            "None",
        ]

        assert [ilas.Sensible_Heat_Recovery_Effectiveness for ilas in ilas_list] == [
            0.8,
            0.8,
            "",
            "",
        ]

        assert [ilas.Latent_Heat_Recovery_Effectiveness for ilas in ilas_list] == [
            0.8,
            0.8,
            "",
            "",
        ]

        design_list = building.idf.idfobjects["DesignSpecification:OutdoorAir"]

        assert [
            design.Outdoor_Air_Flow_Air_Changes_per_Hour for design in design_list
        ] == [0.7, 0.7, 3.0, 3.0]

        # Post Process tests
        results = building.simulate(
            parameter_dict={},
            simulation_options={
                "epw_file": (RESOURCES_PATH / "Paris_2020.epw").as_posix(),
                "outputs": "SYSTEM",
            },
        )

        assert results.sum().to_dict() == {
            "TOTAL_SYSTEM_Energy_[J]": 634902466.3027192,
            "VENTILATION_Energy_[J]": 634902466.3027192,
        }

    def test_dhw_ideal_external(self):
        building = Building(idf_path=RESOURCES_PATH / "test.idf")
        building.add_system(DHWIdealExternal(name="DHW_prod", daily_volume_occupant=30))

        results = building.simulate(
            parameter_dict={},
            simulation_options={
                "epw_file": (RESOURCES_PATH / "Paris_2020.epw").as_posix(),
                "outputs": "SYSTEM",
            },
        )

        assert results.sum().to_dict() == {
            "DHW_Energy_[J]": 8430408987.330694,
            "TOTAL_SYSTEM_Energy_[J]": 8430408987.330694,
        }

    def test_artificial_lighting(self):
        building = Building(idf_path=RESOURCES_PATH / "test.idf")
        building.add_system(ArtificialLighting(name="Lights"))

        results = building.simulate(
            parameter_dict={},
            simulation_options={
                "epw_file": (RESOURCES_PATH / "Paris_2020.epw").as_posix(),
                "outputs": "SYSTEM",
            },
        )

        assert results.sum().to_dict() == {
            "LIGHTING_Energy_[J]": 11899767559.680002,
            "TOTAL_SYSTEM_Energy_[J]": 11899767559.680002,
        }

    def test_ahu_control(self):
        building = Building(idf_path=RESOURCES_PATH / "test.idf")
        building.add_system(AHUControl(name="ahu_control"))
        building.add_system(AirHandlingUnit(name="AHU"))

        building.systems[SystemCategories.VENTILATION][0].pre_process(building.idf)

        schedules_name_list = get_objects_name_list(building.idf, "Schedule:Compact")

        design_list = [
            obj.Outdoor_Air_Schedule_Name
            for obj in building.idf.idfobjects["DesignSpecification:OutdoorAir"]
        ]

        assert "ON_24h24h_FULL_YEAR" in schedules_name_list
        assert design_list == ["ON_24h24h_FULL_YEAR"] * len(design_list)

        data_frame = pd.DataFrame(
            {
                "schedule_1": [0.5] * 8760,
                "schedule_2": [2] * 8760,
            },
            index=pd.date_range("2009-01-01", freq="H", periods=8760),
        )

        building.del_system("ahu_control")
        building.add_system(
            AHUControl(
                name="ahu_control",
                control_strategy="DataFrame",
                time_series=data_frame["schedule_1"],
            )
        )

        results = building.simulate(
            parameter_dict={},
            simulation_options={
                "epw_file": (RESOURCES_PATH / "Paris_2020.epw").as_posix(),
                "outputs": "SYSTEM",
            },
        )

        assert results.sum().to_dict() == {
            "TOTAL_SYSTEM_Energy_[J]": 5800244198.831992,
            "VENTILATION_Energy_[J]": 5800244198.831992,
        }

    def test_other_equipments(self):
        tested_idf = IDF(RESOURCES_PATH / "test.idf")
        other_system = OtherEquipment(
            name="other_equipment",
            zones=["Block1:ApptX1W", "Block1:ApptX1E"],
            design_level_power=10,
            add_output_variables=True,
        )

        copied_idf = deepcopy(tested_idf)
        other_system.pre_process(copied_idf)
        to_test = get_named_objects_field_values(
            copied_idf, "OtherEquipment", field_name="Design_Level"
        )
        assert to_test == ["", "", "", "", 10, 10]
        assert copied_idf.getobject("Schedule:Compact", "ON_24h24h_FULL_YEAR")

        other_system = OtherEquipment(
            name="test_other",
            zones="*",
            design_level_power=20,
            compact_schedule_name="On",
            add_output_variables=True,
        )

        copied_idf = deepcopy(tested_idf)
        other_system.pre_process(copied_idf)
        to_test = get_named_objects_field_values(
            copied_idf, "OtherEquipment", field_name="Design_Level"
        )
        assert to_test == ["", "", "", "", 20, 20, 20, 20]

        df_sched = pd.Series(
            name="test_df",
            data=np.array([1] * 8760),
            index=pd.date_range("01-01-2022", periods=8760, freq="H"),
        )

        other_system = OtherEquipment(
            name="test_other",
            zones="*",
            cop=2,
            design_level_power=20,
            time_series=df_sched,
            add_output_variables=True,
        )

        copied_idf = deepcopy(tested_idf)
        other_system.pre_process(copied_idf)
        to_test = get_named_objects_field_values(
            copied_idf, "OtherEquipment", field_name="Design_Level"
        )
        assert to_test == ["", "", "", "", 40, 40, 40, 40]
        assert copied_idf.getobject("Schedule:File", "test_df")

        other_system = OtherEquipment(
            name="test_other",
            zones="*",
            cop=2,
            design_level_power=20,
            distribute_load=True,
            time_series=df_sched,
            add_output_variables=True,
        )

        copied_idf = deepcopy(tested_idf)
        other_system.pre_process(copied_idf)
        to_test = get_named_objects_field_values(
            copied_idf, "OtherEquipment", field_name="Design_Level"
        )
        assert to_test == [
            "",
            "",
            "",
            "",
            9.999999999999996,
            10.000000000000002,
            10.000000000000002,
            10.0,
        ]
        assert copied_idf.getobject("Schedule:File", "test_df")

    #
    # def test_zone_thermostat(self, building):
    #     building.heating_system["Thermo"] = sys.ZoneThermostat(
    #         name="test_thermo",
    #         building=building,
    #         zones=["Block1:ApptX1W", "Block1:ApptX1E"],
    #     )
    #
    #     building.pre_process()
    #     to_test = energytool.base.idf_utils.get_named_objects_field_values(
    #         building.idf,
    #         "ThermostatSetpoint:DualSetpoint",
    #         field_name="Heating_Setpoint_Temperature_Schedule_Name",
    #     )
    #
    #     assert to_test == [
    #         "-60C_heating_setpoint",
    #         "-60C_heating_setpoint",
    #         "Block2:ApptX2W Heating Setpoint Schedule",
    #         "Block2:ApptX2E Heating Setpoint Schedule",
    #     ]
    #     assert building.idf.getobject("Schedule:Compact", "100C_cooling_setpoint")
    #     assert building.idf.getobject("Schedule:Compact", "-60C_heating_setpoint")
    #
    #     df_sched = pd.Series(
    #         name="test_df",
    #         data=np.array([19] * 8760),
    #         index=pd.date_range("01-01-2022", periods=8760, freq="H"),
    #     )
    #
    #     building.other["Thermo"] = sys.ZoneThermostat(
    #         building=building,
    #         name="test_thermo",
    #         zones="*",
    #         heating_series_schedule=df_sched,
    #     )
    #
    #     building.pre_process()
    #     to_test = energytool.base.idf_utils.get_named_objects_field_values(
    #         building.idf,
    #         "ThermostatSetpoint:DualSetpoint",
    #         field_name="Heating_Setpoint_Temperature_Schedule_Name",
    #     )
    #     assert to_test == ["test_df"] * 4
    #     assert building.idf.getobject("Schedule:File", "test_df")
    #     to_test = energytool.base.idf_utils.get_named_objects_field_values(
    #         building.idf,
    #         "ThermostatSetpoint:DualSetpoint",
    #         field_name="Cooling_Setpoint_Temperature_Schedule_Name",
    #     )
    #     assert to_test == ["100C_cooling_setpoint"] * 4
