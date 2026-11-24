# Scalable Optimization eVTOL Aircraft Scheduling with Hybrid Answer Set Programming

This repository schedules a fleet of electric vertical-take-off-and-landing (eVTOL) aircraft
over a network of vertiports — deciding which flights to fly, how many
passengers to carry, and the departure/arrival/charging times — using
Answer Set Programming with difference constraints (clingo + clingo-dl).

## Requirements

The clingo-dl Python API requires **Python 3.9** and is distributed through the
`potassco` conda channel, so a conda environment is required:

```sh
conda env create -f environment.yml
conda activate evtol-py3.9
```

This installs clingo 5.6.2, clingo-dl 1.4.0, numpy, pandas, openpyxl, and
(for the visualizer) matplotlib and networkx.

> Run all commands from the repository root — paths to `encoding/`,
> `instances/`, and `MER_LMP_Information.xlsx` are resolved relative to it.

## Repository layout

See [WORKFLOW.md](WORKFLOW.md) for how the pieces fit together (which file and
function is used in each step).

| Path | Description |
|------|-------------|
| `encoding/schedule.lp` | Core ASP encoding: routing + clingo-dl timing constraints. |
| `encoding/optional/` | Optional objective/heuristic modules (see mapping below). |
| `encoding/baseline.lp`, `encoding/baseline_py.py` | 1-segment look-ahead greedy baseline. |
| `encoding/compute_revenue.lp` | Computes served customers / revenue from a schedule. |
| `solverClingoAPI.py` | `Schedule` / `BaselineSchedule` solving API around clingo. |
| `run_experiments.py` | Experiment driver (instance generation + benchmark runs). |
| `constants.py` | Network (vertiports, distances) and physical/cost constants. |
| `instances/` | `network.lp`, the `exp0/` benchmark instances, and generators. |
| `utils/utils.py` | Profit/cost computation (`CalProfit`) and fleet-size estimation. |
| `visualize/` | Schedule trajectory plotting. |
| `results/` | Benchmark result CSVs and figures. |

## Optimization / heuristic modules

| Module | Objective |
|--------|-----------|
| `optional/o1.lp` | Maximize revenue |
| `optional/o2.lp` | Minimize unserved customers |
| `optional/o3.lp` | Minimize empty flights |
| `optional/h1.lp` | Prioritize full-load flights |
| `optional/h2.lp` | Prioritize full-load flights in ascending segment order |

## Reproducing the experiments

The driver in `run_experiments.py` runs the benchmark over demand sizes
`p ∈ {10, 20, 50, 100, 150, 200}`, 5 samples each, for every configuration
(`Greedy, O1, O2, O3, H1, H2, O1H2, O2H2, O3H2`):

```sh
python run_experiments.py
```

For each configuration it writes a CSV `exp0_<config>.csv` with the served
customer percentage, profit, and runtime, and stores the final answer set
(`flight` + `dl` atoms) for every (instance, configuration) pair under
`results/answer_sets/<config>/`.

To regenerate the benchmark instances from scratch (overwrites `instances/exp0/`),
call `CreateInstance()` from `run_experiments.py`.

## Running the encoding directly

You can also invoke the encoding with the clingo-dl command line, e.g.:

```sh
clingo-dl encoding/schedule.lp encoding/optional/h2.lp \
  instances/network.lp \
  instances/exp0/rq_ins0_rq10_agent13_seg10_smp0.lp \
  instances/exp0/init_ins0_rq10_agent13_seg10_smp0.lp \
  -c start_seg=1 -c max_seg=10 -c horizon=180 --heuristic=Domain
```

## License

MIT — see `LICENSE`.

## Acknowledgment

This material is based upon work supported by the NASA Aeronautics Research
Mission Directorate (ARMD) University Leadership Initiative (ULI) under
cooperative agreement number 80NSSC23M0059.
