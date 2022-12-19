import numpy as np
from scipy.stats.qmc import LatinHypercube
import datetime as dt

from copy import deepcopy
from fastprogress.fastprogress import force_console_behavior

from energytool.simulate import Simulation
from energytool.simulate import SimulationsRunner

master_bar, progress_bar = force_console_behavior()


class SimulationSampler:
    def __init__(
            self,
            building,
            parameter_list,
            epw_file_path,
            simulation_start=dt.datetime(2009, 1, 1, 0, 0, 0),
            simulation_stop=dt.datetime(2009, 12, 31, 23, 0, 0),
            timestep_per_hour=6,
            sampling_method='LatinHypercube'):

        self.building = building
        self.parameters = parameter_list
        self.epw_file_path = epw_file_path
        self.simulation_start = simulation_start
        self.simulation_stop = simulation_stop
        self.timestep_per_hour = timestep_per_hour
        self.sampling_method = sampling_method
        self.sample = np.empty(shape=(0, len(parameter_list)))
        self.sample_simulation_list = []
        if sampling_method == 'LatinHypercube':
            self.sampling_method = LatinHypercube

    def add_sample(self,
                   sample_size,
                   seed=None,
                   run_directory=None,
                   nb_cpus=-1,
                   nb_simu_per_batch=5):

        sampler = LatinHypercube(d=len(self.parameters), seed=seed)
        new_sample = sampler.random(n=sample_size)
        new_sample_value = np.empty(shape=(0, len(self.parameters)))
        for s in new_sample:
            new_sample_value = np.vstack((
                new_sample_value,
                [param.bounds[0] + val * (param.bounds[1] - param.bounds[0])
                 for param, val in zip(self.parameters, s)]
            ))

        prog_bar = progress_bar(range(new_sample_value.shape[0]))
        for mb, simul in zip(prog_bar, new_sample_value):
            simu_building = deepcopy(self.building)
            for val, param in zip(simul, self.parameters):
                param.building = simu_building
                param.set_value(val)

            self.sample_simulation_list.append(Simulation(
                building=simu_building,
                epw_file_path=self.epw_file_path,
                simulation_start=self.simulation_start,
                simulation_stop=self.simulation_stop,
                timestep_per_hour=self.timestep_per_hour
            ))

        simulation_runner = SimulationsRunner(
            simu_list=self.sample_simulation_list[-sample_size:],
            run_dir=run_directory,
            nb_cpus=nb_cpus,
            nb_simu_per_batch=nb_simu_per_batch
        )

        simulation_runner.run()

        self.sample = np.vstack((self.sample, new_sample_value))


class SurrogateModel:
    def __init__(
            self,
            parameter_list,
    ):
        pass
