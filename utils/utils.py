"""Profit/cost accounting for a schedule and minimum-fleet-size estimation.

`CalProfit` reconstructs each aircraft's timing from the answer set (flight
routes + clingo-dl departure/arrival times), then sums revenue, charging cost,
and emission cost using the time-and-location-dependent LMP/MER price tables.
"""
import os
import re
import sys
import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from constants import (CITY_NAMES as city_names, DIST as dist, VELOCITY as velocity,
                       E_DISCHG as e_dischg, E_MAX as e_max, G_I as g_i,
                       FARE_RATE, EMISSION_FACTOR)

nb_edges = len(city_names) * (len(city_names) - 1)

# Derived rates / unit conversions.
FLIGHT_TIME_FACTOR = 60 / velocity     # flight minutes per mile (= 0.6)
CHARGE_FACTOR = 24 / 25                 # charge minutes per flight minute (= 0.96)
INITIAL_CHARGE_MIN = 25                 # battery (charge-minutes) at the first segment
PRICE_INTERVAL_MIN = 10                 # LMP/MER price granularity (minutes)
MIN_PER_HOUR = 60
KW_PER_MW = 1000
CHARGE_POWER_KW = g_i                   # charging power (kW)


@dataclass
class EconConfig:
    """Bundles the network-specific parameters CalProfit needs, so it isn't
    locked to the NY network's constants and MER/LMP price tables.

    price_tables is {'MER': df, 'LMP': df} indexed by city_names, or None to
    skip charging-cost/emission-cost accounting entirely (e.g. a network with
    no time-and-location price data available) -- revenue is still computed.
    """
    city_names: list
    dist: object
    fare_rate: float = FARE_RATE
    emission_factor: float = EMISSION_FACTOR
    flight_time_factor: float = FLIGHT_TIME_FACTOR
    charge_factor: float = CHARGE_FACTOR
    initial_charge_min: float = INITIAL_CHARGE_MIN
    charge_power_kw: float = CHARGE_POWER_KW
    price_tables: object = None

# Per-step dict keys (a "step" is one flight segment of one agent).
FLIGHT_ATOM = 'flight_atom'             # presence marks a real flight at this step

_FLIGHT_RE = re.compile(r'flight\((\d+),\((\w+),(\w+)\),(\d+),(\d+)\)')
_ARRIVAL_RE = re.compile(r'dl\(arrival\((\d+),\((\w+),(\w+)\),(\d+)\),(\d+)\)')
_START_RE = re.compile(r'dl\(start\((\d+),\((\w+),(\w+)\),(\d+)\),(\d+)\)')


def _load_price_tables():
    """Load the LMP (price) and MER (emission) tables, indexed by vertiport."""
    tables = {
        'MER': pd.read_excel('MER_LMP_Information.xlsx', sheet_name='MER', nrows=7, index_col=0),
        'LMP': pd.read_excel('MER_LMP_Information.xlsx', sheet_name='LMP', nrows=7, index_col=0),
    }
    for t in tables.values():
        t.index = city_names
        t.index.name = 'city'
    return tables


def _parse_schedule(answer_set, df_dist, econ):
    """Parse flight + dl atoms into steps[agent][segment] -> per-step data dict."""
    steps = defaultdict(lambda: defaultdict(dict))
    for token in answer_set.split():
        if token.startswith('dl(arrival'):
            m = _ARRIVAL_RE.match(token)
            if m:
                agent, _dep, arr, step, _t = m.groups()
                steps[int(agent)][int(step)]['destination'] = arr
                # Materialize the next segment so the timing loop's range(len(path))
                # spans it (the original code created it as a parsing side-effect).
                _ = steps[int(agent)][int(step) + 1]
        elif token.startswith('flight('):
            m = _FLIGHT_RE.match(token)
            if m:
                agent, dep, arr, weight, step = m.groups()
                data = steps[int(agent)][int(step)]
                data[FLIGHT_ATOM] = token
                data['weight'] = int(weight)
                data['revenue'] = int(weight) * df_dist.loc[dep, arr] * econ.fare_rate
                data['flight_time'] = df_dist.loc[dep, arr] * econ.flight_time_factor
        elif token.startswith('dl(start'):
            m = _START_RE.match(token)
            if m:
                agent, vertiport, _arr, step, _t = m.groups()
                steps[int(agent)][int(step)]['charge_at_vertiport'] = vertiport
    return steps


