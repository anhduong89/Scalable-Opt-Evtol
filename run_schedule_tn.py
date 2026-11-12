"""Run the real ASP (clingo + clingo-dl) scheduler for the 10-vertiport TN network.

Network data (10 Tennessee airports, haversine distances) lives in constants.py
(TN_CITY_NAMES / TN_DIST), sourced from instances/TN_vertiport_location.xlsx.
Fleet size comes from EstimateMinAgentsGivenSegmentsAndCustomers given a fixed
segment count and per-edge demand -- the same formulation as the NY exp0 bench.

Uses the O1 (maximize revenue) optimization module with the H2 heuristic
(prioritize higher-revenue flights earlier) -- the paper's "O1H2" config -- run
anytime with --heuristic=Domain up to TIME_LIMIT seconds; the last model clingo
reports is its best found so far.

TN has no MER/LMP price data, so charging/emission cost accounting is skipped
(econ.price_tables=None); profit == revenue here. The output schedule JSON maps
each clingo-safe vertiport id back to its real FAA/ICAO code via TN_FAA_CODES.

Requires the evtol-py3.9 conda env (clingo 5.6.2 + clingo-dl 1.4.0).
"""
import argparse
import json
import re

from constants import (TN_CITY_NAMES, TN_DIST, TN_FAA_CODES,
                       TN_VELOCITY, TN_E_DISCHG, TN_G_I)
from utils.utils import (EconConfig, EstimateMinAgents,
                        EstimateMinAgentsGivenSegmentsAndCustomers)
from instances.gen_instance import InitLoc, GenRq
from instances.gen_network import GenerateMapGivenPath
from solverClingoAPI import Schedule, ComputeUnServedCustomers

TIME_LIMIT = 300       # seconds (anytime; keep best model found)
HORIZON = 180          # minutes
NB_RQ = 30             # requested passengers per directed edge
AIRCRAFT_CAPACITY = 4  # passengers/flight
SEED = 0
# Fleet size AND segment count are computed jointly from the paper's
# formulation (EstimateMinAgents) using TN's own distances/physics -- NOT a
# fixed 10. TN's long legs (avg 63 min flight+charge) mean only ~3 flights fit
# in the 180-min horizon, so the optimal segment count is ~3 (with ~254
# aircraft), not 10; fixing 10 makes 7/10 segments un-fillable and the O1
# revenue search thrash against the horizon.

NETWORK = "instances/network_TN.lp"
INIT_FILE = "instances/init_TN.lp"
RQ_FILE = "instances/rq_TN.lp"
OUT_JSON = "schedule_sample_tn_1.json"
O1 = "encoding/optional/o1.lp"
H2 = "encoding/optional/h2.lp"

_FLIGHT_RE = re.compile(r'flight\((\d+),\((\w+),(\w+)\),(\d+),(\d+)\)')
_START_RE = re.compile(r'dl\(start\((\d+),\((\w+),(\w+)\),(\d+)\),(\d+)\)')
_ARRIVAL_RE = re.compile(r'dl\(arrival\((\d+),\((\w+),(\w+)\),(\d+)\),(\d+)\)')


def schedule_to_json(answer_set):
    """Parse flight + dl atoms into the per-agent segment JSON format, converting
    clingo-safe vertiport ids back to FAA codes and dropping stationed self-loops."""
    flights = {}   # (agent, seg) -> (origin, dest, weight)
    starts = {}    # (agent, seg) -> departure_time
    arrivals = {}  # (agent, seg) -> arrival_time
    for tok in answer_set.split():
        m = _FLIGHT_RE.match(tok)
        if m:
            a, o, d, w, x = m.groups()
            flights[(int(a), int(x))] = (o, d, int(w))
            continue
        m = _START_RE.match(tok)
        if m:
            a, o, d, x, t = m.groups()
            starts[(int(a), int(x))] = int(t)
            continue
        m = _ARRIVAL_RE.match(tok)
        if m:
            a, o, d, x, t = m.groups()
            arrivals[(int(a), int(x))] = int(t)

    by_agent = {}
    for (a, x), (o, d, w) in flights.items():
        if o == d:  # stationed self-loop: aircraft stays put, not a real trip
            continue
        by_agent.setdefault(a, []).append((x, o, d, w))

    schedule = []
    for a in sorted(by_agent):
        segs = sorted(by_agent[a])
        out_segs = []
        for seg_num, (x, o, d, w) in enumerate(segs, 1):
            out_segs.append({
                "segment": seg_num,
                "origin": TN_FAA_CODES[o],
                "destination": TN_FAA_CODES[d],
                "departure_time": starts.get((a, x)),
                "arrival_time": arrivals.get((a, x)),
                "people_transported": w,
            })
        if out_segs:
            schedule.append({"agent_id": a, "segments": out_segs})
    return schedule


