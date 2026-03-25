from solverClingoAPI import Schedule, BaselineSchedule, ComputeUnServedCustomers
# from MSMAPSolver import MSMAP
from instances.gen_instance import GenRq, InitLoc
from utils.utils import EstimateMinAgents, EstimateMinAgentsGivenSegmentsAndCustomers
import csv
import pandas as pd
import os
from encoding.baseline_py import GreedyAlg, GreedyAlg2
import math
import pickle
import glob



# algorithm id
o1 = f"encoding/optional/o1.lp"
o2 = f"encoding/optional/o2.lp"
h1 = f"encoding/optional/h1.lp"
h2 = f"encoding/optional/h2.lp"


# run single experiment
def RunSingleExp0(alg, nb_agent, nb_rq, nb_segment, smp, network_file, print_answer=False):
    # Use glob to find matching files with wildcard
    rq_files = glob.glob(f'instances/exp0/rq_ins*_rq{nb_rq}_agent{nb_agent}_seg{10}_smp{smp}.lp')
    init_files = glob.glob(f'instances/exp0/init_ins*_rq{nb_rq}_agent{nb_agent}_seg{10}_smp{smp}.lp')
    
    if not rq_files or not init_files:
        print(f"Warning: No matching files found for rq{nb_rq}_agent{nb_agent}_seg{nb_segment}_smp{smp}")
        return None
    
    rq_file = rq_files[0]  # Use first match
    init_file = init_files[0]
    
    result = {
            "nb_agent": nb_agent,
            "nb_rq": nb_rq,
            "nb_segment": nb_segment}          

    
    heuristic = alg[2] is not None
    print(f" Running with  algorithm {alg[0]} nb_agent={nb_agent}, nb_rq={nb_rq}, nb_segment={nb_segment} sample={smp}")

    s = Schedule(
        time_limit=300,
        update_time_limit=None,
        nb_agents=nb_agent,
        nb_rq=nb_rq,
        max_segment=nb_segment,
        encoding='encoding/schedule.lp',
        network='instances/network.lp',
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
                                network_file='instances/network.lp',
                                init_file=init_file, rq_file=rq_file)
        result.update({
            f"served_customers_{alg[0]}": round((nb_rq*42 - unserved_customers)*100/(nb_rq*42)),
            # f"profit_{alg[0]}": round(model.profit),
            f"run_time_{alg[0]}": round(model.run_time)
        })
        print({
            f"served_customers_{alg[0]}": f"{(nb_rq*42 - unserved_customers)*100/(nb_rq*42):.2f} %",
            # f"profit_{alg[0]}": round(model.profit),
            f"run_time_{alg[0]}": f"{round(model.run_time)} second"
        })
        if print_answer == True:
            print(model.schedule)
    else:
        print(f"Warning: No answer set found. Skipping this configuration.")
        result.update({
        f"served_customers_{alg[0]}": 'TO',
        # f"profit_{alg[0]}": 'TO',
        f"run_time_{alg[0]}": 300
        })

                      
if __name__ == "__main__":
    #algorithm with name, optimization, and heuristic
    h3 = f"encoding/optional/h3.lp"
    alg = ['W*S*(max_seg-X)', None, [h2]]
    RunSingleExp0(alg=alg, 
                  nb_agent=22, 
                  nb_rq=20, 
                  nb_segment=10,
                  smp=4,
                  network_file=None,
                  print_answer=False,
                  )