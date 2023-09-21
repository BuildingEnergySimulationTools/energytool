import numpy as np
import pandas as pd
from scipy.stats.qmc import LatinHypercube
import datetime as dt
from copy import deepcopy
import itertools

import plotly.graph_objects as go

from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.model_selection import cross_val_score
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor

from energytool.simulate import Simulation
from energytool.simulate import SimulationsRunner
from energytool.epluspostprocess import get_aggregated_indicator

from modelitool.measure import time_series_control

from fastprogress.fastprogress import force_console_behavior

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
        sampling_method="LatinHypercube",
    ):
        self.building = building
        self.parameters = parameter_list
        self.epw_file_path = epw_file_path
        self.simulation_start = simulation_start
        self.simulation_stop = simulation_stop
        self.timestep_per_hour = timestep_per_hour
        self.sampling_method = sampling_method
        self.sample = np.empty(shape=(0, len(parameter_list)))
        self.sample_simulation_list = []
        if sampling_method == "LatinHypercube":
            self.sampling_method = LatinHypercube

    def get_boundary_sample(self):
        iter_index = list(itertools.product([0, 1], repeat=len(self.parameters)))

        return np.array(
            [
                [par.bounds[i] for par, i in zip(self.parameters, line)]
                for line in iter_index
            ]
        )

    def add_sample(
        self,
        sample_size,
        seed=None,
        run_directory=None,
        nb_cpus=-1,
        nb_simu_per_batch=5,
    ):
        sampler = LatinHypercube(d=len(self.parameters), seed=seed)
        new_sample = sampler.random(n=sample_size)
        new_sample_value = np.empty(shape=(0, len(self.parameters)))
        for s in new_sample:
            new_sample_value = np.vstack(
                (
                    new_sample_value,
                    [
                        param.bounds[0] + val * (param.bounds[1] - param.bounds[0])
                        for param, val in zip(self.parameters, s)
                    ],
                )
            )

        if self.sample.size == 0:
            bound_sample = self.get_boundary_sample()
            new_sample_value = np.vstack((new_sample_value, bound_sample))

        prog_bar = progress_bar(range(new_sample_value.shape[0]))
        for mb, simul in zip(prog_bar, new_sample_value):
            simu_building = deepcopy(self.building)
            for val, param in zip(simul, self.parameters):
                param.building = simu_building
                param.set_value(val)

            self.sample_simulation_list.append(
                Simulation(
                    building=simu_building,
                    epw_file_path=self.epw_file_path,
                    simulation_start=self.simulation_start,
                    simulation_stop=self.simulation_stop,
                    timestep_per_hour=self.timestep_per_hour,
                )
            )

        simulation_runner = SimulationsRunner(
            simu_list=self.sample_simulation_list[-new_sample_value.shape[0]:],
            run_dir=run_directory,
            nb_cpus=nb_cpus,
            nb_simu_per_batch=nb_simu_per_batch,
        )

        simulation_runner.run()

        self.sample = np.vstack((self.sample, new_sample_value))

    def plot_sample(
        self,
        results_group="building_results",
        indicator="Total",
        reference=None,
        title=None,
        x_label=None,
        y_label=None,
        alpha=0.5,
    ):
        if not self.sample_simulation_list:
            raise ValueError("No simulation found, use add_sample() to " "get a sample")

        y_df = pd.concat(
            [
                getattr(sim.building, results_group)[indicator]
                for sim in self.sample_simulation_list
            ]
        )

        fig = go.Figure()
        fig.add_trace(
            go.Scattergl(
                name="Sample",
                mode="markers",
                x=y_df.index,
                y=y_df,
                marker=dict(
                    color=f"rgba(135, 135, 135, {alpha})",
                ),
            )
        )

        if reference is not None:
            reference = time_series_control(reference).squeeze()
            fig.add_trace(
                go.Scattergl(
                    name="Reference",
                    mode="lines",
                    x=reference.index,
                    y=reference,
                    line=dict(color="crimson", width=2),
                )
            )

        if title is not None:
            fig.update_layout(title=title)
        if y_label is not None:
            fig.update_layout(yaxis_title=y_label)

        if x_label is not None:
            fig.update_layout(xaxis_title=x_label)

        fig.show()


