"""Solving API for the eVTOL scheduler.

`Schedule` runs the hybrid clingo + clingo-dl encoding; `BaselineSchedule`
runs the 1-segment look-ahead greedy baseline. Both solve in a subprocess so a
wall-clock time limit can be enforced. Run experiments via run_experiments.py.
"""
from dataclasses import dataclass, field
import multiprocessing
import time

import clingo
from clingo import Control
from clingo.ast import parse_string, ProgramBuilder
from clingodl import ClingoDLTheory

from utils.utils import CalProfit

LINE = "---------------------------------------------------------------------"


@dataclass
class ScheduleModel:
    """One answer set plus its decoded schedule and economics."""
    schedule: str = ""                       # flight + dl facts, loadable as .lp
    flight_path: list = field(default_factory=list)
    flight_path_fact_format: str = ""        # flight facts only
    dl_assignments: list = field(default_factory=list)
    opt_cost: list = field(default_factory=list)
    output: str = ""
    all_atoms: str = ""
    revenue: float = 0.0
    em_cost: float = 0.0
    chg_cost: float = 0.0
    profit: float = 0.0
    stationed_route_count: int = 0
    empty_flight_count: int = 0
    run_time: float = 0.0


def _build_model(rawmodel, thy, dl_theory, run_time, econ=None):
    """Decode a clingo model into a ScheduleModel (flight path + timing + costs)."""
    m = ScheduleModel()
    m.opt_cost = rawmodel.cost.copy()
    m.output = str(rawmodel)
    m.all_atoms = " ".join(map(str, rawmodel.symbols(atoms=True)))
    m.flight_path = [s for s in m.output.split() if s.startswith('flight(')]
    m.flight_path_fact_format = " ".join(s + '.' for s in m.flight_path)
    if dl_theory:
        m.dl_assignments = [f"dl({var},{val})"
                            for var, val in thy.assignment(rawmodel.thread_id)]
        m.schedule = m.flight_path_fact_format + " " + \
            " ".join(s + '.' for s in m.dl_assignments)
    else:
        m.schedule = m.flight_path_fact_format
    (m.revenue, m.em_cost, m.chg_cost, m.profit,
     m.stationed_route_count, m.empty_flight_count) = CalProfit(m.schedule, econ=econ)
    m.run_time = run_time
    return m


def _read_program(encoding, network, init, rq, choose_opt, choose_heu):
    """Concatenate the encoding, network, instance, and optional modules into one program."""
    parts = [encoding]
    if network:
        parts.append(network)
    parts += [init, rq]
    parts += list(choose_opt or [])
    parts += list(choose_heu or [])
    prg = ""
    for path in parts:
        with open(path, 'r') as file:
            prg += file.read()
    return prg


class Schedule:
    """Runs the full hybrid encoding (routing + clingo-dl timing) as an anytime solver."""

    def __init__(self, time_limit, update_time_limit, max_segment, nb_agents,
                 nb_rq, horizon, encoding, network, init_file, rq_file,
                 heuristic, choose_heu, choose_opt, dl_theory, econ=None):
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
        self.choose_heu = choose_heu
        self.choose_opt = choose_opt
        self.dl_theory = dl_theory
        self.econ = econ
        self.models = []
        self.control_par = ['-c', f'start_seg={self.start_segment}']
        if horizon is not None:
            self.control_par += ['-c', f'horizon={self.horizon}']
        if max_segment is not None:
            self.control_par += ['-c', f'max_seg={self.max_segment}']
        if heuristic:
            self.control_par += ['--heuristic=Domain', '-t4']

    @staticmethod
    def _solving_worker_static(control_par, encoding, network, init, rq, max_segment,
                               nb_agents, nb_rq, choose_opt, choose_heu, dl_theory,
                               time_limit, update_time_limit, fact_load, return_dict,
                               verbose=True, econ=None):
        thy = ClingoDLTheory()
        ctl = Control(control_par)
        thy.register(ctl)
        return_dict['models'] = []
        prg = fact_load + _read_program(encoding, network, init, rq, choose_opt, choose_heu)
        with ProgramBuilder(ctl) as bld:
            parse_string(prg, lambda ast: thy.rewrite_ast(ast, bld.add))

        try:
            if verbose:
                print('Start Grounding...')
            grounding_start = time.time()
            ctl.ground([('base', [])])
            grounding_time = time.time() - grounding_start
            remain_time = time_limit - grounding_time
            if remain_time <= 0:
                print('Grounding took too long, stopping...')
                return
            thy.prepare(ctl)
            if verbose:
                print(f'Done grounding ({grounding_time:.2f}s). Start Solving...')

            remain_solving_time = remain_time
            with ctl.solve(yield_=True, on_model=thy.on_model, async_=True) as hnd:
                start_time = time.time()
                while True:
                    hnd.resume()
                    if update_time_limit is None or remain_solving_time <= update_time_limit:
                        flag = hnd.wait(remain_solving_time)
                    else:
                        flag = hnd.wait(update_time_limit)
                    remain_solving_time = remain_time - (time.time() - start_time)
                    if flag is False or hnd.model() is None:
                        hnd.cancel()
                        break
                    rawmodel = hnd.model()
                    model = _build_model(rawmodel, thy, dl_theory,
                                         run_time=time_limit - remain_solving_time, econ=econ)
                    return_dict['models'] += [model]
                    if verbose:
                        print(f"Model {rawmodel.number}: profit={model.profit:.0f} "
                              f"({model.run_time:.1f}s)")
                        print(LINE)
                hnd.cancel()
        except KeyboardInterrupt:
            print("\nSolving interrupted by keyboard...")

    def Solving(self, fact_load="", verbose=True):
        """Solve in a subprocess, enforcing self.time_limit. Returns the models found."""
        manager = multiprocessing.Manager()
        return_dict = manager.dict()
        p = multiprocessing.Process(
            target=type(self)._solving_worker_static,
            args=(self.control_par, self.encoding, self.network, self.init, self.rq,
                  self.max_segment, self.nb_agents, self.nb_rq, self.choose_opt,
                  self.choose_heu, self.dl_theory, self.time_limit,
                  self.update_time_limit, fact_load, return_dict, verbose, self.econ),
        )
        p.start()
        p.join(self.time_limit)
        if p.is_alive():
            print(f"Solving exceeded time limit of {self.time_limit}s. Terminating...")
            p.terminate()
            p.join()
        self.models = return_dict.get('models', [])
        return self.models


