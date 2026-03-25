from clingo import Control, Model, Function
from clingo.ast import parse_string, ProgramBuilder
from clingodl import ClingoDLTheory
import clingo
import sys
import argparse
import os
import time
import subprocess
from utils.utils import CalProfit, EstimateMinAgents
from instances.gen_instance import GenRq, InitLoc
import random
from typing import List
import re
import multiprocessing
import threading
import ctypes
# Callback function to handle models during solving
def on_model(m):
    print (m)

# Separator line for output readability
LINE = "---------------------------------------------------------------------"

# Uncommented argument parsing section for potential CLI usage
parser = argparse.ArgumentParser(description='Solver for eVTOL scheduling.')
parser.add_argument('--n_rq', type=int, default = 30, help='Number of requests')
parser.add_argument('--n_agents', type=int, default = 34, help='Number of agents')
parser.add_argument('--max_segment', type=int, default = 13, help='Maximum segment')
parser.add_argument('--horizon', type=int, default = 180, help='Horizon')
parser.add_argument('--time_limit', type=int, default = 30, help='Time limit')
parser.add_argument('--seed', type=int, default = 1, help='seed for random initial location')
parser.add_argument('--vertiport_cap', type=int, default = 6, help='vertiport capacity')
args = parser.parse_args()

# Estimate the minimum number of agents and segments required
# min_agents, min_segments = EstimateMinAgents(horizon=180, b_init=60, demand_cust=30, aircraft_capacity=4)

