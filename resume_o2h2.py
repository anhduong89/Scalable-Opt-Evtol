"""Resume the O2H2 (= H2O2) re-run after the reboot.

O2 already completed (30/30). O2H2 has the first N rows; this appends the
remaining instances to results/exp0_O2H2.csv WITHOUT truncating. Re-runnable:
it always starts from however many data rows already exist, so a second crash
just means running it again. When all 30 are present it rebuilds the pkl and
regenerates the tables + plots.
"""
import csv
import os
import pickle
import time

import run_experiments as R

CSV = "results/exp0_O2H2.csv"
CONFIG = [c for c in R.CONFIGS if c.name == "O2H2"][0]
TOTAL = len(R.DEMAND_SIZES) * R.NB_SAMPLE  # 30


def existing_rows():
    if not os.path.exists(CSV) or os.stat(CSV).st_size == 0:
        return 0
    with open(CSV) as f:
        return sum(1 for _ in f) - 1  # minus header


def main():
    start_i = existing_rows()
    print(f"Resuming {CONFIG.name}: {start_i}/{TOTAL} already done; "
          f"running instances {start_i}..{TOTAL-1}", flush=True)
    t0 = time.time()
    for i_n in range(start_i, TOTAL):
        nb_rq = R.DEMAND_SIZES[i_n // R.NB_SAMPLE]
        smp = i_n % R.NB_SAMPLE
        nb_agent, nb_segment = R.EstimateMinAgents(
            horizon=R.HORIZON, b_init=0, demand_cust=nb_rq,
            aircraft_capacity=R.AIRCRAFT_CAPACITY, random_cust=False)
        iid = f"ins{i_n}_rq{nb_rq}_agent{nb_agent}_seg{nb_segment}_smp{smp}"
        rq = f"instances/exp0/rq_{iid}.lp"
        init = f"instances/exp0/init_{iid}.lp"
        res = R.run_config(CONFIG, iid, nb_agent, nb_rq, nb_segment, rq, init)
        R._append_csv(CSV, res)
        print(f"[{time.time()-t0:7.0f}s] {CONFIG.name} {iid} -> "
              f"{ {k: v for k, v in res.items() if CONFIG.name in k} }", flush=True)

    # rebuild pkl from the full CSV
    with open(CSV) as f:
        rows = list(csv.DictReader(f))
    with open(CSV + ".pkl", "wb") as f:
        pickle.dump(rows, f)
    print(f"=== O2H2 complete ({existing_rows()}/{TOTAL}) ===", flush=True)

    # regenerate artifacts
    print("Regenerating tables + plots...", flush=True)
    import make_tables
    make_tables.main()
    import make_plots
    make_plots.main()
    o2_to = sum(1 for r in open("results/exp0_O2.csv") if ",TO," in r)
    h_to = sum(1 for r in open("results/exp0_O2H2.csv") if ",TO," in r)
    print(f"Remaining TO rows: O2={o2_to}  O2H2={h_to}", flush=True)
    print("RESUME DONE", flush=True)


if __name__ == "__main__":
    main()
