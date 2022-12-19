import numpy as np
from pathlib import Path

from energytool.building import Building
from energytool.parameter import UncertainParameter
from energytool.surrogate import SimulationSampler
import energytool.system as st
import datetime as dt

RESOURCES_PATH = Path(__file__).parent / "resources"

Building.set_idd(RESOURCES_PATH)


class TestSurrogate:
    def test_simulation_sampler(self):
        building = Building(idf_path=RESOURCES_PATH / "test.idf")
        heater = st.HeaterSimple(name="Main_boiler", building=building)
        building.heating_system = {heater.name: heater}

        param_list = [
            UncertainParameter(
                name="Materials_capacity",
                bounds=[0.8, 1.2],
                absolute=False,
                building=building,
                idf_parameters=[dict(
                    idf_object="Material",
                    names='*',
                    field="Specific_Heat"
                )]
            ),
            UncertainParameter(
                name="Boiler_cop",
                bounds=[0.7, 0.95],
                absolute=True,
                building=building,
                building_parameters=[dict(
                    category="heating_system",
                    element_name="Main_boiler",
                    key="cop"
                )],
            ),
        ]

        sim_sampler = SimulationSampler(
            building=building,
            parameter_list=param_list,
            epw_file_path=RESOURCES_PATH / "Paris_2020.epw",
            simulation_start=dt.datetime(2009, 1, 1, 0, 0, 0),
            simulation_stop=dt.datetime(2009, 1, 1, 23, 0, 0),
            timestep_per_hour=1,
            sampling_method='LatinHypercube'
        )

        sim_sampler.add_sample(sample_size=3, seed=42)
        sim_sampler.add_sample(sample_size=3, seed=666)

        ref = np.array([
            [0.83014, 0.91343],
            [1.08552, 0.80855],
            [1.05411, 0.70203],
            [0.83145, 0.82079],
            [0.99437, 0.89884],
            [1.15444, 0.75963]
        ])

        assert np.allclose(sim_sampler.sample, ref, atol=0.0001)


