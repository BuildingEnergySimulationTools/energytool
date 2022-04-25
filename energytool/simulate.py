import datetime as dt
import math
import os
import shutil
import tempfile
from pathlib import Path

from eppy.runner.run_functions import runIDFs

from energytool.epluspostprocess import read_eplus_res
from energytool.epluspreprocess import set_run_period
from energytool.epluspreprocess import set_timestep

from fastprogress.fastprogress import master_bar, progress_bar
from fastprogress.fastprogress import force_console_behavior

master_bar, progress_bar = force_console_behavior()


class SimulationConfig:
    def __init__(self,
                 building,
                 epw_file_path,
                 simulation_start=dt.datetime(2009, 1, 1, 0, 0, 0),
                 simulation_stop=dt.datetime(2009, 12, 31, 23, 0, 0),
                 timestep_per_hour=6,
                 ):
        self.building = building
        self.epw_file_path = epw_file_path
        self.simulation_start = simulation_start
        self.simulation_stop = simulation_stop
        self.timestep_per_hour = timestep_per_hour

        set_run_period(building.idf, simulation_start, simulation_stop)
        building.idf.epw = str(epw_file_path)
        set_timestep(building.idf, timestep_per_hour)


class SimulationsRunner:
    def __init__(self,
                 simu_config_list,
                 run_dir=None,
                 nb_cpus=-1,
                 nb_simu_per_batch=10):

        self.simu_config_list = simu_config_list
        self.nb_simu_per_batch = nb_simu_per_batch
        self.nb_cpus = nb_cpus

        if run_dir is None:
            run_dir = tempfile.mkdtemp()
            run_dir = Path(run_dir)

        if not os.path.exists(run_dir):
            os.mkdir(run_dir)

        self.run_dir = run_dir

    def run(self):
        # Remove existing or create result folder
        pool_path = self.run_dir / "pool_path"
        if os.path.exists(pool_path):
            shutil.rmtree(pool_path)
        os.makedirs(pool_path)

        nb_batches = math.ceil(
            len(self.simu_config_list)
            / self.nb_simu_per_batch
        )

        simu_iterator = (
            (i, elmt) for i, elmt in enumerate(self.simu_config_list))

        prog_bar = progress_bar(range(nb_batches))

        for mb, _ in zip(prog_bar, range(1, nb_batches + 1)):
            prog_bar.comment = "batch"
            runs = []
            batch_simu_list = []

            for _ in range(self.nb_simu_per_batch):

                try:
                    simu_idx, simu = next(simu_iterator)
                # Last batch may be shorter
                except StopIteration:
                    break

                simu_fold = pool_path / str(simu_idx)
                os.mkdir(simu_fold)

                batch_simu_list.append(simu_idx)
                idd_ref = simu.building.idf.idd_version

                # 1st Apply building system preprocess operation
                simu.building.pre_process()

                # Prepare E+ runs
                runs.append(
                    (
                        simu.building.idf,
                        {
                            "output_directory": str(simu_fold),
                            "annual": False,
                            "design_day": False,
                            "idd": None,
                            "epmacro": False,
                            "expandobjects": False,
                            "readvars": True,
                            "output_prefix": None,
                            "output_suffix": None,
                            "version": False,
                            "verbose": "v",
                            "ep_version": f"{idd_ref[0]}-{idd_ref[1]}-{idd_ref[2]}",

                        }
                    )
                )

            # 2nd run EnergyPlus
            try:
                runIDFs(runs, self.nb_cpus)
            except Exception as exc:
                raise exc

            for idx in batch_simu_list:
                simu_fold = pool_path / str(idx)
                current_simu = self.simu_config_list[idx]
                current_simu.building.energyplus_results = read_eplus_res(
                    file_path=simu_fold / "eplusout.csv",
                    ref_year=current_simu.simulation_start.year
                )

                # 3rd Apply system post-processing
                current_simu.building.post_process()
