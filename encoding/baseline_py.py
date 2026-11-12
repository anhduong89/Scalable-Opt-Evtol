import numpy as np
import random
from collections import deque
from dataclasses import dataclass
import argparse
import time
import multiprocessing
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from constants import CITY_NAMES as vertiports, DIST as distance_matrix, VELOCITY, E_DISCHG, G_I
# Vertiport names and distance matrix
N = len(vertiports)

# Parameters
MAX_CUSTOMERS_PER_FLIGHT = 4
MAX_AIRCRAFT_PER_VERTIPORT = 10
MAX_OPERATION_TIME = 180  # minutes (3 hours)
FLIGHT_TIME_FACTOR = 60 / VELOCITY          # flight minutes per mile
CHARGE_TIME_FACTOR = E_DISCHG * 60 / G_I    # charge minutes per flight minute

@dataclass
class NetworkConfig:
    """Bundles the per-network parameters the greedy simulation needs, so it
    isn't locked to the module-level NY constants (vertiports/distance_matrix)."""
    vertiports: list
    distance_matrix: object
    flight_time_factor: float = FLIGHT_TIME_FACTOR
    charge_time_factor: float = CHARGE_TIME_FACTOR
    max_operation_time: int = MAX_OPERATION_TIME
    max_customers_per_flight: int = MAX_CUSTOMERS_PER_FLIGHT

    @property
    def n(self):
        return len(self.vertiports)


DEFAULT_NETWORK = NetworkConfig(vertiports, distance_matrix)


class Aircraft:
    def __init__(self, idx, location, max_segments, max_operation_time=MAX_OPERATION_TIME):
        self.idx = idx
        self.location = location
        self.available_at = 0
        self.segments_served = 0
        self.max_segments = max_segments
        self.time_used = 0
        self.max_operation_time = max_operation_time
        self.route = deque()  # (origin, dest, start_time, end_time, num_customers)

    def is_available(self, current_time):
        segment_limit_ok = (self.max_segments is None) or (self.segments_served < self.max_segments)
        return self.available_at <= current_time and segment_limit_ok and self.time_used <= self.max_operation_time


    def assign_flight(self, origin, dest, current_time, num_customers, flight_time, charge_time):
        self.location = dest
        self.segments_served += 1
        self.time_used += flight_time + charge_time
        self.available_at = current_time + flight_time + charge_time
        self.route.append((origin, dest, current_time, current_time + flight_time, num_customers))

def initialize_aircraft(X, Y, net=DEFAULT_NETWORK):
    aircraft_list = []
    for i in range(X):
        loc = random.randint(0, net.n-1)
        aircraft_list.append(Aircraft(i, loc, Y, max_operation_time=net.max_operation_time))
    return aircraft_list

def initialize_demand(M, net=DEFAULT_NETWORK):
    # demand[i][j] = number of customers from i to j
    demand = np.full((net.n, net.n), M, dtype=int)
    np.fill_diagonal(demand, 0)
    return demand

def find_next_flight(aircraft, demand, current_time, net=DEFAULT_NETWORK):
    # Assign flight based on maximum revenue: 0.5 * edge_distance * num_passengers
    loc = aircraft.location
    best = None
    max_revenue = -1
    for dest in range(net.n):
        if demand[loc][dest] > 0:
            edge_dist = net.distance_matrix[loc][dest]
            max_passengers = min(net.max_customers_per_flight, demand[loc][dest])
            flight_time = int(np.ceil(edge_dist * net.flight_time_factor))
            charge_time = int(np.ceil(edge_dist * net.charge_time_factor))
            total_time = flight_time + charge_time
            if aircraft.time_used + total_time > net.max_operation_time:
                continue
            revenue = 0.5 * edge_dist * max_passengers
            if revenue > max_revenue:
                max_revenue = revenue
                best = (loc, dest, max_passengers, flight_time, charge_time)
    return best