# Class to handle scheduling logic
class Schedule:
    def __init__(
        self,
        time_limit: int,
        update_time_limit: int,
        max_segment: int,
        nb_agents: int,
        nb_rq: int,
        horizon:int,
        encoding: str,
        network: str,
        init_file: str,
        rq_file: str,
        heuristic: bool,
        choose_heu: list,
        choose_opt: list,
        dl_theory: bool
    ):
        self.thy = ClingoDLTheory()
        self.time_limit = time_limit
        self.update_time_limit = update_time_limit
        self.start_segment = 1
        self.max_segment = max_segment
        self.nb_agents = nb_agents
        self.nb_rq = nb_rq
        self.horizon = horizon
        self.encoding = encoding
        self.network = network
        self.init = init_file
        self.rq = rq_file
        self.models = []
        self.control_par = ['-c', f'start_seg={self.start_segment}']
        if horizon is not None:
            self.control_par.extend(['-c', f'horizon={self.horizon}'])
        if max_segment is not None:
            self.control_par.extend(['-c', f'max_seg={self.max_segment}'])
        if heuristic:
            self.control_par.append('--heuristic=Domain')
            self.control_par.append('-t4')
            # self.control_par.append('-t4')
        # if n_agents is not None:
        #     InitLoc(nAgents=n_agents, seed=seed_init, limit_nAgents_each_vertiport=vert_cap)
        # if n_rq is not None:
        #     GenRq(cust=n_rq, seed=seed_rq)
        self.choose_heu = choose_heu
        self.choose_opt = choose_opt
        self.dl_theory = dl_theory

    @staticmethod
    def _solving_worker_static(
        control_par, encoding, network, init, rq, max_segment, nb_agents, nb_rq, choose_opt, choose_heu, dl_theory, time_limit, update_time_limit, fact_load, return_dict, print_style='all'
    ):
        # No need to import here; all required modules are already imported at the top of the file.

        LINE = "---------------------------------------------------------------------"
        thy = ClingoDLTheory()
        models = []
        ctl = Control(control_par)
        thy.register(ctl)
        return_dict['models'] = []
        with open(encoding, 'r') as file:
            prg = file.read()
        if network:
            with open(network, 'r') as file:
                prg += file.read()
        with open(init, 'r')as file:
            prg += file.read()
        with open(rq, 'r')as file:
            prg += file.read()
        if choose_opt:
            for opt in choose_opt:
                with open(opt, 'r') as file:
                    prg += file.read()
        if choose_heu:
            for heu in choose_heu:
                with open(heu, 'r') as file:
                    prg += file.read()
        prg = fact_load + prg
        with ProgramBuilder(ctl) as bld:
            parse_string(prg, lambda ast: thy.rewrite_ast(ast, bld.add))

        try:
            print('Start Grounding...')
            grounding_start = time.time()
            ctl.ground([('base', [])])
            grounding_time = time.time() - grounding_start
            print(grounding_time, 'seconds for grounding')
            remain_time = time_limit - grounding_time
            if remain_time <= 0:
                print('Grounding took too long, stopping...')
                return_dict['models'] = []
                return
            thy.prepare(ctl)
            print('Done grounding!')
            print('Start Solving...')
            stop = False
            remain_solving_time=remain_time
            
            with ctl.solve(yield_=True, on_model=thy.on_model, async_=True) as hnd:
                start_time = time.time()
                while not stop:
                    hnd.resume()
                    if update_time_limit is None or remain_solving_time <= update_time_limit:
                        flag = hnd.wait(remain_solving_time)
                    else:
                        flag = hnd.wait(update_time_limit)
                    # print(flag, remain_time)
                    remain_solving_time = remain_time - (time.time() - start_time)
                    # print(f"flag is: {flag}")
                    if  flag is False:
                        print(f"remain solving time is: {remain_solving_time}")
                        print('Stop solving')
                        hnd.cancel()
                        break
                    else:
                        if hnd.model() is None:
                            print('Stop solving')
                            hnd.cancel()
                            break
                        print(f"Model number: {hnd.model().number}")
                        print(f'solving time is: {(time.time() - start_time)}')
                        print(f'remain time is: {remain_solving_time}')
                        rawmodel = hnd.model()
                        
                        # Minimal model extraction (no self)
                        model = argparse.Namespace()
                        if rawmodel is not None:
                            model.opt_cost = rawmodel.cost.copy()
                        # model.number = rawmodel.number
                            model.output = str(rawmodel)
                            model.all_atoms = " ".join(map(str, rawmodel.symbols(atoms=True)))
                            model.flight_path = [symbol for symbol in str(rawmodel).split() if symbol.startswith('as')]
                            model.flight_path_fact_format = " ".join([i + '.' for i in model.flight_path])
                            if dl_theory:
                                dl_assignments = [f"dl({str(dl_variable)},{dl_value})"
                                                for dl_variable, dl_value in thy.assignment(rawmodel.thread_id)]
                                model.dl_assignments = dl_assignments
                                model.schedule = model.flight_path_fact_format + " " + " ".join([i + '.' for i in model.dl_assignments])
                            else:
                                model.schedule = model.flight_path_fact_format
                            # model.revenue, model.em_cost, model.chg_cost, model.profit, model.stationed_route_count, model.empty_flight_count = CalProfit(model.schedule)
                            model.run_time = time_limit - remain_solving_time
                            # if print_style == 'all':
                            #     print(f"Model {rawmodel.number} found with cost {rawmodel.cost} in {model.run_time:.2f} seconds.")
                            #     print(f"Revenue: {model.revenue}, EM Cost: {model.em_cost}, CHG Cost: {model.chg_cost}, Profit: {model.profit}")
                            #     print(f"stationed_route_count: {model.stationed_route_count}, empty_flight_count: {model.empty_flight_count}")
                        if rawmodel is not None:
                            return_dict['models'] += [model]
                            print(f"len of return_dict is {len(return_dict['models'])}")
                        print(LINE)
                hnd.cancel()
        except KeyboardInterrupt:
            print("\nSolving interrupted by keyboard...")

    def Solving(self, fact_load="", print_style='all'):
        
        manager = multiprocessing.Manager()
        return_dict = manager.dict()
        p = multiprocessing.Process(
            target=Schedule._solving_worker_static,
            args=(
                self.control_par,
                self.encoding,
                self.network,
                self.init,
                self.rq,
                self.max_segment,
                self.nb_agents,
                self.nb_rq,
                self.choose_opt,
                self.choose_heu,
                self.dl_theory,
                self.time_limit,
                self.update_time_limit,
                fact_load,
                return_dict,
                print_style
            )
        )
        p.start()
        p.join(self.time_limit)
        if p.is_alive():
            print(f"Solving exceeded time limit of {self.time_limit} seconds. Terminating...")
            p.terminate()
            p.join()
            print(f'check if thread alive: {p.is_alive()}')
            self.models = return_dict['models']
            return 
        self.models = return_dict.get('models', [])
        return self.models

    
    def GetBestMinOptModel(self):
        return min(self.models, key=lambda model: model.opt_cost)

    def GetBestMaxOptModel(self):
        return max(self.models, key=lambda model: model.opt_cost)
    
    def GetBestProfitModel(self):
        return max(self.models, key=lambda model: model.profit)

