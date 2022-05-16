from pathlib import Path
from copy import deepcopy

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
        ahu = st.AirHandlingUnit(name="AHU", building=building)
        building.heating_system = {heater.name: heater}
        building.ventilation_system = {ahu.name: ahu}

        building_1 = deepcopy(building)
        uncertain_parameter = UncertainParameter(
            name='test',
            building=building_1,
            bounds=[0, 1],
            idf_parameters=[dict(
                idf_object="Material",
                names=['Floor/Roof Screed_.03', 'Cast Concrete (Dense)_.1'],
                field="Conductivity"
            )],
            building_parameters=[dict(
                category="heating_system",
                element_name="Heater",
                key="cop"
            )],
            absolute=True
        )

        uncertain_parameter.set_value(value=42)

        ref_idf = [element.Conductivity
                   for element in building_1.idf.idfobjects["Material"][2:4]]

        assert ref_idf == [42] * 2
        assert building_1.heating_system['Heater'].cop == 42

        building_2 = deepcopy(building)
        uncertain_parameter = UncertainParameter(
            name='test',
            building=building_2,
            bounds=[0, 1],
            idf_parameters=[
                dict(
                    idf_object="Material",
                    names=['Floor/Roof Screed_.03',
                           'Cast Concrete (Dense)_.1'],
                    field="Conductivity"
                ),
                dict(
                    idf_object="Material",
                    names=['Gypsum Plasterboard_.025',
                           'Project medium concrete block_.2'],
                    field="Conductivity"
                ),
            ],
            building_parameters=[
                dict(
                    category="heating_system",
                    element_name="Heater",
                    key="cop"
                ),
                dict(
                    category="ventilation_system",
                    element_name="AHU",
                    key="fan_energy_coefficient"
                ),
            ],
            absolute=False
        )

        uncertain_parameter.set_value(value=42)

        ref_idf = [element.Conductivity
                   for element in building_2.idf.idfobjects["Material"][2:6]]

        assert ref_idf == [17.22, 58.8, 10.5, 21.42]
        assert building_2.heating_system['Heater'].cop == 0.86 * 42
        assert building_2.ventilation_system['AHU'].fan_energy_coefficient == 0.23 * 42
