from pathlib import Path

import pandas as pd
import pytest

from energytool.building import Building
import energytool.system as st

RESOURCES_PATH = Path(__file__).parent / "resources"

Building.set_idd(RESOURCES_PATH)


@pytest.fixture(scope="session")
def building(tmp_path_factory):
    building = Building(idf_path=RESOURCES_PATH / "test.idf")

    building.heating_system = {
        "Main_heater": st.HeaterSimple("Old_boiler", building),
        "Distribution": st.AuxiliarySimplified("Heating_aux", building)
    }

    building.dwh_system = {
        "DHW_production": st.DHWIdealExternal("Old_dhw_prod", building)
    }

    building.ventilation_system = {
        "Ventilation": st.AirHandlingUnit("Old_natural", building),
        "Ventilation_control": st.AHUControl(
            name="Constant_ventilation",
            building=building,
            schedule_name="ON_24h24h_FULL_YEAR"
        ),
        "Natural_ventilation": st.NaturalVentilation(
            "Natural_ventilation", building)
    }

    building.artificial_lighting_system = {
        "Lights": st.ArtificialLightingSimple(
            "Artificial_light", building)
    }

    building.building_results = pd.DataFrame(
        [14065759.40650512, 562630.3762602, 0., 0., 1864404.97474219],
        index=[
            'Old_boiler_Energy', 'Heating_aux_Energy', 'Old_natural_Energy',
            'Artificial_light_Energy', 'Old_dhw_prod_Energy']
    ).T

    return building


class TestBuilding:
    def test_load_idf(self):
        test_build = Building(idf_path=RESOURCES_PATH / 'test.idf')

        assert test_build.idf.idfobjects["Building"][0].Name == "Building"

    def test_system_energy_results(self, building):
        ref = pd.DataFrame(
            [14628390.37626, 0.0, 0.0, 0.0, 1.864405e+06, 0.0, 16492794.75750751],
            index=['Heating', 'Cooling', 'Ventilation', 'Lighting', 'DHW',
                   'Local_production', "Total"]).T

        pd.testing.assert_frame_equal(ref, building.system_energy_results)
