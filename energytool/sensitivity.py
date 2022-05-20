import numpy as np
import datetime as dt
import plotly.graph_objects as go

from copy import deepcopy

from SALib.sample import saltelli
from SALib.sample import morris as morris_sampler
from SALib.analyze import morris
from SALib.analyze import sobol

from energytool.simulate import Simulation
from energytool.simulate import SimulationsRunner

from fastprogress.fastprogress import master_bar, progress_bar
from fastprogress.fastprogress import force_console_behavior

master_bar, progress_bar = force_console_behavior()


class SAnalysis:
    def __init__(self,
                 building,
                 sensitivity_method,
                 parameters):
        self.building = building
        self.sensitivity_method = sensitivity_method
        self.parameters = parameters
        self.salib_problem = {
            "num_vars": len(parameters),
            "names": [parameter.name for parameter in parameters],
            "bounds": [parameter.bounds for parameter in parameters]
        }
        self.method_map = {
            "Morris": {
                "method": morris,
                "sampling": morris_sampler
            },
            "Sobol": {
                "method": sobol,
                "sampling": saltelli,
            }
        }
        for param in self.parameters:
            param.building = building

        self.sample = np.array([])
        self.simulation_list = []
        self.sensitivity_results = None

    @property
    def available_indicators(self):
        if self.simulation_list:
            available = list(self.simulation_list[0].results.columns)
            available.append("Total")
            return available
        else:
            raise ValueError("No simulation results available")

    def draw_sample(self, n, arguments=None):
        if arguments is None:
            arguments = {}

        sampler = self.method_map[self.sensitivity_method]['sampling']
        self.sample = sampler.sample(
            N=n,
            problem=self.salib_problem,
            **arguments
        )

    def run_simulations(self,
                        epw_file_path,
                        simulation_start=dt.datetime(2009, 1, 1, 0, 0, 0),
                        simulation_stop=dt.datetime(2009, 12, 31, 23, 0, 0),
                        timestep_per_hour=6,
                        run_directory=None,
                        nb_cpus=-1,
                        nb_simu_per_batch=5):
        if self.sample.size == 0:
            raise ValueError(
                'No sample available. Generate sample using draw_sample()'
            )

        if self.simulation_list:
            self.simulation_list = []

        prog_bar = progress_bar(range(self.sample.shape[0]))
        for mb, simul in zip(prog_bar, self.sample):
            # prog_bar.comment = "Config"
            simu_building = deepcopy(self.building)
            for val, param in zip(simul, self.parameters):
                param.building = simu_building
                param.set_value(val)

            self.simulation_list.append(Simulation(
                building=simu_building,
                epw_file_path=epw_file_path,
                simulation_start=simulation_start,
                simulation_stop=simulation_stop,
                timestep_per_hour=timestep_per_hour
            ))

        simulation_runner = SimulationsRunner(
            simu_list=self.simulation_list,
            run_dir=run_directory,
            nb_cpus=nb_cpus,
            nb_simu_per_batch=nb_simu_per_batch
        )

        simulation_runner.run()

    def analyze(self,
                indicator='Total',
                aggregation_method=np.sum,
                arguments=None):

        if arguments is None:
            arguments = {}

        if indicator not in self.available_indicators:
            raise ValueError('Specified indicator not in computed outputs')

        y_array = np.array(
            [aggregation_method(simu.results[indicator])
             if indicator != "Total" else
             aggregation_method(simu.results.sum(axis=1))
             for simu in self.simulation_list
             ]
        )

        analyser = self.method_map[self.sensitivity_method]["method"]

        self.sensitivity_results = analyser.analyze(
            problem=self.salib_problem,
            Y=y_array,
            **arguments
        )


def plot_sobol_st_bar(salib_res):

    sobol_ind = salib_res.to_df()[0]
    sobol_ind.sort_values(by="ST", ascending=True, inplace=True)

    figure = go.Figure()
    figure.add_trace(go.Bar(
        x=sobol_ind.index,
        y=sobol_ind.ST,
        name="Sobol Total Indices",
        marker_color='orange',
        error_y=dict(type="data", array=sobol_ind.ST_conf.to_numpy()),
        yaxis="y1"
    ))

    figure.update_layout(
        title='Sobol Total indices',
        xaxis_title='Parameters',
        yaxis_title='Sobol total index value [0-1]'
    )

    figure.show()