# Utility function to solve a Clingo program with additional facts
def ClingoSolver(prg_path, facts):
    with open(prg_path, "r") as file:
        prg = file.read()
    prg += facts
    ctl = Control()
    ctl.add("base", [], prg)
    ctl.ground([("base", [])])
    with ctl.solve(yield_=True) as handle:
        for model in handle:
            return " ".join([f"{str(symbol)}." for symbol in model.symbols(shown=True)])

def ClingoDLSolver(prg_path, facts):
    ctl = Control()
    thy = ClingoDLTheory()
    thy.register(ctl)
    with open(prg_path, "r") as file:
        prg = file.read()
    prg += facts
    with ProgramBuilder(ctl) as bld:
        parse_string(prg, lambda ast: thy.rewrite_ast(ast, bld.add))
    ctl.ground([("base", [])])
    thy.prepare(ctl)
    with ctl.solve(yield_=True) as handle:
        for model in handle:
            print(model)


class BaselineSchedule(Schedule):
    def __init__(
                    self, time_limit, max_segment, 
                    rq_file, init_file,
                    nb_agents, nb_rq):
        super().__init__(time_limit=time_limit, 
                        update_time_limit=None,
                        max_segment=max_segment, horizon=None,
                        encoding='T_ITS2025/baseline.lp', 
                        network='T_ITS2025/instances/network_NY_0.lp', init_file=init_file, rq_file=rq_file,
                        nb_agents=nb_agents, nb_rq=nb_rq,
                        heuristic=True, choose_heu=None, choose_opt=None, dl_theory=True)
        
    @staticmethod
    def _solving_worker_static(
        control_par, encoding, network, init, rq, max_segment, nb_agents, nb_rq, choose_opt, choose_heu, dl_theory, time_limit, update_time_limit, fact_load, return_dict, print_style='all'
    ):

        start_time = time.time()
        with open(encoding, 'r') as file:
            prg = file.read()
        if network:
            with open(network, 'r') as file:
                prg += file.read()
        with open(init, 'r') as file:
            prg += file.read()
        with open(rq, "r") as file:
            prg += file.read()
        route = ""
        try:
            for seg in range(1, max_segment):
                if print_style == 'all':
                    print(f'==== seg {seg} ====')
                for agent in range(nb_agents):
                    if print_style == 'all':
                        print(f'==== seg {seg} agent {agent}====')
                    thy = ClingoDLTheory()
                    ctl = Control(control_par)
                    thy.register(ctl)
                    prg_seg = prg + route + f'seg({seg}).'
                    with ProgramBuilder(ctl) as bld:
                        parse_string(prg_seg, lambda ast: thy.rewrite_ast(ast, bld.add))
                    ctl.ground([('base', [])])
                    thy.prepare(ctl)
                    ctl.assign_external(clingo.Function("current_agent", [clingo.Number(agent)]), True)
                    hnd = ctl.solve(yield_=True, on_model=thy.on_model)
                    # Get route from model
                    if hnd.model() is not None:
                        route_syms = [symbol for symbol in str(hnd.model()).split() if symbol.startswith('as')]
                        route = " ".join([i + '.' for i in route_syms])
                        dl_assignments = [f"dl({str(dl_variable)},{dl_value})"
                                        for dl_variable, dl_value in thy.assignment(hnd.model().thread_id)]
                        schedule = route + " " + " ".join([i + '.' for i in dl_assignments])
                        revenue, em_cost, chg_cost, profit, stationed_route_count, empty_flight_count = CalProfit(schedule)
                        run_time = time.time() - start_time
                        model = argparse.Namespace()
                        model.flight_path_fact_format = schedule
                        model.profit = profit
                        model.run_time = run_time
                        model.all_atoms = str(hnd.model()).split()
                        return_dict['models'] = [model]
                    
        except KeyboardInterrupt:
            print("\nSolving interrupted by keyboard...")
            return None
        finally:
            if print_style == 'all':
                print(route)
                print(f'run time is {run_time}')
                print(f'profit is {profit}')
                print(f'stationed_route_count is {stationed_route_count}')
            
        
    def Solving(self, fact_load="", print_style='all'):
        
        manager = multiprocessing.Manager()
        return_dict = manager.dict()
        p = multiprocessing.Process(
            target=BaselineSchedule._solving_worker_static,
            args=(
                self.control_par,
                self.encoding,
                self.network,
                self.init,
                self.rq,
                self.max_segment,
                self.nb_agents,
                self.nb_rq,
                self.choose_opt,
                self.choose_heu,
                self.dl_theory,
                self.time_limit,
                self.update_time_limit,
                fact_load,
                return_dict,
                print_style
            )
        )
        p.start()
        p.join(self.time_limit)
        if p.is_alive():
            print(f"Solving exceeded time limit of {self.time_limit} seconds. Terminating...")
            p.terminate()
            p.join()
            print(f'check if thread alive: {p.is_alive()}')
            self.models = return_dict['models']
            return return_dict.get('models', [])
        
        self.models = return_dict.get('models', [])
        return self.models
            