def _recompute_timing(steps, econ):
    """Recompute battery, charge time, and departure/arrival times along each route.

    Returns (stationed_route_count, empty_flight_count).
    """
    stationed_route_count = 0
    empty_flight_count = 0
    for agent in range(len(steps)):
        path = steps[agent]
        for step in range(len(path)):
            data = path[step]
            if step == 1:
                data['current_battery'] = econ.initial_charge_min
                path[step + 1]['previous_arrival_time'] = data['flight_time']
            if 'flight_time' in data and data['current_battery'] >= data['flight_time']:
                data['remain_battery'] = data['current_battery'] - data['flight_time']
                data['charge_time'] = 0
            elif 'flight_time' in data:
                data['aftercharge_battery'] = data['flight_time']
                data['charge_time'] = (data['aftercharge_battery'] - data['current_battery']) * econ.charge_factor
                data['remain_battery'] = data['aftercharge_battery'] - data['flight_time']
            if 'remain_battery' in data:
                path[step + 1]['current_battery'] = data['remain_battery']

            if FLIGHT_ATOM in data and 'previous_arrival_time' in data:
                data['departure_time'] = data['previous_arrival_time'] + data['charge_time']
                data['start_charge'] = data['previous_arrival_time']
                data['stop_charge'] = data['start_charge'] + data['charge_time']
            if step != 0 and 'departure_time' in data:
                path[step + 1]['previous_arrival_time'] = data['departure_time'] + data['flight_time']

            if 'destination' in data and 'charge_at_vertiport' in data:
                if data['destination'] == data['charge_at_vertiport']:
                    stationed_route_count += 1
                elif data['weight'] == 0:
                    empty_flight_count += 1
    return stationed_route_count, empty_flight_count


def _charging_window_prices(tables, vertiport, time_arrival, time_depart):
    """MER, LMP, and column labels covering the charging window [arrival, depart]."""
    col = math.floor(time_arrival / PRICE_INTERVAL_MIN)
    next_col = math.ceil(time_depart / PRICE_INTERVAL_MIN)
    mer = tables['MER'].loc[vertiport][col:next_col].tolist()
    lmp = tables['LMP'].loc[vertiport][col:next_col].tolist()
    labels = tables['MER'].columns[col:next_col].tolist()
    return mer, lmp, labels


def _add_charging_and_emission_costs(steps, tables, econ):
    """Fill per-step CHARGING_COST and EMISSION_COST from the time-varying prices."""
    for steps_of_agent in steps.values():
        for data in steps_of_agent.values():
            if not (data.get('charge_time', 0) > 0):
                continue
            mer, lmp, labels = _charging_window_prices(
                tables, data['charge_at_vertiport'], data['start_charge'], data['stop_charge'])
            data['MER'], data['LMP'] = mer, lmp
            if len(labels) > 1:
                # Charging spans several price intervals: weight each by its overlap.
                charging = emission = 0.0
                for i in range(len(labels)):
                    if i == 0:
                        minutes = labels[0] - data['start_charge']
                    elif i == len(labels) - 1:
                        minutes = data['stop_charge'] - labels[i - 1]
                    else:
                        minutes = PRICE_INTERVAL_MIN
                    hours = minutes / MIN_PER_HOUR
                    charging += hours * (lmp[i] / KW_PER_MW) * econ.charge_power_kw
                    emission += hours * (mer[i] * econ.emission_factor / KW_PER_MW) * econ.charge_power_kw
                data['CHARGING_COST'] = charging
                data['EMISSION_COST'] = emission
            else:
                hours = data['charge_time'] / MIN_PER_HOUR
                data['CHARGING_COST'] = hours * (lmp[0] / KW_PER_MW) * econ.charge_power_kw
                data['EMISSION_COST'] = hours * (mer[0] * econ.emission_factor / KW_PER_MW) * econ.charge_power_kw


