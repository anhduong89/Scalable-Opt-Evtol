import numpy as np
import random
from collections import deque
import argparse
import time
import signal
import threading
import multiprocessing
# Vertiport names and distance matrix
vertiports = ["jfk", "lga", "teb", "ryend", "cri", "cimbl", "dandy"]
N = len(vertiports)
distance_matrix = np.array([
    [0.,          10.48113508,  18.51467981,  18.54127528,  5.7385456,    13.03650962,  20.09902115], 
    [10.48113508,  0.,           9.15619145,   15.04929904,  10.56004164,  6.52505341,   13.22524436],
    [18.51467981,  9.15619145,   0.,           11.47944457,  16.1038714,   6.31668958,   6.33708216 ],
    [18.54127528,  15.04929904,  11.47944457,  0.,           13.32823709,  8.5872692,    6.16996146 ],
    [5.7385456,    10.56004164,  16.1038714,   13.32823709,  0.,           9.86908414,   16.01052999],
    [13.03650962,  6.52505341,   6.31668958,   8.5872692,    9.86908414,   0.,           7.31033037 ],
    [20.09902115,  13.22524436,  6.33708216,   6.16996146,   16.01052999,  7.31033037,   0.  ]
])

# Parameters
MAX_CUSTOMERS_PER_FLIGHT = 4
MAX_AIRCRAFT_PER_VERTIPORT = 10
MAX_OPERATION_TIME = 180  # minutes (3 hours)

class Aircraft:
    def __init__(self, idx, location, max_segments):
        self.idx = idx
        self.location = location
        self.available_at = 0
        self.segments_served = 0
        self.max_segments = max_segments
        self.time_used = 0
        self.route = deque()  # (origin, dest, start_time, end_time, num_customers)

    def is_available(self, current_time):
        segment_limit_ok = (self.max_segments is None) or (self.segments_served < self.max_segments)
        return self.available_at <= current_time and segment_limit_ok and self.time_used <= MAX_OPERATION_TIME


    def assign_flight(self, origin, dest, current_time, num_customers, flight_time, charge_time):
        self.location = dest
        self.segments_served += 1
        self.time_used += flight_time + charge_time
        self.available_at = current_time + flight_time + charge_time
        self.route.append((origin, dest, current_time, current_time + flight_time, num_customers))

def initialize_aircraft(X, Y):
    aircraft_list = []
    for i in range(X):
        loc = random.randint(0, N-1)
        aircraft_list.append(Aircraft(i, loc, Y))
    return aircraft_list

def initialize_demand(M):
    # demand[i][j] = number of customers from i to j
    demand = np.full((N, N), M, dtype=int)
    np.fill_diagonal(demand, 0)
    return demand

def find_next_flight(aircraft, demand, current_time):
    # Assign flight based on maximum revenue: 0.5 * edge_distance * num_passengers
    loc = aircraft.location
    best = None
    max_revenue = -1
    for dest in range(N):
        if demand[loc][dest] > 0:
            edge_dist = distance_matrix[loc][dest]
            max_passengers = min(MAX_CUSTOMERS_PER_FLIGHT, demand[loc][dest])
            flight_time = int(np.ceil(edge_dist * 0.6))
            charge_time = int(np.ceil(edge_dist * 24 / 25))
            total_time = flight_time + charge_time
            if aircraft.time_used + total_time > MAX_OPERATION_TIME:
                continue
            revenue = 0.5 * edge_dist * max_passengers
            if revenue > max_revenue:
                max_revenue = revenue
                best = (loc, dest, max_passengers, flight_time, charge_time)
    return best

# greedy in time, with timeout using multiprocessing (like simulate2)
def simulate_worker(M, X, result_queue):
    total_transported = np.zeros((N, N), dtype=int)
    # For this simulation, ignore the segment limit Y for each aircraft
    aircraft_list = initialize_aircraft_no_segment_limit(X)
    demand = initialize_demand(M)
    time_step = 0
    all_routes = [[] for _ in range(X)]
    while time_step < MAX_OPERATION_TIME:
        # print(f"Time step: {time_step}")
        for ac in aircraft_list:
            if ac.available_at <= time_step and ac.time_used < MAX_OPERATION_TIME:
                next_flight = find_next_flight(ac, demand, time_step)
                if next_flight:
                    origin, dest, num_customers, flight_time, charge_time = next_flight
                    ac.assign_flight(origin, dest, time_step, num_customers, flight_time, charge_time)
                    demand[origin][dest] -= num_customers
                    total_transported[origin][dest] += num_customers
                    all_routes[ac.idx].append({
                        'minute': time_step,
                        'origin': vertiports[origin],
                        'dest': vertiports[dest],
                        'num_customers': num_customers,
                        'flight_time': flight_time,
                        'charge_time': charge_time
                    })
        time_step += 1
        if np.sum(demand) == 0:
            break
    result_queue.put((all_routes, total_transported))

