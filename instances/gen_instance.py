import os
import random
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from constants import CITY_NAMES as vPort_id

def InitLoc(nAgents, seed=None, limit_nAgents_each_vertiport=6, out_file='instances/init.lp',
            city_names=vPort_id):
    random.seed(seed)
    emax_print = [[i, 60] for i in range(0, nAgents)]
    emin_print = [[i, 0] for i in range(0, nAgents)]
    dischg_rate_print = [[i, 4] for i in range(0, nAgents)]
    capacity_print = [[i, 4] for i in range(0, nAgents)]
    init_loc_print = []
    # init_loc = np.arange(nAgents)%(len(vPort_id))
    init_loc = []
    counts = {}
    if seed != None:
        for i in range(nAgents):
            while True:
                val = random.randint(0, len(city_names)-1)
                if counts.get(val, 0) < limit_nAgents_each_vertiport:
                    counts[val] = counts.get(val, 0) + 1
                    init_loc.append(val)
                    break
        for i in range(0, nAgents):
            init_loc_print += [[i, city_names[init_loc[i]]]]
    else:
        for i in range(nAgents):
            init_loc_print += [[i, city_names[i%len(city_names)]]]

    init_battery_print = [[i, 60] for i in range(0, nAgents)]

    variable = [init_loc_print, emax_print, emin_print, dischg_rate_print, capacity_print, init_battery_print]
    atoms_name = ['init_loc', 'emax', 'emin', 'dischg_rate', 'capacity', 'b_init']

    with open(out_file, "w+") as out:
        out.write('agent(0..' + str(nAgents - 1) + ').\n')
        out.write("%battery in minute.\n")
        for var, atom_name in zip(variable, atoms_name):
            for row in var:
                out.write(atom_name + str(tuple(row)).replace("'", "") + '.\n')



    
def GenRq(cust=None, random_flag=False, out_file='instances/rq.lp', city_names=vPort_id):


    request_p = [[j, i] for i in range(0, len(city_names)) for j in range(0, len(city_names))]
    matrix_out = [[random.randint(0, cust) if i!=j else 0 for j in range(0, len(city_names))] for i in range(0, len(city_names))]

    request_p = [[city_names[m[0]], city_names[m[1]]]for m in request_p]
    request_print = []
    total_edge = len(city_names) * (len(city_names))
    for i in range(0, total_edge):
        no = i
        origin = request_p[i][0]
        destination = request_p[i][1]
        if not random_flag:
            request_print += [[no, (origin, destination), cust]] if origin != destination else [[no, (origin, destination), 0]]
        else:
            cust_rand = matrix_out[city_names.index(origin)][city_names.index(destination)]
            request_print += [[no, (origin, destination), cust_rand]]

    f = open(out_file,"w+")
    f.write(f'%{matrix_out}')
    f.write('%request(ID, (edge), number of request passenger)\n')
    for i in request_print:
        f.write('request' + str(tuple(i)).replace("'","") + '.\n')
    f.close()
    
    if random_flag:
        return [req[2] for req in request_print]


if __name__ == '__main__':
    InitLoc(34)
    GenRq(30)