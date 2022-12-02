import numpy as np
from energytool.simulate import Simulation
from energytool.simulate import SimulationsRunner
from sklearn.metrics import mean_squared_error
from scipy.optimize import differential_evolution


def error_func_with_gaps(results, reference, gaps_list,
                         error_function=mean_squared_error):
    """
    Remove a list of gaps before returning the error.
    The function may be used to delete the time intervals when measurement are absent
    :param results: Pandas DataFrame or Pandas Series holding
    simulation results
    :param reference: Pandas DataFrame or Pandas Series
    holding reference measurements
    :param gaps_list: list of tuple with gap boundaries.
    Ex. [('2021-01-10', '2021-01-12'), ('2021-01-15', '2021-01-18')]
    :param error_function: error_function
    to apply (default is scikit-learn mean_square_error)
    :return: error (float)
    """
    holed_reference = reference.copy()
    holed_results = results.copy()
    for gap in gaps_list:
        remove = holed_reference.loc[gap[0]: gap[1]]
        holed_reference.drop(remove.index, inplace=True)
        remove = holed_results.loc[gap[0]: gap[1]]
        holed_results.drop(remove.index, inplace=True)

    return error_function(holed_results, holed_reference)


class Identificator:
    def __init__(self, building, parameters, error_function=None):
        self.building = building
        self.parameters = parameters
        self.parameters_id_values = {par.name: np.nan for par in parameters}
        self.optimization_results = None

        for param in self.parameters:
            param.building = self.building

        if error_function is None:
            self.error_function = mean_squared_error
        else:
            self.error_function = error_function

    def fit(
            self,
            indicator,
            reference,
            epw_file_path,
            calibration_timestep='auto',
            resampling_method=np.sum,
            simulation_start=None,
            simulation_stop=None,
            simulation_timestep_per_hour=6,
            result='building_results',
            convergence_tolerance=0.05,
            population_size=5):

        if not reference.index.inferred_type == "datetime64":
            raise ValueError("reference index dtypes must be datetime64")

        if simulation_start is None:
            simulation_start = reference.index[0]

        if simulation_stop is None:
            simulation_stop = reference.index[-1]

        reference = reference.loc[simulation_start: simulation_stop]

        # If calibration timestep is set to 'auto'
        # the method infer a Reference timestep assuming timestep is constant
        if calibration_timestep == 'auto':
            calibration_timestep = reference.index.to_series().diff()[1]
        else:
            reference = reference.resample(
                calibration_timestep).agg(resampling_method)

        simu = Simulation(self.building, epw_file_path, simulation_start,
                          simulation_stop, simulation_timestep_per_hour)

        sim_runner = SimulationsRunner([simu])

        print('Optimization started')
        print([par.name for par in self.parameters])
        print([tuple(par.bounds) for par in self.parameters])

        res = differential_evolution(
            self._objective_function,
            args=(sim_runner, result, indicator,
                  reference, calibration_timestep, resampling_method),
            bounds=[tuple(par.bounds) for par in self.parameters],
            callback=self._optimization_callback,
            tol=convergence_tolerance,
            popsize=population_size
        )

        if res['success']:
            print(f'Identification successful error function = {res["fun"]}')
            for key, val in zip(self.parameters_id_values.keys(), res["x"]):
                self.parameters_id_values[key] = val
            self.optimization_results = res
        else:
            raise ValueError("Identification failed to converge")

    def _objective_function(self, x, *args):
        (sim_runner, result, indicator, reference,
         calibration_timestep, resampling_method) = args

        for idx, param in enumerate(self.parameters):
            param.set_value(x[idx])

        sim_runner.run()

        results = getattr(self.building, result).loc[:, indicator]
        results = results.resample(calibration_timestep).agg(resampling_method)

        return self.error_function(results, reference)

    def _optimization_callback(self, xk, convergence):
        print({
            it.name: val for it, val in zip(self.parameters, xk)
        })
        print(f'convergence = {convergence}')
