from pathlib import Path

import energytool.system as st
import energytool.epluspreprocess as pr

from energytool.building import Building
from energytool.parameter import UncertainParameter
from energytool.sensitivity import SAnalysis

RESOURCES_PATH = Path(__file__).parent / "resources"

Building.set_idd(RESOURCES_PATH)


class TestSensitivity:
    def test_sanalysis(self):
        building = Building(idf_path=RESOURCES_PATH / "test.idf")
        heater = st.HeaterSimple(name="Main_boiler", building=building)
        building.heating_system = {heater.name: heater}

        material_capacity = UncertainParameter(
            name="Materials_capacity",
            bounds=[0.8, 1.2],
            building=building,
            idf_parameters=[dict(
                idf_object="Material",
                names='*',
                field="Specific_Heat"
            )]
        )

        boiler_cop = UncertainParameter(
            name="Boiler_cop",
            bounds=[0.8, 1.2],
            building=building,
            building_parameters=[dict(
                category="heating_system",
                element_name="Main_boiler",
                key="cop"
            )],
            absolute=False
        )

        material_conductivity = UncertainParameter(
            name="Material_conductivity",
            bounds=[0.8, 1.2],
            building=building,
            idf_parameters=[dict(
                idf_object="Material",
                names='*',
                field="Conductivity"
            )]
        )

        sa_analysis = SAnalysis(
            building=building,
            sensitivity_method="Sobol",
            parameters=[material_conductivity, material_capacity, boiler_cop],
        )

        sa_analysis.draw_sample(n=1)
        sa_analysis.run_simulations(
            epw_file_path=RESOURCES_PATH / "Paris_2020.epw")

        build_0 = sa_analysis.simulation_list[0].building
        assert build_0.heating_system["Main_boiler"].cop == 0.86 * 0.9875
        cond_tot_test = pr.get_objects_field_values(
            build_0.idf, "Material", "Conductivity")
        nom_values = pr.get_objects_field_values(
            building.idf, "Material", "Conductivity")
        assert cond_tot_test == [val * 0.8375 for val in nom_values]
        capa_tot_test = pr.get_objects_field_values(
            build_0.idf, "Material", "Specific_Heat")
        nom_values = pr.get_objects_field_values(
            building.idf, "Material", "Specific_Heat")
        assert capa_tot_test == [val * 0.9875 for val in nom_values]

        build_1 = sa_analysis.simulation_list[1].building
        assert build_1.heating_system["Main_boiler"].cop == 0.86 * 0.9875
        cond_tot_test = pr.get_objects_field_values(
            build_1.idf, "Material", "Conductivity")
        nom_values = pr.get_objects_field_values(
            building.idf, "Material", "Conductivity")
        assert cond_tot_test == [val * 1.0625 for val in nom_values]
        capa_tot_test = pr.get_objects_field_values(
            build_1.idf, "Material", "Specific_Heat")
        nom_values = pr.get_objects_field_values(
            building.idf, "Material", "Specific_Heat")
        assert capa_tot_test == [val * 0.9875 for val in nom_values]