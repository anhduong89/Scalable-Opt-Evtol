"""Generate the LaTeX result tables from results/exp0_*.csv.

Reads one CSV per configuration (all share the same 30-instance grid: 6 demand
sizes x 5 samples, in order), and emits two `table*` environments:

  table1.tex: Greedy, O3, H2, O1H2, O2H2, O3H2
  table2.tex: O1, O2, H1

Each table lists the 30 instances numbered 1..30, with an AVG$\\pm$STD row after
every block of 5 samples. `served` is a percentage, `pf` is profit ($), `RT` is
run time (s). Timeouts are stored as the literal "TO" (run time = 300).
"""
import csv
import os
import statistics

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
NB_SAMPLE = 5

# config key -> LaTeX header label
LABELS = {
    "Greedy": "Greedy",
    "O1":  r"O{\scriptsize$1$}",
    "O2":  r"O{\scriptsize$2$}",
    "O3":  r"O{\scriptsize$3$}",
    "H1":  r"H{\scriptsize$1$}",
    "H2":  r"H{\scriptsize$2$}",
    "O1H2": r"H{\scriptsize$2$}O{\scriptsize$1$}",
    "O2H2": r"H{\scriptsize$2$}O{\scriptsize$2$}",
    "O3H2": r"H{\scriptsize$2$}O{\scriptsize$3$}",
}

TABLE1 = ["Greedy", "O3", "H2", "O1H2", "O2H2", "O3H2"]
TABLE2 = ["O1", "O2", "H1"]


def load(config):
    """Return list of 30 dicts with keys nb_agent, nb_rq, served, pf, rt."""
    path = os.path.join(RESULTS_DIR, f"exp0_{config}.csv")
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append({
                "nb_agent": int(r["nb_agent"]),
                "nb_rq": int(r["nb_rq"]),
                "served": r[f"served_customers_{config}"],
                "pf": r[f"profit_{config}"],
                "rt": int(r[f"run_time_{config}"]),
            })
    return rows


def fmt_mean_std(vals):
    """Format a list of numbers as 'mean' (std 0) or 'mean$\\pm$std'."""
    mean = statistics.mean(vals)
    std = statistics.stdev(vals) if len(vals) > 1 else 0.0
    mstr = str(int(round(mean))) if abs(mean - round(mean)) < 1e-9 else f"{mean:.1f}"
    if std < 1e-9:
        return mstr
    return f"{mstr}" + r"$\pm$" + f"{std:.2f}"


def cell_value(raw):
    """Per-instance cell: 'TO' stays 'TO', numbers stay as-is."""
    return raw


def block_stats(block, key):
    """AVG cell for a block; 'TO' if every sample timed out (only for served/pf)."""
    numeric = [int(b[key]) for b in block if b[key] != "TO"]
    if not numeric:
        return "TO"
    return fmt_mean_std(numeric)


def rt_block_stats(block):
    return fmt_mean_std([b["rt"] for b in block])


def build_table(configs, caption, label, resize, sideways=False):
    rows = {c: load(c) for c in configs}
    n = len(rows[configs[0]])
    ncfg = len(configs)

    # column spec: Sample | aircraft | customers | (served|pf|RT) per config
    colspec = "|c|c|c|" + "c|c|c|" * ncfg

    env = "sidewaystable*" if sideways else "table*"
    out = []
    out.append(r"\begin{" + env + ("}" if sideways else "}[htbp]"))
    out.append(r"\caption{" + caption + "}")
    out.append(r"\centering")
    out.append(r"\resizebox{" + resize + r"}{!}{")
    out.append(r"\begin{tabular}{" + colspec + "}")
    out.append(r"\hline")

    # header row 1: grouped config labels
    h1 = ["Sample", "Number of", "Number of"]
    for c in configs:
        h1.append(r"\multicolumn{3}{c|}{" + LABELS[c] + "}")
    out.append("&".join(h1) + r"\\")
    # header row 2
    h2 = ["", "aircraft", "customers"] + ["served & pf & RT"] * ncfg
    out.append("&".join(h2) + r"\\")
    # header row 3 (units)
    h3 = ["", "", "per edge"] + [r"($\%$) &(\$) & (s)"] * ncfg
    out.append("&".join(h3) + r"\\ \hline")

    for g in range(n // NB_SAMPLE):
        block = {c: rows[c][g * NB_SAMPLE:(g + 1) * NB_SAMPLE] for c in configs}
        ref = block[configs[0]]
        for i in range(NB_SAMPLE):
            idx = g * NB_SAMPLE + i + 1
            cells = [str(idx), str(ref[i]["nb_agent"]), str(ref[i]["nb_rq"])]
            for c in configs:
                b = block[c][i]
                cells += [cell_value(b["served"]), cell_value(b["pf"]), str(b["rt"])]
            out.append("&".join(cells) + r"\\")
        # AVG row
        avg = [r"AVG$\pm$STD", str(ref[0]["nb_agent"]), str(ref[0]["nb_rq"])]
        for c in configs:
            avg += [block_stats(block[c], "served"),
                    block_stats(block[c], "pf"),
                    rt_block_stats(block[c])]
        out.append("&".join(avg) + r"\\")

    out.append(r"\hline")
    out.append(r"\end{tabular}")
    out.append("}")
    out.append(r"\label{" + label + "}")
    out.append(r"\end{" + env + "}")
    return "\n".join(out)


def main():
    t1 = build_table(
        TABLE1,
        "Experiment results of the baseline and best-performing configurations: "
        "Greedy, O3, H2, and the hybrids H2O1, H2O2, H2O3:",
        "table: main experiment", r"\textheight", sideways=True)
    t2 = build_table(
        TABLE2,
        "Experiment results of the remaining configurations: "
        "optimizations O1 and O2, and heuristic H1:",
        "table: extension experiment", r"\textwidth")
    with open(os.path.join(RESULTS_DIR, "table1.tex"), "w") as f:
        f.write(t1 + "\n")
    with open(os.path.join(RESULTS_DIR, "table2.tex"), "w") as f:
        f.write(t2 + "\n")
    print(t1)
    print()
    print(t2)


if __name__ == "__main__":
    main()