class SurrogateModel:
    def __init__(self, simulation_sampler):
        self.simulation_sampler = simulation_sampler
        self.x_scaler = StandardScaler()
        self.y_scaler = StandardScaler()
        self.infos = {}

        self.model_dict = {
            "Tree_regressor": RandomForestRegressor(),
            "Random_forest": RandomForestRegressor(),
            "Linear_regression": LinearRegression(),
            "Linear_second_order": Pipeline(
                [("poly", PolynomialFeatures(2)), ("Line_reg", LinearRegression())]
            ),
            "Linear_third_order": Pipeline(
                [("poly", PolynomialFeatures(3)), ("Line_reg", LinearRegression())]
            ),
            "Support_Vector": SVR(),
            "Multi_layer_perceptron": MLPRegressor(max_iter=3000),
        }

    def _get_first_building(self):
        if not self.simulation_sampler.sample_simulation_list:
            raise ValueError("No building and simulation results available")

        return self.simulation_sampler.sample_simulation_list[0].building

    @property
    def parameters_boundaries(self):
        return [param.bounds for param in self.simulation_sampler.parameters]

    @property
    def available_building_indicators(self):
        first_build = self._get_first_building()
        available = list(first_build.building_results.columns)
        available.append("Total")
        return available

    @property
    def available_energyplus_indicators(self):
        first_build = self._get_first_building()
        available = list(first_build.energyplus_results.columns)
        return available

    def add_samples(
        self,
        sample_size,
        seed=None,
        run_directory=None,
        nb_cpus=-1,
        nb_simu_per_batch=5,
    ):
        self.simulation_sampler.add_sample(
            sample_size, seed, run_directory, nb_cpus, nb_simu_per_batch
        )

    def fit_sample(
        self,
        indicator="Total",
        results_group="building_results",
        start=None,
        end=None,
        metrics_method=mean_squared_error,
        aggregation_method=np.sum,
        method_args=None,
        reference=None,
        custom_series=None,
        verbose=True,
        random_state=None,
        test_size=0.2,
        cv=10,
    ):
        if custom_series is None:
            y_array = get_aggregated_indicator(
                simulation_list=self.simulation_sampler.sample_simulation_list,
                results_group=results_group,
                indicator=indicator,
                method=aggregation_method,
                reference=reference,
                method_args=method_args,
                start=start,
                end=end,
            )

        else:
            y_array = time_series_control(custom_series)

        x_scaled = self.x_scaler.fit_transform(self.simulation_sampler.sample)
        y_scaled = self.y_scaler.fit_transform(np.reshape(y_array, (-1, 1)))
        y_scaled = y_scaled.flatten()

        xs_train, xs_test, ys_train, ys_test = train_test_split(
            x_scaled, y_scaled, test_size=test_size, random_state=random_state
        )

        for key, mod in self.model_dict.items():
            mod.fit(xs_train, ys_train)

        score_dict = {}
        for key, mod in self.model_dict.items():
            cv_scores = cross_val_score(
                mod, xs_train, ys_train, scoring="neg_mean_squared_error", cv=cv
            )

            score_dict[key] = [np.mean(cv_scores), np.std(cv_scores)]
        sorted_score_dict = dict(
            sorted(score_dict.items(), key=lambda item: item[1], reverse=True)
        )

        if verbose:
            print(
                f"Cross validation neg_mean_squared_error scores"
                f"[mean, standard deviation] of {cv} folds"
            )
            print(sorted_score_dict)

        best_model_key = list(sorted_score_dict)[0]
        selected_mod = self.model_dict[best_model_key]
        ys_test_predicted = selected_mod.predict(xs_test)
        y_test = self.y_scaler.inverse_transform(np.reshape(ys_test, (-1, 1)))
        y_test_predicted = self.y_scaler.inverse_transform(
            np.reshape(ys_test_predicted, (-1, 1))
        )
        metrics_method_results = mean_squared_error(y_test, y_test_predicted)

        self.infos["best_model_key"] = best_model_key
        self.infos["metrics_method_results"] = metrics_method_results
        self.infos["metrics_method"] = metrics_method
        self.infos["indicator"] = indicator
        self.infos["results_group"] = results_group
        self.infos["aggregation_method"] = aggregation_method

        if verbose:
            print(f"{self.infos}")

    def predict(self, x_array):
        if self.infos == {}:
            raise ValueError(
                "Surrogate model is not fitted yet"
                "perform model fitting using fit_sample() method"
            )

        if x_array.ndim == 1:
            x_array = np.reshape(x_array, (1, -1))

        xs_array = self.x_scaler.transform(x_array)
        best_model = self.model_dict[self.infos["best_model_key"]]
        ys_array = best_model.predict(xs_array)
        return self.y_scaler.inverse_transform(np.reshape(ys_array, (-1, 1)))
