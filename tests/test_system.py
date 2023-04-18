from pathlib import Path
import numpy as np
import pandas as pd

import pytest

from energytool.building import Building
from energytool.epluspostprocess import read_eplus_res
from energytool.simulate import Simulation, SimulationsRunner
import energytool.system as sys
import energytool.epluspreprocess as pr

RESOURCES_PATH = Path(__file__).parent / "resources"

Building.set_idd(RESOURCES_PATH)


@pytest.fixture(scope="session")
def building(tmp_path_factory):
    building = Building(idf_path=RESOURCES_PATH / "test.idf")

    return building


class TestSystems:
    def test_heater_simple(self, building):
        gas_boiler = sys.HeaterSimple(
            name="Main_boiler", cop=0.5, building=building, zones="*"
        )
        building.heating_system = {gas_boiler.name: gas_boiler}

        building.energyplus_results = read_eplus_res(RESOURCES_PATH / "test_res.csv")

        building.post_process()

        to_test = building.building_results.sum().to_numpy()[0]

        assert np.floor(to_test) == np.floor(1957968532.1269674)

    def test_ahu(self, building):
        cta = sys.AirHandlingUnit(
            name="AHU",
            building=building,
            zones=["Block1:ApptX1W", "Block1:ApptX1E"],
            ach=0.7,
            heat_recovery_efficiency=0.8,
        )

        building.ventilation_system = {cta.name: cta}

        simu = Simulation(building, epw_file_path=RESOURCES_PATH / "Paris_2020.epw")
        runner = SimulationsRunner([simu])
        runner.run()

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
        result = simu.building.building_results.AHU_Energy.sum()
        assert result == 634902466.3027192

    def test_dhw_ideal_external(self, building):
        dhw = sys.DHWIdealExternal(
            name="DHW_prod", building=building, daily_volume_occupant=30
        )

        building.dwh_system = {dhw.name: dhw}

        simu = Simulation(building, epw_file_path=RESOURCES_PATH / "Paris_2020.epw")
        runner = SimulationsRunner([simu])
        runner.run()

        result = simu.building.building_results.DHW_prod_Energy.sum()

        assert result == 8430408987.330694

    def test_ahu_control(self, building):
        ahu_control = sys.AHUControl(name="ahu_control", building=building)

        building.ventilation_system[ahu_control.name] = ahu_control

        building.pre_process()

        schedules_name_list = pr.get_objects_name_list(building.idf, "Schedule:Compact")

        design_list = [
            obj.Outdoor_Air_Schedule_Name
            for obj in building.idf.idfobjects["DesignSpecification:OutdoorAir"]
        ]

        assert "ON_24h24h_FULL_YEAR" in schedules_name_list
        assert design_list == ["ON_24h24h_FULL_YEAR"] * len(design_list)

    def test_other_equipments(self, building):
        building.other["Other_test"] = sys.OtherEquipment(
            name="test_other",
            building=building,
            zones=["Block1:ApptX1W", "Block1:ApptX1E"],
            design_level_power=10,
            add_output_variables=True,
        )

        building.pre_process()
        to_test = pr.get_objects_field_values(
            building.idf, "OtherEquipment", field_name="Design_Level"
        )
        assert to_test == ["", "", "", "", 10, 10]
        assert building.idf.getobject("Schedule:Compact", "ON_24h24h_FULL_YEAR")

        building.other["Other_test"] = sys.OtherEquipment(
            name="test_other",
            building=building,
            zones="*",
            design_level_power=20,
            compact_schedule_name="On",
            add_output_variables=True,
        )

        building.pre_process()
        to_test = pr.get_objects_field_values(
            building.idf, "OtherEquipment", field_name="Design_Level"
        )
        assert to_test == ["", "", "", "", 20, 20, 20, 20]

        df_sched = pd.Series(
            name="test_df",
            data=np.array([1] * 8760),
            index=pd.date_range("01-01-2022", periods=8760, freq="H"),
        )

        building.other["Other_test"] = sys.OtherEquipment(
            name="test_other",
            building=building,
            zones="*",
            cop=2,
            design_level_power=20,
            series_schedule=df_sched,
            add_output_variables=True,
        )

        building.pre_process()
        to_test = pr.get_objects_field_values(
            building.idf, "OtherEquipment", field_name="Design_Level"
        )
        assert to_test == ["", "", "", "", 40, 40, 40, 40]
        assert building.idf.getobject("Schedule:File", "test_df")

        building.other["Other_test"] = sys.OtherEquipment(
            name="test_other",
            building=building,
            zones="*",
            cop=2,
            design_level_power=20,
            distribute_load=True,
            series_schedule=df_sched,
            add_output_variables=True,
        )

        building.pre_process()
        to_test = pr.get_objects_field_values(
            building.idf, "OtherEquipment", field_name="Design_Level"
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
        assert building.idf.getobject("Schedule:File", "test_df")

    def test_zone_thermostat(self, building):
        building.heating_system["Thermo"] = sys.ZoneThermostat(
            name="test_thermo",
            building=building,
            zones=["Block1:ApptX1W", "Block1:ApptX1E"],
        )

        building.pre_process()
        to_test = pr.get_objects_field_values(
            building.idf,
            "ThermostatSetpoint:DualSetpoint",
            field_name="Heating_Setpoint_Temperature_Schedule_Name",
        )

        assert to_test == [
            "-60C_heating_setpoint",
            "-60C_heating_setpoint",
            "Block2:ApptX2W Heating Setpoint Schedule",
            "Block2:ApptX2E Heating Setpoint Schedule",
        ]
        assert building.idf.getobject("Schedule:Compact", "100C_cooling_setpoint")
        assert building.idf.getobject("Schedule:Compact", "-60C_heating_setpoint")

        df_sched = pd.Series(
            name="test_df",
            data=np.array([19] * 8760),
            index=pd.date_range("01-01-2022", periods=8760, freq="H"),
        )

        building.other["Thermo"] = sys.ZoneThermostat(
            building=building,
            name="test_thermo",
            zones="*",
            heating_series_schedule=df_sched,
        )

        building.pre_process()
        to_test = pr.get_objects_field_values(
            building.idf,
            "ThermostatSetpoint:DualSetpoint",
            field_name="Heating_Setpoint_Temperature_Schedule_Name",
        )
        assert to_test == ["test_df"] * 4
        assert building.idf.getobject("Schedule:File", "test_df")
        to_test = pr.get_objects_field_values(
            building.idf,
            "ThermostatSetpoint:DualSetpoint",
            field_name="Cooling_Setpoint_Temperature_Schedule_Name",
        )
        assert to_test == ["100C_cooling_setpoint"] * 4
