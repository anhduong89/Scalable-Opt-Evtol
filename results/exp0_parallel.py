from solverClingoAPI import MSMAP, Schedule, BaselineSchedule, ComputeUnServedCustomers
from instances.gen_instance import GenRq, InitLoc
from utils.utils import EstimateMinAgents, EstimateMinAgentsGivenSegmentsAndCustomers
import csv
import pandas as pd
import os
from encoding.baseline_py import GreedyAlg, GreedyAlg2
import math
import pickle
def CreateInstance():
    nb_sample = 5
    i_n = 0
    for nb_rq in [10, 20, 50, 100, 150, 200]:
        nb_agent, nb_segment = EstimateMinAgents(
                                                    horizon=180, b_init=0, demand_cust=nb_rq, 
                                                    aircraft_capacity=4, random_cust=False)
        for smp in range(nb_sample):
            rq_file = f'T_ITS2025/instances/exp0/rq_ins{i_n}_rq{nb_rq}_agent{nb_agent}_seg{nb_segment}_smp{smp}.lp'
            init_file = f'T_ITS2025/instances/exp0/init_ins{i_n}_rq{nb_rq}_agent{nb_agent}_seg{nb_segment}_smp{smp}.lp'
            # Create rq_file and init_file (delete if exist, then create empty)
            for file_path in [rq_file, init_file]:
                if os.path.exists(file_path):
                    os.remove(file_path)
                with open(file_path, 'w') as f:
                    pass


            InitLoc(nAgents=nb_agent, out_file=init_file)
            GenRq(cust=nb_rq, out_file=rq_file)
            i_n += 1
def run_alg(alg, nb_sample=5):
    import os
    import csv
    from solverClingoAPI import BaselineSchedule, Schedule, ComputeUnServedCustomers
    from utils.utils import EstimateMinAgents
    network_file = 'T_ITS2025/instances/network_NY_0.lp'
    o1 = f"T_ITS2025/optional/o1.lp"
    o2 = f"T_ITS2025/optional/o2.lp"
    h1 = f"T_ITS2025/optional/h1.lp"
    h2 = f"T_ITS2025/optional/h2.lp"
    local_results = []
    local_i_n = 0
    for nb_rq in [10, 20, 50, 100, 150, 200]:
        for smp in range(nb_sample):
            nb_agent, nb_segment = EstimateMinAgents(
                horizon=180, b_init=0, demand_cust=nb_rq, 
                aircraft_capacity=4, random_cust=False)
            rq_file = f'T_ITS2025/instances/exp0/rq_ins{local_i_n}_rq{nb_rq}_agent{nb_agent}_seg{nb_segment}_smp{smp}.lp'
            init_file = f'T_ITS2025/instances/exp0/init_ins{local_i_n}_rq{nb_rq}_agent{nb_agent}_seg{nb_segment}_smp{smp}.lp'
            result = {
                "nb_agent": nb_agent,
                "nb_rq": nb_rq,
                "nb_segment": nb_segment
            }
            heuristic = alg[2] is not None
            print(f" Running with instance {local_i_n} algorithm {alg[0]} nb_agent={nb_agent}, nb_rq={nb_rq}, nb_segment={nb_segment} sample={smp}")
            if alg[0] == 'Greedy':
                s = BaselineSchedule(
                    time_limit=300,
                    nb_agents=nb_agent,
                    nb_rq=nb_rq,
                    max_segment=nb_segment,
                    rq_file=rq_file,
                    init_file=init_file
                )
            else:
                s = Schedule(
                    time_limit=300,
                    update_time_limit=None,
                    nb_agents=nb_agent,
                    nb_rq=nb_rq,
                    max_segment=nb_segment,
                    encoding='T_ITS2025/schedule.lp',
                    network='T_ITS2025/instances/network_NY_0.lp',
                    rq_file=rq_file,
                    init_file=init_file,
                    choose_heu=alg[2],
                    choose_opt=alg[1],
                    dl_theory=True,
                    horizon=180,
                    heuristic=heuristic,
                )
            s.Solving()
            if hasattr(s, 'models') and len(s.models) > 0:
                model = s.models[-1]
            else:
                print(f"Warning: No answer set found. Skipping this configuration.")
                result.update({
                    f"served_customers_{alg[0]}": 'TO',
                    f"profit_{alg[0]}": 'TO',
                    f"run_time_{alg[0]}": 300
                })
                local_results.append(result)
                local_i_n += 1
                continue
            unserved_customers = ComputeUnServedCustomers(
                model.flight_path_fact_format, 
                network_file=network_file,
                init_file=init_file, rq_file=rq_file)
            result.update({
                f"served_customers_{alg[0]}": round((nb_rq*42 - unserved_customers)*100/(nb_rq*42)),
                f"profit_{alg[0]}": round(model.profit),
                f"run_time_{alg[0]}": round(model.run_time)
            })
            print({
                f"served_customers_{alg[0]}": round((nb_rq*42 - unserved_customers)*100/(nb_rq*42)),
                f"profit_{alg[0]}": round(model.profit),
                f"run_time_{alg[0]}": round(model.run_time)
            })
            csv_file = f'exp0_{alg[0]}.csv'
            write_header = not os.path.exists(csv_file) or os.stat(csv_file).st_size == 0
            if write_header:
                with open(csv_file, mode='a', newline='') as file:
                    writer = csv.DictWriter(file, fieldnames=result.keys())
                    writer.writeheader()
            with open(csv_file, mode='a', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=result.keys())
                writer.writerow(result)
            local_results.append(result)
            local_i_n += 1
    return local_results

def _run_alg_with_sample(args):
    alg, nb_sample = args
    return run_alg(alg, nb_sample)

def RunExp0(save_to_csv=True):
    save_result = []
    i_n = 0
    o1 = f"T_ITS2025/optional/o1.lp"
    o2 = f"T_ITS2025/optional/o2.lp"
    h1 = f"T_ITS2025/optional/h1.lp"
    h2 = f"T_ITS2025/optional/h2.lp"
    nb_sample = 5
    import concurrent.futures

    algs = [
        ("Greedy", None, None),
        ("O1", [o1], None),
        ("O2", [o2], None),
        ("H1", None, [h1]),
        ("H2", None, [h2]),
        ("O1H2", [o1], [h2]),
        ("O2H2", [o2], [h2])
    ]

    with concurrent.futures.ProcessPoolExecutor() as executor:
        all_results = list(executor.map(_run_alg_with_sample, [(alg, nb_sample) for alg in algs]))
    # Optionally flatten and combine all_results if needed

    # Optionally, save all combined results to a single file if needed
    # with open('exp0_all_results.pkl', 'wb') as f:
    #     pickle.dump(save_result, f)

if __name__ == "__main__":
    RunExp0()