def main(fixed_segment=None, domain_heuristic=True):
    if fixed_segment is None:
        # Joint optimum: formulation picks BOTH fleet size and segment count.
        nb_agent, nb_segment = EstimateMinAgents(
            horizon=HORIZON, b_init=0, demand_cust=NB_RQ,
            aircraft_capacity=AIRCRAFT_CAPACITY, random_cust=False,
            nb_vertiports=len(TN_CITY_NAMES), dist_matrix=TN_DIST,
            velocity_mph=TN_VELOCITY, e_dischg_rate=TN_E_DISCHG, g_i_rate=TN_G_I)
        nb_agent, nb_segment = int(nb_agent), int(nb_segment)
        print(f"nb_agent = {nb_agent}, nb_segment = {nb_segment} (joint optimum), "
              f"vertiports = {len(TN_CITY_NAMES)}")
    else:
        # Fixed segment count: formulation derives the fleet size for it.
        nb_segment = fixed_segment
        nb_agent = int(EstimateMinAgentsGivenSegmentsAndCustomers(
            horizon=HORIZON, b_init=0, demand_cust=NB_RQ,
            aircraft_capacity=AIRCRAFT_CAPACITY, nb_segments=nb_segment,
            random_cust=False, nb_vertiports=len(TN_CITY_NAMES)))
        print(f"nb_agent = {nb_agent}, nb_segment = {nb_segment} (fixed segment), "
              f"vertiports = {len(TN_CITY_NAMES)}")

    # (Re)generate the TN network + instance facts.
    GenerateMapGivenPath(TN_CITY_NAMES, TN_DIST, TN_VELOCITY, TN_E_DISCHG, TN_G_I,
                         out_file=NETWORK).run()
    InitLoc(nAgents=nb_agent, seed=SEED, limit_nAgents_each_vertiport=nb_agent,
            out_file=INIT_FILE, city_names=TN_CITY_NAMES)
    GenRq(cust=NB_RQ, out_file=RQ_FILE, city_names=TN_CITY_NAMES)

    econ = EconConfig(
        city_names=TN_CITY_NAMES, dist=TN_DIST,
        flight_time_factor=60 / TN_VELOCITY,
        charge_factor=TN_E_DISCHG * 60 / TN_G_I,
        charge_power_kw=TN_G_I,
        price_tables=None,  # no TN LMP/MER data -> revenue-only profit
    )

    # The H2 "#heuristic" directives only take effect under --heuristic=Domain.
    # For long-legged TN with segment counts above the physical ~3, that domain
    # heuristic biases toward long high-revenue flights that overflow the
    # horizon and the search finds no model -- so allow disabling it and fall
    # back to default branch-and-bound (still O1-optimized, still multi-thread).
    solver = Schedule(
        time_limit=TIME_LIMIT, update_time_limit=None, nb_agents=nb_agent, nb_rq=NB_RQ,
        max_segment=nb_segment, encoding="encoding/schedule.lp", network=NETWORK,
        rq_file=RQ_FILE, init_file=INIT_FILE,
        choose_heu=[H2] if domain_heuristic else None, choose_opt=[O1],
        dl_theory=True, horizon=HORIZON, heuristic=domain_heuristic, econ=econ,
    )
    if not domain_heuristic and '-t4' not in solver.control_par:
        solver.control_par += ['-t4']   # keep 4-thread search without the Domain heuristic
    print(f"solver args: {solver.control_par}")
    solver.Solving()

    if not solver.models:
        print("No model found within the time limit.")
        return

    best = solver.models[-1]
    unserved = ComputeUnServedCustomers(best.flight_path_fact_format, NETWORK,
                                        INIT_FILE, RQ_FILE, verbose=False)
    total_demand = NB_RQ * len(TN_CITY_NAMES) * (len(TN_CITY_NAMES) - 1)
    served = total_demand - unserved
    print(f"models found: {len(solver.models)}")
    print(f"best: revenue={best.revenue:.2f} profit={best.profit:.2f} "
          f"run_time={best.run_time:.1f}s empty_flights={best.empty_flight_count}")
    print(f"served customers: {served}/{total_demand} ({served / total_demand:.1%})")

    schedule = schedule_to_json(best.schedule)
    with open(OUT_JSON, "w") as f:
        json.dump(schedule, f, indent=2)
    print(f"wrote {OUT_JSON} ({len(schedule)} agents with real trips)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="TN eVTOL scheduler (real ASP solve).")
    ap.add_argument("--segment", type=int, default=None,
                    help="Fix the segment count (fleet size derived for it). "
                         "Omit to use the joint (agents, segments) optimum.")
    ap.add_argument("--no-domain-heuristic", action="store_true",
                    help="Disable the --heuristic=Domain / H2 search bias and use "
                         "default branch-and-bound. Needed for segment counts above "
                         "TN's physical ~3, where the domain heuristic finds no model.")
    args = ap.parse_args()
    main(fixed_segment=args.segment, domain_heuristic=not args.no_domain_heuristic)