# greedy in time, with timeout using multiprocessing (like greedy_by_segment)
def _greedy_by_time_worker(M, X, result_queue, net=DEFAULT_NETWORK):
    total_transported = np.zeros((net.n, net.n), dtype=int)
    # For this simulation, ignore the segment limit Y for each aircraft
    aircraft_list = initialize_aircraft_no_segment_limit(X, net=net)
    demand = initialize_demand(M, net=net)
    time_step = 0
    all_routes = [[] for _ in range(X)]
    while time_step < net.max_operation_time:
        # print(f"Time step: {time_step}")
        for ac in aircraft_list:
            if ac.available_at <= time_step and ac.time_used < net.max_operation_time:
                next_flight = find_next_flight(ac, demand, time_step, net=net)
                if next_flight:
                    origin, dest, num_customers, flight_time, charge_time = next_flight
                    ac.assign_flight(origin, dest, time_step, num_customers, flight_time, charge_time)
                    demand[origin][dest] -= num_customers
                    total_transported[origin][dest] += num_customers
                    all_routes[ac.idx].append({
                        'minute': time_step,
                        'origin': net.vertiports[origin],
                        'dest': net.vertiports[dest],
                        'num_customers': num_customers,
                        'flight_time': flight_time,
                        'charge_time': charge_time
                    })
        time_step += 1
        if np.sum(demand) == 0:
            break
    result_queue.put((all_routes, total_transported))

def greedy_by_time(M, X, timeout=60, net=DEFAULT_NETWORK):
    print('Starting simulation 1 with timeout...')
    result_queue = multiprocessing.Queue()
    p = multiprocessing.Process(target=_greedy_by_time_worker, args=(M, X, result_queue, net))
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join()
        print("Simulation stopped due to timeout.")
        return [], np.zeros((net.n, net.n), dtype=int)
    if not result_queue.empty():
        return result_queue.get()
    else:
        return [], np.zeros((net.n, net.n), dtype=int)

# Helper: initialize aircraft with no segment limit
def initialize_aircraft_no_segment_limit(X, net=DEFAULT_NETWORK):
    aircraft_list = []
    for i in range(X):
        loc = random.randint(0, net.n-1)
        # Use None to indicate no segment limit
        aircraft_list.append(Aircraft(i, loc, max_segments=None, max_operation_time=net.max_operation_time))
    return aircraft_list

# greedy in segments (loop from 1 to Y, no available check, only horizon check)
def _greedy_by_segment_worker(M, X, Y, result_queue, net=DEFAULT_NETWORK):
    total_transported = np.zeros((net.n, net.n), dtype=int)
    aircraft_list = initialize_aircraft(X, Y, net=net)
    demand = initialize_demand(M, net=net)
    all_routes = [[] for _ in range(X)]

    for seg in range(Y):
        for ac in aircraft_list:
            next_flight = find_next_flight(ac, demand, ac.available_at, net=net)
            if next_flight:
                origin, dest, num_customers, flight_time, charge_time = next_flight
                if ac.time_used + flight_time + charge_time > net.max_operation_time:
                    continue
                ac.assign_flight(origin, dest, ac.available_at, num_customers, flight_time, charge_time)
                demand[origin][dest] -= num_customers
                total_transported[origin][dest] += num_customers
                all_routes[ac.idx].append({
                    'minute': ac.available_at - (flight_time + charge_time),
                    'origin': net.vertiports[origin],
                    'dest': net.vertiports[dest],
                    'num_customers': num_customers,
                    'flight_time': flight_time,
                    'charge_time': charge_time
                })
    # Put result in queue
    result_queue.put((all_routes, total_transported))

def greedy_by_segment(M, X, Y, timeout=60, net=DEFAULT_NETWORK):
    print('Starting simulation 2 with segments...')
    result_queue = multiprocessing.Queue()
    p = multiprocessing.Process(target=_greedy_by_segment_worker, args=(M, X, Y, result_queue, net))
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join()
        print("Simulation stopped due to timeout.")
        return [], np.zeros((net.n, net.n), dtype=int)
    if not result_queue.empty():
        return result_queue.get()
    else:
        return [], np.zeros((net.n, net.n), dtype=int)

