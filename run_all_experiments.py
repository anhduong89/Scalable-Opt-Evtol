from solverClingoAPI import Schedule, BaselineSchedule, ComputeUnServedCustomers
from MSMAPSolver import MSMAP
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
o1 = f"T_ITS2025/optional/o1.lp"
o2 = f"T_ITS2025/optional/o2.lp"
h1 = f"T_ITS2025/optional/h1.lp"
h2 = f"T_ITS2025/optional/h2.lp"

# run experiment for IEEE-ITSS-2026
def RunExp0(save_to_csv=True):
    save_result = []
    # results_file = 'results_exp0.csv'
    
    # # Erase the CSV file at the beginning if it exists
    # if os.path.exists(results_file):
    #     os.remove(results_file)

    # columns = [["nb_agent", "nb_rq", "nb_segment", "served_customers", "profit", "run_time"]]

    # # Write header once at the beginning
    # with open(results_file, mode='w', newline='') as file:
    #     writer = csv.DictWriter(file, fieldnames=columns)
    #     writer.writeheader()
    i_n = 0
    network_file = 'T_ITS2025/instances/network.lp'

    nb_sample = 5
    for alg in [("Greedy", None, None),("O1",[o1],None), ("O2", [o2], None), ("H1", None, [h1]), ("H2", None, [h2]), ("O1H2", [o1], [h2]), ("O2H2", [o2], [h2])]:
        csv_file = f'exp0_{alg[0]}.csv'
        if alg[0] != 'H2':
            continue
        for nb_rq in [10, 20, 50, 100, 150, 200]:
            for smp in range(nb_sample):
                nb_agent, nb_segment = EstimateMinAgents(
                                                        horizon=180, b_init=0, demand_cust=nb_rq, 
                                                        aircraft_capacity=4, random_cust=False)
                rq_file = f'T_ITS2025/instances/exp0/rq_ins{i_n}_rq{nb_rq}_agent{nb_agent}_seg{nb_segment}_smp{smp}.lp'
                init_file = f'T_ITS2025/instances/exp0/init_ins{i_n}_rq{nb_rq}_agent{nb_agent}_seg{nb_segment}_smp{smp}.lp'
                result = {
                        "nb_agent": nb_agent,
                        "nb_rq": nb_rq,
                        "nb_segment": nb_segment}          

                
                heuristic = alg[2] is not None
                print(f" Running with instance {i_n} algorithm {alg[0]} nb_agent={nb_agent}, nb_rq={nb_rq}, nb_segment={nb_segment} sample={smp}")
                if alg[0] == 'Greedy':
                    s = BaselineSchedule(
                        time_limit=300,
                        nb_agents=nb_agent,
                        nb_rq=nb_rq,
                        max_segment=nb_segment,
                        rq_file=rq_file,
                        init_file=init_file
                    )

                    # s.Solving(print_style='default')
                else:
                    s = Schedule(
                        time_limit=300,
                        update_time_limit=None,
                        nb_agents=nb_agent,
                        nb_rq=nb_rq,
                        max_segment=nb_segment,
                        encoding='T_ITS2025/schedule.lp',
                        network='T_ITS2025/instances/network.lp',
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
                    unserved_customers = ComputeUnServedCustomers(
                                            model.flight_path_fact_format, 
                                            network_file='T_ITS2025/instances/network.lp',
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
                else:
                    print(f"Warning: No answer set found. Skipping this configuration.")
                    result.update({
                    f"served_customers_{alg[0]}": 'TO',
                    f"profit_{alg[0]}": 'TO',
                    f"run_time_{alg[0]}": 300
                    })

                # Write header if file does not exist or is empty
                
                write_header = not os.path.exists(csv_file) or os.stat(csv_file).st_size == 0
                if save_to_csv and write_header:
                    with open(csv_file, mode='a', newline='') as file:
                        writer = csv.DictWriter(file, fieldnames=result.keys())
                        writer.writeheader()
                # Append result to CSV file
                if save_to_csv == True:
                    with open(csv_file, mode='a', newline='') as file:
                        writer = csv.DictWriter(file, fieldnames=result.keys())
                        writer.writerow(result)
                save_result.append(result)
                i_n += 1
    # save save_result to file using pickle
    with open(f'{csv_file}.pkl', 'wb') as f:
        pickle.dump(save_result, f)
                
# experiments for IEEE-ITSS 2026
def RunSingleExp0(alg, nb_agent, nb_rq, nb_segment, rq_file, init_file, network_file, heuristic):
    print(f" Running with algorithm {alg[0]} and {rq_file}")
    result = {
            "nb_agent": nb_agent,
            "nb_rq": nb_rq,
            "nb_segment": nb_segment}     
    if alg[0] == 'Greedy':
        s = BaselineSchedule(
            time_limit=300,
            nb_agents=nb_agent,
            nb_rq=nb_rq,
            max_segment=nb_segment,
            rq_file=rq_file,
            init_file=init_file
        )

        # s.Solving(print_style='default')
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
    else:
        print(f"Warning: No answer set found. Skipping this configuration.")
        result.update({
        f"served_customers_{alg[0]}": 'TO',
        f"profit_{alg[0]}": 'TO',
        f"run_time_{alg[0]}": 300
        })

def Run_Single_Exp2():
    results = []
    for i in range(1):
        seed_init = i
        vert_cap = 10
        n_rq = 30
        cust_per_edge=GenRq(cust=30, random_flag=True, out_file=f'instances/100rand/rq_{i}.lp')
        
        min_agents, min_segments = EstimateMinAgents(horizon=180, b_init=15, demand_cust=cust_per_edge, random_cust=True, aircraft_capacity=4)
        print('min_agents:', min_agents)
        print('min_segments:', min_segments)
        InitLoc(nAgents=min_agents, seed=seed_init, limit_nAgents_each_vertiport=vert_cap, out_file=f'instances/100rand/init_{seed_init}.lp')
        out = MSMAP(time_limit=30, max_segment=min_segments, network='instances/network_NY.lp', rq_file=f'instances/100rand/rq_{i}.lp',
            init_file=f'instances/100rand/init_{seed_init}.lp')
        # Initialize a list to store the results

        print(f'msmap_output: {out}')
        # Collect data for each iteration
        nonzero_cust_per_edge = [x for x in cust_per_edge if x != 0]
        result_row = {
            "i": i,
            "total_cust_per_edge": sum(cust_per_edge),
            "min_cust_per_edge": min(nonzero_cust_per_edge) if nonzero_cust_per_edge else 0,
            "max_cust_per_edge": max(cust_per_edge),
            "median_cust_per_edge": sorted(cust_per_edge)[len(cust_per_edge) // 2],
            "mean_cust_per_edge": sum(cust_per_edge) / len(cust_per_edge) if cust_per_edge else 0,
            "agents": min_agents,
            "segments": min_segments,
            "msmap_output": out  # Assuming MSMAP has an 'output' attribute or method
        }
        # # Append to CSV after each iteration
        # write_header = i == 0
        # with open('results_exp2.csv', mode='a', newline='') as file:
        #     writer = csv.DictWriter(file, fieldnames=["i", "total_cust_per_edge", "min_cust_per_edge", "max_cust_per_edge", "median_cust_per_edge", "mean_cust_per_edge", "agents", "segments", "msmap_output"])
        #     if write_header:
        #         writer.writeheader()
        #     writer.writerow(result_row)


        
if __name__ == "__main__":
    Run_Single_Exp2()
