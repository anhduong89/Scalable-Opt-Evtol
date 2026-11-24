"""Experiment driver for the exp0 scheduling benchmark.

`CreateInstance` (re)generates the `instances/exp0/` benchmark; `RunExp0` runs
every configuration over it, writing per-config result CSVs and storing each
final answer set under `results/answer_sets/`.
"""
from collections import namedtuple
import csv
import os
import pickle

from solverClingoAPI import Schedule, BaselineSchedule, ComputeUnServedCustomers
from instances.gen_instance import GenRq, InitLoc
from utils.utils import EstimateMinAgents

# --- experiment parameters -------------------------------------------------
TIME_LIMIT = 300                  # seconds per (instance, config)
HORIZON = 180                     # minutes
AIRCRAFT_CAPACITY = 4
MAX_PASSENGERS_PER_REQUEST = 42   # customers per edge a request can demand
NETWORK = "instances/network.lp"
DEMAND_SIZES = [10, 20, 50, 100, 150, 200]
NB_SAMPLE = 5

# --- optional encoding modules ---------------------------------------------
O1 = "encoding/optional/o1.lp"    # maximize revenue
O2 = "encoding/optional/o2.lp"    # minimize unserved customers
O3 = "encoding/optional/o3.lp"    # minimize empty flights
H1 = "encoding/optional/h1.lp"    # prioritize full-load flights
H2 = "encoding/optional/h2.lp"    # prioritize full-load flights, ascending segment

# A configuration = a name plus its optional optimization / heuristic modules.
Config = namedtuple("Config", ["name", "opt", "heu"])
CONFIGS = [
    Config("Greedy", None, None),
    Config("O1", [O1], None),
    Config("O2", [O2], None),
    Config("O3", [O3], None),
    Config("H1", None, [H1]),
    Config("H2", None, [H2]),
    Config("O1H2", [O1], [H2]),
    Config("O2H2", [O2], [H2]),
    Config("O3H2", [O3], [H2]),
]


def CreateInstance():
    """(Re)generate the exp0 benchmark instances (overwrites instances/exp0/)."""
    i_n = 0
    for nb_rq in DEMAND_SIZES:
        nb_agent, nb_segment = EstimateMinAgents(
            horizon=HORIZON, b_init=0, demand_cust=nb_rq,
            aircraft_capacity=AIRCRAFT_CAPACITY, random_cust=False)
        for smp in range(NB_SAMPLE):
            instance_id = f"ins{i_n}_rq{nb_rq}_agent{nb_agent}_seg{nb_segment}_smp{smp}"
            rq_file = f"instances/exp0/rq_{instance_id}.lp"
            init_file = f"instances/exp0/init_{instance_id}.lp"
            # seed per sample so the 5 samples get distinct randomized initial
            # locations; lift the per-vertiport cap so large fleets don't starve.
            InitLoc(nAgents=nb_agent, seed=smp,
                    limit_nAgents_each_vertiport=nb_agent, out_file=init_file)
            GenRq(cust=nb_rq, out_file=rq_file)
            i_n += 1


def SaveAnswerSet(config_name, instance_id, schedule, out_dir="results/answer_sets"):
    """Store the final answer set (flight + dl atoms) for one (instance, config)
    pair as a loadable .lp file: results/answer_sets/<config>/as_<instance_id>.lp
    """
    dir_path = os.path.join(out_dir, config_name)
    os.makedirs(dir_path, exist_ok=True)
    out_path = os.path.join(dir_path, f"as_{instance_id}.lp")
    with open(out_path, "w") as f:
        # schedule is space-separated facts, each already ending in '.'
        f.write("\n".join(schedule.split()) + "\n")
    return out_path


