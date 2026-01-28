import enum
import itertools
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

from multiprocessing import cpu_count

from joblib import Parallel, delayed
from fastprogress.fastprogress import progress_bar

from corrai.base.model import Model


class VariantKeys(enum.Enum):
    MODIFIER = "MODIFIER"
    ARGUMENTS = "ARGUMENTS"
    DESCRIPTION = "DESCRIPTION"


def get_modifier_dict(
    variant_dict: dict[str, dict[VariantKeys, Any]], add_existing: bool = False
):
    """
    Generate a dictionary that maps modifier values (name) to associated variant names.

    This function takes a dictionary containing variant information and extracts
    the MODIFIER values along with their corresponding variants, creating a new
    dictionary where each modifier is associated with a list of variant names
    that share that modifier.

    :param variant_dict: A dictionary containing variant information where keys are
                        variant names and values are dictionaries with keys from the
                        VariantKeys enum (e.g., MODIFIER, ARGUMENTS, DESCRIPTION).
    :param add_existing: A boolean flag indicating whether to include existing
                        variant to each modifier.
                        If True, existing modifiers will be included;
                        if False, only non-existing modifiers will be considered.
                        Set to False by default.
    :return: A dictionary that maps modifier values to lists of variant names.
    """
    temp_dict = {}

    if add_existing:
        temp_dict = {
            variant_dict[var][VariantKeys.MODIFIER]: [
                f"EXISTING_{variant_dict[var][VariantKeys.MODIFIER]}"
            ]
            for var in variant_dict.keys()
        }
        for var in variant_dict.keys():
            temp_dict[variant_dict[var][VariantKeys.MODIFIER]].append(var)
    else:
        for var in variant_dict.keys():
            modifier = variant_dict[var][VariantKeys.MODIFIER]
            if modifier not in temp_dict:
                temp_dict[modifier] = []
            temp_dict[modifier].append(var)

    return temp_dict


def get_combined_variants(
    variant_dict: dict[str, dict[VariantKeys, Any]], add_existing: bool = False
):
    """
    Generate a list of combined variants based on the provided variant dictionary.

    This function takes a dictionary containing variant information and generates a list
    of combined variants by taking the Cartesian product of the variant names.
    The resulting list contains tuples, where each tuple represents a
    combination of variant to create a unique combination.

    :param variant_dict: A dictionary containing variant information where keys are
                        variant names and values are dictionaries with keys from the
                        VariantKeys enum (e.g., MODIFIER, ARGUMENTS, DESCRIPTION).
    :param add_existing: A boolean flag indicating whether to include existing
                        variant to each modifier.
                        If True, existing modifiers will be included;
                        if False, only non-existing modifiers will be considered.
                        Set to False by default.
    :return: A list of tuples representing combined variants based on the provided
             variant dictionary.
    """
    modifier_dict = get_modifier_dict(variant_dict, add_existing)
    return list(itertools.product(*list(modifier_dict.values())))


def simulate_variants(
    model: Model,
    variant_dict: dict[str, dict[VariantKeys, Any]],
    modifier_map: dict[str, Callable],
    simulation_options: dict[str, Any],
    n_cpu: int = -1,
    add_existing: bool = False,
    custom_combinations=None,
    save_dir: Path = None,
    file_extension: str = ".txt",
    simulate_kwargs: dict = None,
):
    simulate_kwargs = simulate_kwargs or {}

    if n_cpu <= 0:
        n_cpu = max(1, cpu_count() + n_cpu)

    if custom_combinations is not None:
        combined_variants = custom_combinations
    else:
        combined_variants = get_combined_variants(variant_dict, add_existing)

    models = []

    for idx, simulation in enumerate(combined_variants, start=1):
        working_model = deepcopy(model)

        for variant in simulation:
            split_var = variant.split("_")
            if (add_existing and split_var[0] != "EXISTING") or not add_existing:
                modifier = modifier_map[variant_dict[variant][VariantKeys.MODIFIER]]
                modifier(
                    model=working_model,
                    description=variant_dict[variant][VariantKeys.DESCRIPTION],
                    **variant_dict[variant][VariantKeys.ARGUMENTS],
                )

        if save_dir:
            working_model.save((save_dir / f"Model_{idx}").with_suffix(file_extension))

        models.append(working_model)

    bar = progress_bar(models)

    results = Parallel(n_jobs=n_cpu)(
        delayed(
            lambda m: m.simulate(
                simulation_options=simulation_options, **simulate_kwargs
            )
        )(m)
        for m in bar
    )

    return results