def ComputeUnServedCustomers(flight_path, network_file, init_file, rq_file, verbose=True):
    with open("encoding/compute_revenue.lp", "r") as file:
        prg = file.read()
    with open(network_file, "r") as file:
        prg += file.read()
    with open(init_file, "r") as file:
        prg += file.read()
    with open(rq_file, "r") as file:
        prg += file.read()
    prg += flight_path
    ctl = Control()
    ctl.add("base", [], prg)
    ctl.ground([("base", [])])
    with ctl.solve(yield_=True) as handle:
        for model in handle:
            for atom in model.symbols(shown=True):
                if verbose:
                    print(atom)
                if atom.name == "total_remain":
                    total_remain= atom.arguments[0].number
    return total_remain
    

# Get the model with the best optimization cost
def GetBestModelOptCost(models: List[argparse.Namespace]):
    if not models:
        return None
    return max(models, key=lambda model: model.opt_cost)

# Get the model with the highest profit
def GetBestModelProfit(models: List[argparse.Namespace]):
    if not models:
        return None
    return max(models, key=lambda model: model.profit)

# Compute revenue based on flight paths
def ComputeRevenue(flight_path):
    flight_path = " ".join([i + '.' for i in flight_path.split()])
    ctl = Control([])
    ctl.add(flight_path)
    ctl.load('compute_revenue.lp')
    ctl.ground([("base", [])])
    with ctl.solve(yield_=True) as out:
        print(out.model())

# Get the number of agents at each vertiport
def GetNumberOfAgentsEachVertiport(dl_assignments):
    schedule = " ".join([i + '.' for i in dl_assignments])
    ctl = Control([])
    ctl.add(schedule)
    ctl.load('transfer.lp')
    ctl.ground([("base", [])])
    with ctl.solve(yield_=True) as out:
        print(out.model())

# Centralized scheduling approach
def CentralSchedule():
    schedule = Schedule()
    models = schedule.Solving()
    best_model = GetBestModelProfit(models)
    return best_model

# Consecutive scheduling approach
def ConsecutiveSchedule():
    schedule = Schedule(choose_opt=[2, 2.1])
    models = schedule.Solving()
    best_model = GetBestModelOptCost(models)
    flight_path = best_model.flight_path_clingo_format
    
    schedule = Schedule(start_segment=11, max_segment=13, heuristic=False, choose_opt=[1, 2.1])
    print(flight_path)
    models = schedule.Solving(fact_load=flight_path)
    best_model = GetBestModelOptCost(models)

    return best_model

def DP():
    flight_path =''
    for d in range(0, 56):
        print(f'========== Schedule Agent {d}:')
        schedule = Schedule(time_limit=10
                            , start_segment=1
                            , max_segment=6
                            , encoding='encoding/d_s.lp'
                            , network='instances/network_NY.lp'
                            , init_path= 'instances/init_decoupled.lp'
                            , heuristic=True
                            , choose_heu=[2]
                            , choose_opt=[1]
                            , n_rq=None
                            , n_agents=None
                            , seed_init=1
                            , seed_rq=1
                            , dl_theory=True
                            )
        models = schedule.Solving(fact_load=f'agent({d}).'+ flight_path)
        best_model = GetBestModelOptCost(models=models)
        flight_path = best_model.flight_path_fact_format
        print(flight_path)
    return best_model.to_visualized