def _build_solver(config, nb_agent, nb_rq, nb_segment, rq_file, init_file):
    if config.name == "Greedy":
        return BaselineSchedule(time_limit=TIME_LIMIT, nb_agents=nb_agent, nb_rq=nb_rq,
                                max_segment=nb_segment, rq_file=rq_file, init_file=init_file)
    return Schedule(time_limit=TIME_LIMIT, update_time_limit=None, nb_agents=nb_agent,
                    nb_rq=nb_rq, max_segment=nb_segment, encoding="encoding/schedule.lp",
                    network=NETWORK, rq_file=rq_file, init_file=init_file,
                    choose_heu=config.heu, choose_opt=config.opt, dl_theory=True,
                    horizon=HORIZON, heuristic=config.heu is not None)


def _served_pct(nb_rq, unserved):
    total = nb_rq * MAX_PASSENGERS_PER_REQUEST
    return round((total - unserved) * 100 / total)


def run_config(config, instance_id, nb_agent, nb_rq, nb_segment, rq_file, init_file,
               as_dir="results/answer_sets"):
    """Solve one (instance, config), save its answer set, and return a result row."""
    print(f"Running {config.name} on {instance_id}")
    result = {"nb_agent": nb_agent, "nb_rq": nb_rq, "nb_segment": nb_segment}
    solver = _build_solver(config, nb_agent, nb_rq, nb_segment, rq_file, init_file)
    solver.Solving()
    if solver.models:
        model = solver.models[-1]
        SaveAnswerSet(config.name, instance_id,
                      model.schedule or model.flight_path_fact_format, out_dir=as_dir)
        unserved = ComputeUnServedCustomers(model.flight_path_fact_format, NETWORK,
                                            init_file, rq_file, verbose=False)
        result.update({
            f"served_customers_{config.name}": _served_pct(nb_rq, unserved),
            f"profit_{config.name}": round(model.profit),
            f"run_time_{config.name}": round(model.run_time),
        })
    else:
        print("  No answer set found (timeout).")
        result.update({
            f"served_customers_{config.name}": "TO",
            f"profit_{config.name}": "TO",
            f"run_time_{config.name}": TIME_LIMIT,
        })
    print("  ", {k: v for k, v in result.items() if config.name in k})
    return result


def _append_csv(csv_file, result):
    write_header = not os.path.exists(csv_file) or os.stat(csv_file).st_size == 0
    with open(csv_file, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=result.keys())
        if write_header:
            writer.writeheader()
        writer.writerow(result)


def RunExp0(save_to_csv=True):
    """Run every configuration over the full exp0 benchmark (Tables I & II)."""
    for config in CONFIGS:
        csv_file = f"results/exp0_{config.name}.csv"
        rows = []
        i_n = 0  # instance index resets per config (each config reruns the same instances)
        for nb_rq in DEMAND_SIZES:
            for smp in range(NB_SAMPLE):
                nb_agent, nb_segment = EstimateMinAgents(
                    horizon=HORIZON, b_init=0, demand_cust=nb_rq,
                    aircraft_capacity=AIRCRAFT_CAPACITY, random_cust=False)
                instance_id = f"ins{i_n}_rq{nb_rq}_agent{nb_agent}_seg{nb_segment}_smp{smp}"
                rq_file = f"instances/exp0/rq_{instance_id}.lp"
                init_file = f"instances/exp0/init_{instance_id}.lp"
                result = run_config(config, instance_id, nb_agent, nb_rq, nb_segment,
                                    rq_file, init_file)
                if save_to_csv:
                    _append_csv(csv_file, result)
                rows.append(result)
                i_n += 1
        if save_to_csv:
            with open(f"{csv_file}.pkl", "wb") as f:
                pickle.dump(rows, f)


def RunSingleExp0(config, nb_agent, nb_rq, nb_segment, rq_file, init_file):
    """Run a single (instance, config); instance_id is derived from the rq filename."""
    instance_id = os.path.splitext(os.path.basename(rq_file))[0]
    if instance_id.startswith("rq_"):
        instance_id = instance_id[len("rq_"):]
    return run_config(config, instance_id, nb_agent, nb_rq, nb_segment, rq_file, init_file)


if __name__ == "__main__":
    RunExp0()
