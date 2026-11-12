"""Re-run only the O2 and O2H2 (= H2O2) configurations over the full exp0
benchmark, after the aggregate-free rewrite of encoding/optional/o2.lp.

Backs up and overwrites results/exp0_O2.csv and results/exp0_O2H2.csv so the
new numbers replace the old (timed-out) ones rather than being appended.
"""
import os
import pickle
import shutil
import time

import run_experiments as R

TARGETS = ["O2", "O2H2"]


def main():
    configs = [c for c in R.CONFIGS if c.name in TARGETS]
    print(f"Re-running configs: {[c.name for c in configs]}")
    print(f"TIME_LIMIT={R.TIME_LIMIT}s, sizes={R.DEMAND_SIZES}, samples={R.NB_SAMPLE}")
    t0 = time.time()
    for config in configs:
        csv_file = f"results/exp0_{config.name}.csv"
        # back up then start fresh so _append_csv does not duplicate old rows
        for suffix in ("", ".pkl"):
            p = csv_file + suffix
            if os.path.exists(p):
                shutil.copy2(p, p + ".bak")
        open(csv_file, "w").close()  # truncate

        rows = []
        i_n = 0
        for nb_rq in R.DEMAND_SIZES:
            for smp in range(R.NB_SAMPLE):
                nb_agent, nb_segment = R.EstimateMinAgents(
                    horizon=R.HORIZON, b_init=0, demand_cust=nb_rq,
                    aircraft_capacity=R.AIRCRAFT_CAPACITY, random_cust=False)
                iid = f"ins{i_n}_rq{nb_rq}_agent{nb_agent}_seg{nb_segment}_smp{smp}"
                rq = f"instances/exp0/rq_{iid}.lp"
                init = f"instances/exp0/init_{iid}.lp"
                res = R.run_config(config, iid, nb_agent, nb_rq, nb_segment, rq, init)
                R._append_csv(csv_file, res)
                rows.append(res)
                print(f"[{time.time()-t0:8.0f}s] {config.name} {iid} -> "
                      f"{ {k: v for k, v in res.items() if config.name in k} }",
                      flush=True)
                i_n += 1
        with open(f"{csv_file}.pkl", "wb") as f:
            pickle.dump(rows, f)
        print(f"=== done {config.name} ({time.time()-t0:.0f}s elapsed) ===", flush=True)
    print(f"ALL DONE in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