class BaselineSchedule(Schedule):
    """1-segment look-ahead greedy baseline: solve one segment per agent at a time."""

    def __init__(self, time_limit, max_segment, rq_file, init_file, nb_agents, nb_rq,
                network='instances/network.lp', econ=None):
        super().__init__(time_limit=time_limit, update_time_limit=None,
                         max_segment=max_segment, horizon=None,
                         encoding='encoding/baseline.lp',
                         network=network,
                         init_file=init_file, rq_file=rq_file,
                         nb_agents=nb_agents, nb_rq=nb_rq,
                         heuristic=True, choose_heu=None, choose_opt=None, dl_theory=True,
                         econ=econ)

    @staticmethod
    def _solving_worker_static(control_par, encoding, network, init, rq, max_segment,
                               nb_agents, nb_rq, choose_opt, choose_heu, dl_theory,
                               time_limit, update_time_limit, fact_load, return_dict,
                               verbose=True, econ=None):
        start_time = time.time()
        prg = _read_program(encoding, network, init, rq, choose_opt, choose_heu)
        route = ""
        try:
            for seg in range(1, max_segment):
                for agent in range(nb_agents):
                    if verbose:
                        print(f'==== seg {seg} agent {agent} ====')
                    thy = ClingoDLTheory()
                    ctl = Control(control_par)
                    thy.register(ctl)
                    prg_seg = prg + route + f'seg({seg}).'
                    with ProgramBuilder(ctl) as bld:
                        parse_string(prg_seg, lambda ast: thy.rewrite_ast(ast, bld.add))
                    ctl.ground([('base', [])])
                    thy.prepare(ctl)
                    ctl.assign_external(
                        clingo.Function("current_agent", [clingo.Number(agent)]), True)
                    hnd = ctl.solve(yield_=True, on_model=thy.on_model)
                    if hnd.model() is None:
                        continue
                    route_syms = [s for s in str(hnd.model()).split()
                                  if s.startswith('flight(')]
                    route = " ".join(s + '.' for s in route_syms)
                    dl_assignments = [f"dl({var},{val})"
                                      for var, val in thy.assignment(hnd.model().thread_id)]
                    schedule = route + " " + " ".join(s + '.' for s in dl_assignments)
                    revenue, em_cost, chg_cost, profit, stationed, empty = CalProfit(schedule, econ=econ)
                    model = ScheduleModel()
                    model.flight_path_fact_format = schedule
                    model.schedule = schedule
                    model.revenue, model.em_cost, model.chg_cost = revenue, em_cost, chg_cost
                    model.profit = profit
                    model.stationed_route_count, model.empty_flight_count = stationed, empty
                    model.run_time = time.time() - start_time
                    return_dict['models'] = [model]
        except KeyboardInterrupt:
            print("\nSolving interrupted by keyboard...")


def ComputeUnServedCustomers(flight_path, network_file, init_file, rq_file, verbose=True):
    """Return the number of customers left unserved by the given flight path."""
    prg = _read_program("encoding/compute_revenue.lp", network_file, init_file, rq_file,
                        None, None)
    prg += flight_path
    ctl = Control()
    ctl.add("base", [], prg)
    ctl.ground([("base", [])])
    total_remain = None
    with ctl.solve(yield_=True) as handle:
        for model in handle:
            for atom in model.symbols(shown=True):
                if verbose:
                    print(atom)
                if atom.name == "total_remain":
                    total_remain = atom.arguments[0].number
    return total_remain
