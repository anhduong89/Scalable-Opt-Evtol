"""Generate the vertiport network facts used by the encodings.

Writes instances/network.lp: vertiport / distance / flight_time / charge_time /
edge facts plus the edge_loop rule, derived from constants.py.
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from constants import (CITY_NAMES, DIST, VELOCITY, E_DISCHG, G_I,
                        TN_CITY_NAMES, TN_DIST, TN_VELOCITY, TN_E_DISCHG, TN_G_I)


class GenerateMapGivenPath:
    def __init__(self, city_names=CITY_NAMES, dist=DIST, velocity=VELOCITY,
                 e_dischg=E_DISCHG, g_i=G_I, out_file="instances/network.lp"):
        self.out_file = out_file
        # Vertiport network (single source of truth: constants.py).
        self.vPort_id = list(city_names)
        self.vPort_print = ";".join(city_names)
        self.dist = pd.DataFrame(dist, self.vPort_id, self.vPort_id)
        # flight / charge time per edge in minutes (integer-rounded)
        self.flight_time = np.round(self.dist * (60 / velocity)).astype(int)
        self.charge_time = np.round(self.dist * e_dischg * 60 / g_i).astype(int)

        self.distance_print = [[(i, j), int(np.round(self.dist[i][j]))]
                               for i in self.vPort_id for j in self.vPort_id]
        self.flight_time_print = [[(i, j), int(self.flight_time[i][j])]
                                  for i in self.vPort_id for j in self.vPort_id]
        self.charge_time_print = [[(i, j), int(self.charge_time[i][j])]
                                  for i in self.vPort_id for j in self.vPort_id]

    def run(self):
        with open(self.out_file, "w+") as f:
            f.write('vertiport' + str(tuple(self.vPort_print)).replace("'", "").replace(', ', '') + '.\n')
            f.write('% distance= miles/10\n')
            for i in self.distance_print:
                f.write('distance' + str(tuple(i)).replace("'", "") + '.\n')
            for i in self.flight_time_print:
                f.write('flight_time' + str(tuple(i)).replace("'", "") + '.\n')
            for i in self.charge_time_print:
                f.write('charge_time' + str(tuple(i)).replace("'", "") + '.\n')
            for i in self.vPort_id:
                for j in self.vPort_id:
                    f.write('edge((' + i + ',' + j + ')).\n')
            f.write('\nedge_loop((V,V)) :- edge((V,V)).\n')


if __name__ == '__main__':
    GenerateMapGivenPath().run()
    GenerateMapGivenPath(TN_CITY_NAMES, TN_DIST, TN_VELOCITY, TN_E_DISCHG, TN_G_I,
                         out_file="instances/network_TN.lp").run()
