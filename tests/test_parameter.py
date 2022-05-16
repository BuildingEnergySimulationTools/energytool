from pathlib import Path

import energytool.system as st

from energytool.building import Building
from energytool.parameter import UncertainParameter

RESOURCES_PATH = Path(__file__).parent / "resources"

Building.set_idd(RESOURCES_PATH)

RESOURCES_PATH = Path(__file__).parent / "resources"

Building.set_idd(RESOURCES_PATH)


class TestParameter:
    def test_uncertain_parameter(self):
        building = Building(idf_path=RESOURCES_PATH / "test.idf")
        heater = st.HeaterSimple(name="Heater", building=building)
        building.heating_system = {heater.name: heater}

        uncertain_parameter = UncertainParameter(
            name='test',
            building=building,
            bounds=[0, 1],
            idf_parameters=[dict(
                idf_object="Material",
                names=['Floor/Roof Screed_.03', 'Cast Concrete (Dense)_.1'],
                field="Conductivity"
            )],
            building_parameters=[dict(
                category=building.heating_system,
                element_name="Heater",
                key="cop"
            )]
        )

        uncertain_parameter.set_value(value=42)

        ref_idf = [element.Conductivity
                   for element in building.idf.idfobjects["Material"][2:4]]

        assert ref_idf == [42] * 2
        assert building.heating_system['Heater'].cop == 42
