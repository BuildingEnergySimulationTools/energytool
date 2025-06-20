from pathlib import Path
from tempfile import TemporaryDirectory
from pytest import approx
from energytool.building import Building, SimuOpt
from energytool.outputs import OutputCategories
from energytool.system import HeaterSimple

RESOURCES_PATH = Path(__file__).parent / "resources"

Building.set_idd(RESOURCES_PATH)


class TestBuilding:
    def test_building(self):
        test_build = Building(idf_path=RESOURCES_PATH / "test.idf")
        test_build.add_system(HeaterSimple(name="Heater", cop=0.1))

        param_dict = {
            "idf.material.Urea Formaldehyde Foam_.1327.Conductivity": 0.05,
            "system.heating.Heater.cop": 0.5,
            "epw_file": (RESOURCES_PATH / "B4R_weather_Paris_2020.epw").as_posix(),
        }
        simulation_options = {
            SimuOpt.OUTPUTS.value: f"{OutputCategories.SYSTEM.value}|{OutputCategories.RAW.value}"
        }

        res = test_build.simulate(
            parameter_dict=param_dict, simulation_options=simulation_options
        )

        assert test_build.zone_name_list == [
            "Block1:ApptX1W",
            "Block1:ApptX1E",
            "Block2:ApptX2W",
            "Block2:ApptX2E",
        ]

        assert test_build.surface == 200.0

        assert test_build.volume == 600.0

        assert res.sum().to_dict() == approx(
            {
                "HEATING_Energy_[J]": 124442595875.44434,
                "TOTAL_SYSTEM_Energy_[J]": 124442595875.44434,
                "BLOCK1:APPTX1W:"
                "Zone Other Equipment Total Heating Energy [J](Hourly)": 18564769403.136005,
                "BLOCK1:APPTX1E:"
                "Zone Other Equipment Total Heating Energy [J](Hourly)": 18564769403.136005,
                "BLOCK2:APPTX2W:"
                "Zone Other Equipment Total Heating Energy [J](Hourly)": 18564769403.136005,
                "BLOCK2:APPTX2E:"
                "Zone Other Equipment Total Heating Energy [J](Hourly)": 18564769403.136005,
                "BLOCK1:APPTX1W IDEAL LOADS AIR:"
                "Zone Ideal Loads Supply Air Total Heating Energy "
                "[J](Hourly)": 15412078533.53048,
                "BLOCK1:APPTX1E IDEAL LOADS AIR:"
                "Zone Ideal Loads Supply Air Total Heating Energy "
                "[J](Hourly)": 15855121735.988373,
                "BLOCK2:APPTX2W IDEAL LOADS AIR:"
                "Zone Ideal Loads Supply Air Total Heating Energy "
                "[J](Hourly)": 15276675722.295742,
                "BLOCK2:APPTX2E IDEAL LOADS AIR:"
                "Zone Ideal Loads Supply Air Total Heating Energy "
                "[J](Hourly) ": 15677421945.907581,
            },
            rel=0.05,
        )

        param_dict = {
            "idf.material.Urea Formaldehyde Foam_.1327.Conductivity": 0.05,
            "system.heating.Heater.cop": 0.5,
        }

        simulation_options = {
            "epw_file": (RESOURCES_PATH / "B4R_weather_Paris_2020.epw").as_posix(),
            SimuOpt.START.value: "2009-01-01",
            SimuOpt.STOP.value: "2009-02-01",
            SimuOpt.TIMESTEP.value: 15 * 60,
            SimuOpt.OUTPUTS.value: f""
            f"{OutputCategories.SYSTEM.value}|"
            f"{OutputCategories.RAW.value}",
        }

        res = test_build.simulate(
            parameter_dict=param_dict, simulation_options=simulation_options
        )

        assert res.sum().to_dict() == approx(
            {
                "HEATING_Energy_[J]": 28997691318.06697,
                "TOTAL_SYSTEM_Energy_[J]": 28997691318.06697,
                "BLOCK1:APPTX1W:"
                "Zone Other Equipment Total Heating Energy "
                "[J](Hourly)": 1627596221.6448004,
                "BLOCK1:APPTX1E:"
                "Zone Other Equipment Total Heating Energy "
                "[J](Hourly)": 1627596221.6448004,
                "BLOCK2:APPTX2W:"
                "Zone Other Equipment Total Heating Energy "
                "[J](Hourly)": 1627596221.6448004,
                "BLOCK2:APPTX2E:"
                "Zone Other Equipment Total Heating Energy "
                "[J](Hourly)": 1627596221.6448004,
                "BLOCK1:"
                "APPTX1W IDEAL LOADS AIR:Zone Ideal Loads Supply Air Total Heating Energy "
                "[J](Hourly)": 3608218979.0446877,
                "BLOCK1:APPTX1E IDEAL LOADS AIR:"
                "Zone Ideal Loads Supply Air Total Heating Energy "
                "[J](Hourly)": 3682672386.484531,
                "BLOCK2:APPTX2W IDEAL LOADS AIR:"
                "Zone Ideal Loads Supply Air Total Heating Energy "
                "[J](Hourly)": 3571575271.9865627,
                "BLOCK2:APPTX2E IDEAL LOADS AIR:"
                "Zone Ideal Loads Supply Air Total Heating Energy "
                "[J](Hourly) ": 3636379021.517704,
            },
            rel=0.05,
        )

        param_dict = {
            "Conductivity": 0.10,
            "system.heating.Heater.cop": 0.5,
        }

        param_mapping = {
            "Conductivity": [
                "idf.material.Urea Formaldehyde Foam_.1327.Conductivity",
                "idf.material.MW Glass Wool (rolls)_.0095.Conductivity",
            ]
        }

        res = test_build.simulate(
            parameter_dict=param_dict,
            simulation_options=simulation_options,
            param_mapping=param_mapping,
        )

        assert res.sum().to_dict() == approx(
            {
                "HEATING_Energy_[J]": 31800181020.40322,
                "TOTAL_SYSTEM_Energy_[J]": 31800181020.40322,
                "BLOCK1:APPTX1W:Zone Other Equipment Total Heating Energy [J](Hourly)": 1627596221.6448004,
                "BLOCK1:APPTX1E:Zone Other Equipment Total Heating Energy [J](Hourly)": 1627596221.6448004,
                "BLOCK2:APPTX2W:Zone Other Equipment Total Heating Energy [J](Hourly)": 1627596221.6448004,
                "BLOCK2:APPTX2E:Zone Other Equipment Total Heating Energy [J](Hourly)": 1627596221.6448004,
                "BLOCK1:APPTX1W IDEAL LOADS AIR:Zone Ideal Loads Supply Air Total Heating Energy [J](Hourly)": 4005689459.7009125,
                "BLOCK1:APPTX1E IDEAL LOADS AIR:Zone Ideal Loads Supply Air Total Heating Energy [J](Hourly)": 4023417664.7472544,
                "BLOCK2:APPTX2W IDEAL LOADS AIR:Zone Ideal Loads Supply Air Total Heating Energy [J](Hourly)": 3907308730.1056757,
                "BLOCK2:APPTX2E IDEAL LOADS AIR:Zone Ideal Loads Supply Air Total Heating Energy [J](Hourly) ": 3963674655.647766,
            },
            rel=0.05,
        )

    def test_save(self):
        with TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir)
            test_build = Building(idf_path=RESOURCES_PATH / "test.idf")

            # Save the model
            test_build.save(file_path / "test_model.idf")

            # Check if the saved file exists with the correct name
            saved_file_path = file_path / "test_model.idf"
            assert saved_file_path.exists()

    def test_get_initial_value(self):
        test_build = Building(idf_path=RESOURCES_PATH / "test.idf")
        string_search = "idf.DesignSpecification:OutdoorAir.Block1:ApptX1E.Outdoor_Air_Flow_Air_Changes_per_Hour"
        init_value = test_build.get_param_init_value(string_search)

        assert init_value == 3

        string_search_two_params = [
            "idf.Sizing:Zone.Block1:ApptX1E.Zone_Heating_Sizing_Factor",
            "idf.DesignSpecification:OutdoorAir.Block1:ApptX1E.Outdoor_Air_Flow_Air_Changes_per_Hour",
        ]

        init_values = test_build.get_param_init_value(string_search_two_params)

        assert init_values == [1.25, 3]
