## Requirements

- Python 3.9 (only Python 3.9 works with clingodl API)
- numpy
- pandas
- clingo & clingo-dl

## Folders & Files

## Usage

**Stage 1: Assign flights and customers**

```sh
clingo encoding/s.lp instances/100rand/rq_94.lp instances/100rand/init_94.lp instances/network_NY_0.lp -c start_seg=1 -c max_seg=13 --heuristic=Domain -t4 --outf=1

clingo-dl T_ITS2025/schedule.lp T_ITS2025/optional/h2.lp T_ITS2025/optional/o2.lp T_ITS2025/instances/exp0/rq_ins4_rq10_agent13_seg10_smp4.lp T_ITS2025/instances/exp0/init_ins4_rq10_agent13_seg10_smp4.lp instances/network_NY_0.lp -c start_seg=1 -c max_seg=10 --heuristic=Domain -t4 --opt-mode=opt --opt-strategy=usc

clingo-dl T_ITS2025/schedule.lp T_ITS2025/optional/h2.lp T_ITS2025/optional/o2.lp T_ITS2025/instances/exp0/rq_ins4_rq10_agent13_seg10_smp4.lp T_ITS2025/instances/exp0/init_ins4_rq10_agent13_seg10_smp4.lp instances/network_NY_0.lp -c start_seg=1 -c max_seg=10 --heuristic=Domain
```

**Stage 2: Switching**

```sh
clingo encoding/sw0.1.lp instances/network_NY_0.lp test_1.lp -c horizon=180 --out-ifs=\\n --out-atomf=%s. --opt-mode=opt
```
> `test_1.lp` is the flight path (ASP facts of predicate `as`).

**Stage 3: Assign time with clingo-dl**

```sh
clingo-dl encoding/time2.lp instances/init.lp instances/network_NY_0.lp test_2.lp -c horizon=180 --out-ifs=\\n --out-atomf=%s.
```
> `test_2.lp` is the flight path.

**Run all stages**

```sh
python solverClingoAPI.py --n_agents=34 --n_rq=30 --horizon=180 --max_segment=13
```

**Additional examples**

```sh
clingo-dl encoding/time0.lp instances/init.lp instances/network_NY_0.lp results/test_as_gate/UNSAT_time0.lp -c horizon=180 --out-ifs=\\n --out-atomf=%s.

clingo-dl encoding/s_t.lp instances/rq_t.lp instances/init.lp instances/network_NY_0.lp -c start_seg=1 -c max_seg=13 --heuristic=Domain -t4 --outf=1

clingo-dl T_ITS2025/schedule.lp instances/init_a74_NY_1.lp instances/rq_30_NY_1.lp T_ITS2025/instances/network_NY.lp T_ITS2025/optional/h2.lp -c start_seg=1 -c max_seg=5 --time-limit=300 -c horizon=180 --heuristic=Domain --outf=1
```


clingo encoding/s.lp instances/network_NY_0.lp instances/rq.lp instances/init.lp --heuristic=Domain -c max_seg=10