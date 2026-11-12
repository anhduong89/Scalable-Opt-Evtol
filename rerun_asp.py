"""Re-run one ASP configuration over the full exp0 benchmark on the current
machine, writing to a separate results directory so earlier runs are kept.

    python rerun_asp.py <CONFIG> [--out results/auco]

Writes <out>/exp0_<CONFIG>.csv (+ .pkl) and <out>/answer_sets/<CONFIG>/.
Resumable: instances already present in the CSV are skipped.
"""
import argparse
import os
import pickle
import platform
import time

import run_experiments as R


def existing_rows(csv_file):
    if not os.path.exists(csv_file) or os.stat(csv_file).st_size == 0:
        return 0
    with open(csv_file) as f:
        return sum(1 for _ in f) - 1  # minus header


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", choices=[c.name for c in R.CONFIGS])
    ap.add_argument("--out", default="results/auco")
    args = ap.parse_args()

    config = next(c for c in R.CONFIGS if c.name == args.config)
    os.makedirs(args.out, exist_ok=True)
    csv_file = os.path.join(args.out, f"exp0_{config.name}.csv")
    as_dir = os.path.join(args.out, "answer_sets")
    start_i = existing_rows(csv_file)
    total = len(R.DEMAND_SIZES) * R.NB_SAMPLE
    print(f"{config.name} on {platform.node()}: TIME_LIMIT={R.TIME_LIMIT}s, "
          f"resuming at {start_i}/{total}", flush=True)

    t0 = time.time()
    for i_n in range(start_i, total):
        nb_rq = R.DEMAND_SIZES[i_n // R.NB_SAMPLE]
        smp = i_n % R.NB_SAMPLE
        nb_agent, nb_segment = R.EstimateMinAgents(
            horizon=R.HORIZON, b_init=0, demand_cust=nb_rq,
            aircraft_capacity=R.AIRCRAFT_CAPACITY, random_cust=False)
        iid = f"ins{i_n}_rq{nb_rq}_agent{nb_agent}_seg{nb_segment}_smp{smp}"
        rq = f"instances/exp0/rq_{iid}.lp"
        init = f"instances/exp0/init_{iid}.lp"
        res = R.run_config(config, iid, nb_agent, nb_rq, nb_segment, rq, init, as_dir=as_dir)
        R._append_csv(csv_file, res)
        print(f"[{time.time()-t0:8.0f}s] {config.name} {iid} -> "
              f"{ {k: v for k, v in res.items() if config.name in k} }", flush=True)

    import csv
    with open(csv_file) as f:
        rows = list(csv.DictReader(f))
    with open(f"{csv_file}.pkl", "wb") as f:
        pickle.dump(rows, f)
    print(f"=== done {config.name} ({time.time()-t0:.0f}s) ===", flush=True)


if __name__ == "__main__":
    main()