# Switching trajectory approach 1
def MSMAP(time_limit=30, start_segment=1, max_segment=13, network='instances/network_NY_0.lp',
                        rq_file='instances/rq.lp',
                        init_file='instances/init.lp'):
    # Initial solution
    print('=========== step 1: assign trajectory allowing operation time > horizon, prioritizing serving all customers:')
    s = Schedule(time_limit=time_limit
                , start_segment=start_segment
                , max_segment=max_segment
                , encoding='encoding/s.lp'
                , network=network
                , heuristic=True
                , choose_heu=None
                , choose_opt=None
                , init_path=init_file
                , rq_path=rq_file
                , dl_theory=False
                )
    models = s.Solving()
    best_model = min(models, key=lambda model: model.opt_cost)
    # best_model = GetBestModelOptCost(models=models)

    # Switching logic
    answer_set = best_model.flight_path_fact_format
    print(answer_set)
    print("========== step 2: start switching trajectory to constraint operation time <= horizon")
    sw = Schedule(time_limit=15
                , encoding='encoding/sw0.1.lp'
                , network=network
                , horizon=180
                , heuristic=False
                , choose_heu=None
                , choose_opt=None
                , dl_theory=False
                )
    models = sw.Solving(fact_load=answer_set)
    best_model = max(models, key=lambda model: model.opt_cost)


    model_after_switch = best_model
    # Extract d and d_prime
    print("mixed best: ", re.findall(r"mixed_best\(([^,]+),([^,]+),.*?\)\s", model_after_switch.all_atoms))
    print(f"empty_flights: ", re.findall(r"wasted\([^)]+\)", model_after_switch.all_atoms))

    answer_set = model_after_switch.flight_path_fact_format
    print(f"flight path after swap: \n{answer_set}")

    print(f"solution time: ", re.findall(r"solution_time\([^)]+\)", model_after_switch.all_atoms))
        
    print("========== step 3: assign time using clingo-dl")
    # Final scheduling with time constraints
    dl = Schedule(time_limit=30
                    , encoding='encoding/time0.lp'
                    , network=network
                    , heuristic=False
                    , dl_theory=True
                    , max_segment=max_segment
                    )
    time = dl.Solving(fact_load=answer_set)
    if len(time) != 0:
        return 'SAT2'
    else: return 'SAT1'

# Main execution
if __name__ == "__main__":
    # InitLoc(nAgents=50, out_file='T_ITS2025/instances/init.lp')
    # GenRq(cust=50, out_file='T_ITS2025/instances/rq.lp')
    # s = Schedule(
    #     time_limit=60,
    #     update_time_limit=5,
    #     max_segment=8,
    #     encoding='T_ITS2025/schedule.lp',
    #     network='T_ITS2025/instances/network_NY_0.lp',
    #     rq_file='T_ITS2025/instances/rq.lp',
    #     init_file='T_ITS2025/instances/init.lp',
    #     choose_heu=None,
    #     choose_opt=[2],
    #     dl_theory=True,
    #     horizon=180,
    #     heuristic=False
    # )
    # s.Solving()
    # print('test')
    # s = BaselineSchedule(time_limit=300,
    #                     max_segment=10,
    #                     nb_agents=160,
    #                     nb_rq=150,
    #                     rq_file='T_ITS2025/instances/exp0/rq_ins20_rq150_agent160_seg10_smp0.lp',
    #                     init_file='T_ITS2025/instances/exp0/init_ins20_rq150_agent160_seg10_smp0.lp')
    # s.Solving()
    # print("unserved customer: ",ComputeUnServedCustomers(
    #                                         s.models[-1].flight_path_fact_format, 
    #                                         network_file='T_ITS2025/instances/network_NY_0.lp',
    #                                         init_file='T_ITS2025/instances/exp0/init_ins20_rq150_agent160_seg10_smp0.lp', rq_file='T_ITS2025/instances/exp0/rq_ins20_rq150_agent160_seg10_smp0.lp'))
    pass