def CalProfit(answer_set, econ=None):
    """Return (revenue, emission_cost, charging_cost, profit, stationed, empty_flights).

    econ defaults to the NY network (city_names/dist + a freshly-loaded
    MER/LMP price table). Pass an EconConfig for a different network; set its
    price_tables=None to skip charging/emission cost accounting when no price
    data is available for that network (revenue is still computed).
    """
    if econ is None:
        econ = EconConfig(city_names=city_names, dist=dist, price_tables=_load_price_tables())
    df_dist = pd.DataFrame(econ.dist, index=econ.city_names, columns=econ.city_names)

    steps = _parse_schedule(answer_set, df_dist, econ)
    stationed_route_count, empty_flight_count = _recompute_timing(steps, econ)
    if econ.price_tables is not None:
        _add_charging_and_emission_costs(steps, econ.price_tables, econ)

    total_revenue = total_em_cost = total_chg_cost = 0.0
    for steps_of_agent in steps.values():
        for data in steps_of_agent.values():
            if 'CHARGING_COST' in data and not np.isnan(data['CHARGING_COST']):
                total_chg_cost += data['CHARGING_COST']
            if 'EMISSION_COST' in data and not np.isnan(data['EMISSION_COST']):
                total_em_cost += data['EMISSION_COST']
            if 'revenue' in data:
                total_revenue += data['revenue']

    profit = total_revenue - total_em_cost - total_chg_cost
    return (total_revenue, total_em_cost, total_chg_cost, profit,
            stationed_route_count, empty_flight_count)


def EstimateMinAgents(horizon, b_init, demand_cust, aircraft_capacity, random_cust,
                      nb_vertiports=7, dist_matrix=None, velocity_mph=None,
                      e_dischg_rate=None, g_i_rate=None):
    """Estimate the minimum fleet size and route length to serve all demand.

    b_init is the initial battery expressed in charging minutes. dist_matrix /
    velocity_mph / e_dischg_rate / g_i_rate default to the NY network's
    constants; pass a different network's values (e.g. TN_DIST, TN_VELOCITY,
    TN_E_DISCHG, TN_G_I) to estimate fleet size for that network instead.
    """
    if dist_matrix is None:
        dist_matrix = dist
    if velocity_mph is None:
        velocity_mph = velocity
    if e_dischg_rate is None:
        e_dischg_rate = e_dischg
    if g_i_rate is None:
        g_i_rate = g_i
    if random_cust:
        minimum_flights_per_edge = [math.ceil(d / aircraft_capacity) for d in demand_cust]
    else:
        minimum_flights_per_edge = math.ceil(demand_cust / aircraft_capacity)
    require_operation_time = dist_matrix * (60 / velocity_mph + e_dischg_rate * 60 / g_i_rate)
    require_total = np.array(minimum_flights_per_edge) * require_operation_time.flatten()
    min_number_agents = np.ceil(sum(require_total) / (horizon + b_init)).astype(int)
    if random_cust:
        min_number_segments = np.ceil(np.sum(minimum_flights_per_edge) / min_number_agents).astype(int)
    else:
        min_number_segments = np.ceil(
            minimum_flights_per_edge * (nb_vertiports * (nb_vertiports - 1)) / min_number_agents).astype(int)
    return min_number_agents, min_number_segments


def EstimateMinAgentsGivenSegmentsAndCustomers(horizon, b_init, demand_cust,
                                               aircraft_capacity, nb_segments,
                                               random_cust, nb_vertiports=7):
    """Estimate the minimum fleet size given a fixed number of segments."""
    if random_cust:
        minimum_flights_per_edge = [math.ceil(d / aircraft_capacity) for d in demand_cust]
        return np.ceil(sum(minimum_flights_per_edge) / nb_segments).astype(int)
    minimum_flights_per_edge = math.ceil(demand_cust / aircraft_capacity)
    return np.ceil(
        minimum_flights_per_edge * (nb_vertiports * (nb_vertiports - 1)) / nb_segments).astype(int)


if __name__ == "__main__":
    # Self-check on a fixed schedule.
    _SCHEDULE = ('flight(0,(jfk,teb),2,1). flight(9,(teb,cri),4,1). '
                 'dl(arrival(0,(jfk,teb),1),11). dl(start(0,(teb,lga),2),20).')
    print(CalProfit(_SCHEDULE))
