from pathlib import Path

from energytool.building import Building, SimuOpt
from energytool.outputs import OutputCategories
from energytool.system import HeaterSimple

RESOURCES_PATH = Path(__file__).parent / "resources"

Building.set_idd(RESOURCES_PATH)

PARAM_DICT = {
    "idf.material.Urea Formaldehyde Foam_.1327.Conductivity": 0.05,
    "system.heating.Heater.cop": 0.5,
    "epw_file": (
        Path(r"C:\EnergyPlusV9-4-0\WeatherData") / "B4R_weather_Paris_2020.epw"
    ).as_posix(),
}

SIMULATION_OPTION = {
    SimuOpt.OUTPUTS: f"{OutputCategories.SYSTEM.value}|{OutputCategories.RAW.value}"
}


class TestBuilding:
    def test_load_idf(self):
        test_build = Building(idf_path=RESOURCES_PATH / "test.idf")
        test_build.add_system(HeaterSimple(name="Heater", cop=0.1))

        res = test_build.simulate(
            parameter_dict=PARAM_DICT, simulation_options=SIMULATION_OPTION
        )

        assert test_build.zone_name_list == [
            "Block1:ApptX1W",
            "Block1:ApptX1E",
            "Block2:ApptX2W",
            "Block2:ApptX2E",
        ]

        assert test_build.surface == 200.0

        assert test_build.volume == 600.0

        assert res.sum().to_dict() == {
            "HEATING_Energy_[J]": 124442595875.44434,
            "TOTAL_SYSTEM_Energy_[J]": 124442595875.44434,
            "BLOCK1:APPTX1W:Zone Other Equipment Total Heating Energy [J](Hourly)": 18564769403.136005,
            "BLOCK1:APPTX1E:Zone Other Equipment Total Heating Energy [J](Hourly)": 18564769403.136005,
            "BLOCK2:APPTX2W:Zone Other Equipment Total Heating Energy [J](Hourly)": 18564769403.136005,
            "BLOCK2:APPTX2E:Zone Other Equipment Total Heating Energy [J](Hourly)": 18564769403.136005,
            "BLOCK1:APPTX1W IDEAL LOADS AIR:Zone Ideal Loads Supply Air Total Heating Energy [J](Hourly)": 15412078533.53048,
            "BLOCK1:APPTX1E IDEAL LOADS AIR:Zone Ideal Loads Supply Air Total Heating Energy [J](Hourly)": 15855121735.988373,
            "BLOCK2:APPTX2W IDEAL LOADS AIR:Zone Ideal Loads Supply Air Total Heating Energy [J](Hourly)": 15276675722.295742,
            "BLOCK2:APPTX2E IDEAL LOADS AIR:Zone Ideal Loads Supply Air Total Heating Energy [J](Hourly) ": 15677421945.907581,
        }