def print_solution(routes):
    for idx, route in enumerate(routes):
        print(f"Aircraft {idx}:")
        for flight_num, seg in enumerate(route, 1):
            print(f"  Flight {flight_num:2d} | t={seg['minute']:3d}: {seg['origin']} -> {seg['dest']} | customers={seg['num_customers']} | flight={seg['flight_time']}min | charge={seg['charge_time']}min")
        print()

def run_greedy_by_time(cust, agent, seg):
    start_time = time.time()
    _, total_transported = greedy_by_time(cust, agent, seg)
    end_time = time.time()

    print(f"Total running time: {end_time - start_time:.3f} seconds")

    print("\nTotal transported customers per edge:")
    for i in range(N):
        for j in range(N):
            if i != j and total_transported[i][j] > 0:
                print(f"{vertiports[i]} -> {vertiports[j]}: {total_transported[i][j]}")

    total_customers_served = np.sum(total_transported)
    total_initial_demand = cust * N * (N - 1)
    served_ratio = total_customers_served / total_initial_demand
    print(f"Total served customers: {total_customers_served}/{total_initial_demand} ({served_ratio:.2%})")
    return round(served_ratio, 2), end_time-start_time

    
def run_greedy_by_segment(cust, agent, seg):
    start_time = time.time()
    _, total_transported = greedy_by_segment(cust, agent, seg)
    end_time = time.time()

    print(f"Total running time: {end_time - start_time:.3f} seconds")

    print("\nTotal transported customers per edge:")
    for i in range(N):
        for j in range(N):
            if i != j and total_transported[i][j] > 0:
                print(f"{vertiports[i]} -> {vertiports[j]}: {total_transported[i][j]}")

    total_customers_served = np.sum(total_transported)
    total_initial_demand = cust * N * (N - 1)
    served_ratio = total_customers_served / total_initial_demand
    print(f"Total served customers: {total_customers_served}/{total_initial_demand} ({served_ratio:.2%})")
    return round(served_ratio, 2), end_time - start_time
if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--M', type=int, default=150, help='Number of customers per edge')
    parser.add_argument('--X', type=int, default=160, help='Number of aircraft')
    parser.add_argument('--Y', type=int, default=10, help='Max segments per aircraft')
    args = parser.parse_args()
    start_time = time.time()
    routes, total_transported = greedy_by_time(args.M, args.X)
    print_solution(routes)
    # Count number of aircraft at each vertiport at the end
    aircraft_at_vertiport = [0] * N
    for ac in routes:
        if ac:
            last_flight = ac[-1]
            dest_idx = vertiports.index(last_flight['dest'])
            aircraft_at_vertiport[dest_idx] += 1
    print("\nNumber of aircraft at each vertiport at the end:")
    for idx, count in enumerate(aircraft_at_vertiport):
        print(f"{vertiports[idx]}: {count}")
    print("\nArrival time at the end vertiport of each aircraft:")
    for idx, ac in enumerate(routes):
        if ac:
            last_flight = ac[-1]
            arrival_time = last_flight['minute'] + last_flight['flight_time']
            print(f"Aircraft {idx}: {last_flight['dest']} at t={arrival_time}")
    end_time = time.time()
    print(f"Total running time: {end_time - start_time:.3f} seconds")

    print("\nTotal transported customers per edge:")
    for i in range(N):
        for j in range(N):
        # if i != j and total_transported[i][j] > 0:
            print(f"{vertiports[i]} -> {vertiports[j]}: {total_transported[i][j]}")
        # if i != j and total_transported[i][j] > 0:
            edge_dist = distance_matrix[i][j]
            flight_time = int(np.ceil(edge_dist * 0.6))
            charge_time = int(np.ceil(edge_dist * 24 / 25))
            print(f"operation time= {flight_time + charge_time} minutes")
    
    total_customers_served = np.sum(total_transported)
    total_initial_demand = args.M * N * (N - 1)
    served_ratio = total_customers_served / total_initial_demand
    print(f"Total served customers: {total_customers_served}/{total_initial_demand} ({served_ratio:.2%})")