def simulate(M, X, timeout=60):
    print('Starting simulation 1 with timeout...')
    result_queue = multiprocessing.Queue()
    p = multiprocessing.Process(target=simulate_worker, args=(M, X, result_queue))
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join()
        print("Simulation stopped due to timeout.")
        return [], np.zeros((N, N), dtype=int)
    if not result_queue.empty():
        return result_queue.get()
    else:
        return [], np.zeros((N, N), dtype=int)

# Helper: initialize aircraft with no segment limit
def initialize_aircraft_no_segment_limit(X):
    aircraft_list = []
    for i in range(X):
        loc = random.randint(0, N-1)
        # Use None to indicate no segment limit
        aircraft_list.append(Aircraft(i, loc, max_segments=None))
    return aircraft_list

# Modify Aircraft class to handle None as unlimited segments
# (You need to update the is_available method in Aircraft class as follows:)
# def is_available(self, current_time):
#     segment_limit_ok = (self.max_segments is None) or (self.segments_served < self.max_segments)
#     return self.available_at <= current_time and segment_limit_ok and self.time_used < MAX_OPERATION_TIME

# greedy in segments (loop from 1 to Y, no available check, only horizon check)
def simulate2_worker(M, X, Y, result_queue):
    total_transported = np.zeros((N, N), dtype=int)
    aircraft_list = initialize_aircraft(X, Y)
    demand = initialize_demand(M)
    all_routes = [[] for _ in range(X)]

    for seg in range(Y):
        for ac in aircraft_list:
            next_flight = find_next_flight(ac, demand, ac.available_at)
            if next_flight:
                origin, dest, num_customers, flight_time, charge_time = next_flight
                if ac.time_used + flight_time + charge_time > MAX_OPERATION_TIME:
                    continue
                ac.assign_flight(origin, dest, ac.available_at, num_customers, flight_time, charge_time)
                demand[origin][dest] -= num_customers
                total_transported[origin][dest] += num_customers
                all_routes[ac.idx].append({
                    'minute': ac.available_at - (flight_time + charge_time),
                    'origin': vertiports[origin],
                    'dest': vertiports[dest],
                    'num_customers': num_customers,
                    'flight_time': flight_time,
                    'charge_time': charge_time
                })
    # Put result in queue
    result_queue.put((all_routes, total_transported))

def simulate2(M, X, Y, timeout=60):
    print('Starting simulation 2 with segments...')
    result_queue = multiprocessing.Queue()
    p = multiprocessing.Process(target=simulate2_worker, args=(M, X, Y, result_queue))
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join()
        print("Simulation stopped due to timeout.")
        return [], np.zeros((N, N), dtype=int)
    if not result_queue.empty():
        return result_queue.get()
    else:
        return [], np.zeros((N, N), dtype=int)

def print_solution(routes):
    for idx, route in enumerate(routes):
        print(f"Aircraft {idx}:")
        for flight_num, seg in enumerate(route, 1):
            print(f"  Flight {flight_num:2d} | t={seg['minute']:3d}: {seg['origin']} -> {seg['dest']} | customers={seg['num_customers']} | flight={seg['flight_time']}min | charge={seg['charge_time']}min")
        print()

class TimeoutException(Exception):
    pass

def handler(signum, frame):
    raise TimeoutException("Timeout!")

def GreedyAlg(cust, agent, seg):


    start_time = time.time()
    _, total_transported = simulate(cust, agent, seg)
    end_time = time.time()
    signal.alarm(0)  # Disable the alarm

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
    return round(served_ratio, 2), '', end_time-start_time

    
def GreedyAlg2(cust, agent, seg):
    start_time = time.time()
    _, total_transported = simulate2(cust, agent, seg)
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
    return round(served_ratio, 2), '', end_time - start_time
if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--M', type=int, default=150, help='Number of customers per edge')
    parser.add_argument('--X', type=int, default=160, help='Number of aircraft')
    parser.add_argument('--Y', type=int, default=10, help='Max segments per aircraft')
    args = parser.parse_args()
    start_time = time.time()
    routes, total_transported = simulate(args.M, args.X)
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