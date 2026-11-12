"""Generate a sample greedy schedule for the TN network.

Fleet size is derived from EstimateMinAgentsGivenSegmentsAndCustomers (see
utils/utils.py) given a fixed segment count and per-edge demand, matching the
same formulation used for the NY network's exp0 benchmark. Run from the repo
root: `python gen_schedule_tn.py`.
"""
import json
import random

from constants import TN_CITY_NAMES, TN_DIST, TN_VELOCITY, TN_E_DISCHG, TN_G_I
from utils.utils import EstimateMinAgentsGivenSegmentsAndCustomers
from instances.gen_instance import InitLoc, GenRq
from encoding.baseline_py import NetworkConfig, greedy_by_segment

HORIZON = 180          # minutes
NB_SEGMENTS = 10       # fixed segment count per aircraft
DEMAND_CUST = 30       # requests per directed edge
AIRCRAFT_CAPACITY = 4  # passengers/flight, same convention as the NY network
SEED = 0


def main():
    nb_agent = EstimateMinAgentsGivenSegmentsAndCustomers(
        horizon=HORIZON, b_init=0, demand_cust=DEMAND_CUST,
        aircraft_capacity=AIRCRAFT_CAPACITY, nb_segments=NB_SEGMENTS,
        random_cust=False, nb_vertiports=len(TN_CITY_NAMES))
    nb_agent = int(nb_agent)
    print(f"nb_agent = {nb_agent}, nb_segment = {NB_SEGMENTS}")

    InitLoc(nAgents=nb_agent, seed=SEED, limit_nAgents_each_vertiport=nb_agent,
            out_file="instances/init_TN.lp", city_names=TN_CITY_NAMES)
    GenRq(cust=DEMAND_CUST, out_file="instances/rq_TN.lp", city_names=TN_CITY_NAMES)

    net = NetworkConfig(
        vertiports=TN_CITY_NAMES,
        distance_matrix=TN_DIST,
        flight_time_factor=60 / TN_VELOCITY,
        charge_time_factor=TN_E_DISCHG * 60 / TN_G_I,
        max_operation_time=HORIZON,
        max_customers_per_flight=AIRCRAFT_CAPACITY,
    )

    random.seed(SEED)
    all_routes, total_transported = greedy_by_segment(
        DEMAND_CUST, nb_agent, NB_SEGMENTS, timeout=60, net=net)

    served = int(total_transported.sum())
    total_demand = DEMAND_CUST * net.n * (net.n - 1)
    print(f"served {served}/{total_demand} ({served / total_demand:.1%})")

    schedule = []
    for agent_id, route in enumerate(all_routes):
        if not route:
            continue
        segments = [{
            "segment": seg_num,
            "origin": seg["origin"],
            "destination": seg["dest"],
            "departure_time": seg["minute"],
            "arrival_time": seg["minute"] + seg["flight_time"],
            "people_transported": int(seg["num_customers"]),
        } for seg_num, seg in enumerate(route, 1)]
        schedule.append({"agent_id": agent_id, "segments": segments})

    out_path = "schedule_sample_tn_1.json"
    with open(out_path, "w") as f:
        json.dump(schedule, f, indent=2)
    print(f"wrote {out_path} ({len(schedule)} agents with routes)")


if __name__ == "__main__":
    main()
