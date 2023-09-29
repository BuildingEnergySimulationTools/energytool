import pandas as pd
import numpy as np


def get_aggregated_indicator(
    simulation_list,
    results_group="building_results",
    indicator="Total",
    method=np.sum,
    method_args=None,
    reference=None,
    start=None,
    end=None,
):
    if not simulation_list:
        raise ValueError(
            "Empty simulation list. " "Cannot perform indicator aggregation"
        )

    first_build = simulation_list[0].building
    available = list(first_build.building_results.columns)
    available += list(first_build.energyplus_results.columns)
    available.append("Total")

    if indicator not in available:
        raise ValueError(
            "Indicator is not present in building_results or " "in energyplus_results"
        )

    y_df = pd.concat(
        [getattr(sim.building, results_group)[indicator] for sim in simulation_list],
        axis=1,
    )

    if start is not None:
        if end is None:
            raise ValueError("If start is specified, " "end must also be specified")
        else:
            y_df = y_df.loc[start:end]
        if reference is not None:
            reference = reference.loc[start:end]

    if reference is None:
        return method(y_df).to_numpy()

    elif method_args is None:
        return np.array(
            [method(reference, y_df.iloc[:, i]) for i in range(y_df.shape[1])]
        )

    else:
        return np.array(
            [
                method(reference, y_df.iloc[:, i], **method_args)
                for i in range(y_df.shape[1])
            ]
        )
