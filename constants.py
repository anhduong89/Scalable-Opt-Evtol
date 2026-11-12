"""Single source of truth for network topology and physical/cost constants.

Previously the 7-vertiport NY distance matrix and the magic numbers below
were duplicated (and in one case diverged) across utils/utils.py,
encoding/baseline_py.py, visualize/visualize.py and instances/gen_network.py.
Import from here instead of redefining.
"""
import numpy as np

# Vertiport names (NY network, 25-mile radius).
CITY_NAMES = ["jfk", "lga", "teb", "ryend", "cri", "cimbl", "dandy"]

# Pairwise distances (miles) between vertiports, indexed by CITY_NAMES.
DIST = np.array([
    [0.,          10.48113508,  18.51467981,  18.54127528,  5.7385456,    13.03650962,  20.09902115],
    [10.48113508,  0.,           9.15619145,   15.04929904,  10.56004164,  6.52505341,   13.22524436],
    [18.51467981,  9.15619145,   0.,           11.47944457,  16.1038714,   6.31668958,   6.33708216 ],
    [18.54127528,  15.04929904,  11.47944457,  0.,           13.32823709,  8.5872692,    6.16996146 ],
    [5.7385456,    10.56004164,  16.1038714,   13.32823709,  0.,           9.86908414,   16.01052999],
    [13.03650962,  6.52505341,   6.31668958,   8.5872692,    9.86908414,   0.,           7.31033037 ],
    [20.09902115,  13.22524436,  6.33708216,   6.16996146,   16.01052999,  7.31033037,   0.         ],
])

# Physical / cost parameters (see paper, Section V).
VELOCITY = 100        # flight speed, mph
E_DISCHG = 4          # discharge rate, kWh/mile
E_MAX = 100           # battery capacity, kWh
G_I = 250             # charging rate, kW
FARE_RATE = 0.5       # fare, $/passenger-mile
EMISSION_FACTOR = 185 # carbon-tax multiplier, $/ton applied to MER

# Vertiport names (TN network): 10 real Tennessee airports, sourced from
# instances/TN_vertiport_location.xlsx. IDs are lowercased FAA/ICAO codes,
# clingo-safe (Elizabethton's "0A9" becomes "a0a9" since an ASP constant may
# not start with a digit). TN_FAA_CODES maps each back to the real FAA code
# for human-facing output (e.g. the schedule JSON).
TN_CITY_NAMES = ["tri", "cha", "rzr", "a0a9", "dkx", "mbt", "gkt", "m54", "mqy", "tha"]
TN_FAA_CODES = {
    "tri": "TRI", "cha": "CHA", "rzr": "RZR", "a0a9": "0A9", "dkx": "DKX",
    "mbt": "MBT", "gkt": "GKT", "m54": "M54", "mqy": "MQY", "tha": "THA",
}

# Pairwise great-circle (haversine) distances (miles) between vertiports,
# indexed by TN_CITY_NAMES, computed from the lat/long coordinates in
# instances/TN_vertiport_location.xlsx (R = 3958.7613 mi). The file's own
# "Summary & Notes" sheet recommends straight-line haversine distances for
# UAM routing over the road/routing values in the raw distance matrix.
TN_DIST = np.array([
    [0.000000, 185.682121, 161.229945, 14.866967, 89.051401, 225.391271, 75.666097, 218.530950, 231.422280, 227.701928],
    [185.682121, 0.000000, 24.693159, 193.456265, 98.546143, 87.969389, 110.128538, 100.932364, 100.028462, 63.489214],
    [161.229945, 24.693159, 0.000000, 168.819842, 75.004246, 100.126467, 85.598652, 108.860437, 111.510787, 82.070341],
    [14.866967, 193.456265, 168.819842, 0.000000, 98.940827, 237.241221, 83.512482, 231.142690, 243.662093, 238.069615],
    [89.051401, 98.546143, 75.004246, 98.940827, 0.000000, 140.350801, 20.691191, 137.255181, 147.981959, 139.135588],
    [225.391271, 87.969389, 100.126467, 237.241221, 140.350801, 0.000000, 159.677898, 21.576790, 12.192062, 34.951430],
    [75.666097, 110.128538, 85.598652, 83.512482, 20.691191, 159.677898, 0.000000, 157.444743, 167.722437, 156.207130],
    [218.530950, 100.932364, 108.860437, 231.142690, 137.255181, 21.576790, 157.444743, 0.000000, 16.501194, 55.567028],
    [231.422280, 100.028462, 111.510787, 243.662093, 147.981959, 12.192062, 167.722437, 16.501194, 0.000000, 46.097350],
    [227.701928, 63.489214, 82.070341, 238.069615, 139.135588, 34.951430, 156.207130, 55.567028, 46.097350, 0.000000],
])

TN_VELOCITY = 170  # flight speed, mph
# charge_time = dist * TN_E_DISCHG * 60 / TN_G_I; chosen so 1 min of charging
# offsets the energy used flying 6 miles (charge_time = dist / 6).
TN_E_DISCHG = 1
TN_G_I = 360
