"""Generate the Table-I result plots (profit, run time, service rate) as SVGs,
matching the style of the original paper figures:

  * service_rate.svg : line plot, circle markers, "Service Rate (%)"
  * run_time.svg     : line plot, square markers, "Runtime (s)"
  * profit.svg       : grouped bar chart, "Profit ($)"
  * pareto.svg              : runtime-quality trade-off scatter at the largest
                              scale, with a zoom inset on the H2 / hybrid frontier
  * pareto_all_service.svg  : runtime vs service-rate trade-off, one panel per
                              instance scale (small multiples)
  * pareto_all_profit.svg   : runtime vs profit trade-off, one panel per scale

x-axis is categorical, one tick per problem size labelled ins(customers,aircraft).
Each point/bar is the mean over the 5 samples (no error bars, as in the original).
"""
import csv
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
NB_SAMPLE = 5

# Table-I configurations with their (plain-text) legend labels, in plot order.
CONFIGS = [
    ("Greedy", "Greedy"),
    ("O3",     "O3"),
    ("H2",     "H2"),
    ("O1H2",   "H2O1"),
    ("O2H2",   "H2O2"),
    ("O3H2",   "H2O3"),
]


def load(config):
    path = os.path.join(RESULTS_DIR, f"exp0_{config}.csv")
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append({
                "nb_agent": int(r["nb_agent"]),
                "nb_rq": int(r["nb_rq"]),
                "profit": r[f"profit_{config}"],
                "run_time": int(r[f"run_time_{config}"]),
                "served_customers": r[f"served_customers_{config}"],
            })
    return rows


def grouped_mean(rows, key):
    """Per problem-size mean of a metric (TO entries dropped); also return labels."""
    means, labels = [], []
    for g in range(len(rows) // NB_SAMPLE):
        block = rows[g * NB_SAMPLE:(g + 1) * NB_SAMPLE]
        vals = [float(b[key]) for b in block if b[key] != "TO"]
        means.append(np.mean(vals) if vals else np.nan)
        labels.append(f"ins({block[0]['nb_rq']},{block[0]['nb_agent']})")
    return np.array(means), labels


def line_plot(key, ylabel, fname, marker, legend_loc):
    data = {c: load(c) for c, _ in CONFIGS}
    fig, ax = plt.subplots(figsize=(9, 4.5))
    labels = None
    for cfg, leg in CONFIGS:
        mean, labels = grouped_mean(data[cfg], key)
        x = np.arange(len(mean))
        ax.plot(x, mean, marker=marker, markersize=8, linewidth=2, label=leg)
    ax.set_xticks(np.arange(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_xlabel("Instance")
    ax.set_ylabel(ylabel)
    ax.grid(True)
    ax.set_axisbelow(True)
    ax.legend(loc=legend_loc)
    fig.tight_layout()
    out = os.path.join(RESULTS_DIR, fname)
    fig.savefig(out, format="svg")
    plt.close(fig)
    print("wrote", out)


def bar_plot(key, ylabel, fname, legend_loc):
    data = {c: load(c) for c, _ in CONFIGS}
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ncfg = len(CONFIGS)
    width = 0.8 / ncfg
    labels = None
    for i, (cfg, leg) in enumerate(CONFIGS):
        mean, labels = grouped_mean(data[cfg], key)
        x = np.arange(len(mean))
        offset = (i - (ncfg - 1) / 2) * width
        ax.bar(x + offset, mean, width, label=leg)
    ax.set_xticks(np.arange(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_xlabel("Instance")
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y")
    ax.set_axisbelow(True)
    ax.legend(loc=legend_loc)
    fig.tight_layout()
    out = os.path.join(RESULTS_DIR, fname)
    fig.savefig(out, format="svg")
    plt.close(fig)
    print("wrote", out)


def pareto_plot(fname="pareto.svg", agent=211):
    """Runtime-quality trade-off scatter at the largest scale (agent aircraft):
    two panels (service rate / profit vs. runtime), one marker per configuration
    (faint per-sample points + bold mean), with a zoom inset on the H2/hybrid
    frontier where the dominated configs would otherwise compress the axis.
    """
    markers = {"Greedy": "o", "O3": "^", "H2": "D",
               "O1H2": "v", "O2H2": "P", "O3H2": "X"}
    data = {c: load(c) for c, _ in CONFIGS}
    cmap = plt.cm.tab10

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.4))
    axins1 = ax1.inset_axes([0.13, 0.34, 0.54, 0.44])
    axins2 = ax2.inset_axes([0.13, 0.34, 0.54, 0.44])
    for i, (key, lab) in enumerate(CONFIGS):
        rows = [r for r in data[key]
                if r["nb_agent"] == agent and r["served_customers"] != "TO"]
        rt = np.array([r["run_time"] for r in rows], float)
        sv = np.array([float(r["served_customers"]) for r in rows])
        pf = np.array([float(r["profit"]) for r in rows]) / 1000
        c, mk = cmap(i), markers[key]
        for ax, y in ((ax1, sv), (ax2, pf)):
            ax.scatter(rt, y, s=20, color=c, alpha=0.3, marker=mk)
            ax.scatter(rt.mean(), y.mean(), s=115, color=c, marker=mk,
                       edgecolor="k", zorder=5)
        for axins, y in ((axins1, sv), (axins2, pf)):
            axins.scatter(rt, y, s=16, color=c, alpha=0.35, marker=mk)
            axins.scatter(rt.mean(), y.mean(), s=95, color=c, marker=mk,
                          edgecolor="k", zorder=5)
        if key in ("Greedy", "O3"):  # dominated: label in the main view
            ax1.annotate(lab, (rt.mean(), sv.mean()), textcoords="offset points",
                         xytext=(6, -3), fontsize=8)
            ax2.annotate(lab, (rt.mean(), pf.mean()), textcoords="offset points",
                         xytext=(6, -3), fontsize=8)
        if key in ("H2", "O1H2", "O2H2", "O3H2"):  # frontier: label in the inset
            dy = {"H2": 5, "O1H2": -10, "O2H2": 6, "O3H2": -11}[key]
            axins1.annotate(lab, (rt.mean(), sv.mean()), textcoords="offset points",
                            xytext=(6, dy), fontsize=7)
            axins2.annotate(lab, (rt.mean(), pf.mean()), textcoords="offset points",
                            xytext=(6, dy), fontsize=7)
    axins1.set_xlim(25, 200); axins1.set_ylim(91, 100.5)
    axins2.set_xlim(25, 200); axins2.set_ylim(45.2, 46.1)
    for axins in (axins1, axins2):
        axins.grid(True, linestyle="--", alpha=0.3); axins.tick_params(labelsize=6)
    ax1.indicate_inset_zoom(axins1, edgecolor="gray")
    ax2.indicate_inset_zoom(axins2, edgecolor="gray")
    ax1.set_ylim(10, 103); ax2.set_ylim(8, 50)
    for ax, yl in ((ax1, "Service rate (%)"), (ax2, r"Profit (\$k)")):
        ax.set_xlabel("Runtime (s)"); ax.set_ylabel(yl); ax.set_xlim(0, 315)
        ax.grid(True, linestyle="--", alpha=0.4); ax.set_axisbelow(True)
    ax1.set_title("(a) Service rate vs. runtime")
    ax2.set_title("(b) Profit vs. runtime")
    fig.suptitle(f"Runtime--quality trade-off at {agent} aircraft")
    fig.tight_layout()
    out = os.path.join(RESULTS_DIR, fname)
    fig.savefig(out, format="svg", bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


PARETO_MARKERS = {"Greedy": "o", "O3": "^", "H2": "D",
                  "O1H2": "v", "O2H2": "P", "O3H2": "X"}
SCALES = [(13, 10), (22, 20), (55, 50), (106, 100), (160, 150), (211, 200)]


def pareto_small_multiples(metric, ylabel, fname, sharey, divide=1.0, ylim=None):
    """Runtime vs. `metric` trade-off, one panel per instance scale (2x3 grid),
    one marker per configuration (faint samples + bold mean). Service rate shares
    a 0-100 y-axis across panels; profit autoscales per panel (different magnitudes).
    """
    data = {c: load(c) for c, _ in CONFIGS}
    cmap = plt.cm.tab10
    fig, axes = plt.subplots(2, 3, figsize=(11, 6.4), sharex=True, sharey=sharey)
    axes = axes.ravel()
    for p, (ag, rq) in enumerate(SCALES):
        ax = axes[p]
        for i, (key, lab) in enumerate(CONFIGS):
            rows = [r for r in data[key]
                    if r["nb_agent"] == ag and r[metric] != "TO"]
            if not rows:
                continue
            rt = np.array([r["run_time"] for r in rows], float)
            yv = np.array([float(r[metric]) for r in rows]) / divide
            c, mk = cmap(i), PARETO_MARKERS[key]
            ax.scatter(rt, yv, s=14, color=c, alpha=0.30, marker=mk)
            ax.scatter(rt.mean(), yv.mean(), s=90, color=c, marker=mk,
                       edgecolor="k", zorder=5, label=lab if p == 0 else None)
        ax.set_title(f"{ag} aircraft ($p={rq}$)", fontsize=9)
        ax.grid(True, linestyle="--", alpha=0.4); ax.set_axisbelow(True)
        ax.set_xlim(0, 315)
        if ylim:
            ax.set_ylim(*ylim)
    for ax in axes[3:]:
        ax.set_xlabel("Runtime (s)")
    label_axes = (axes[0], axes[3]) if sharey else axes
    for ax in label_axes:
        ax.set_ylabel(ylabel)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=6, fontsize=9,
               bbox_to_anchor=(0.5, -0.02))
    fig.suptitle(f"Runtime--{ylabel.split(' (')[0].lower()} trade-off "
                 f"across instance scales", y=1.0)
    fig.tight_layout(rect=[0, 0.03, 1, 1])
    out = os.path.join(RESULTS_DIR, fname)
    fig.savefig(out, format="svg", bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def main():
    line_plot("served_customers", "Service Rate (%)", "service_rate.svg",
              marker="o", legend_loc="lower left")
    line_plot("run_time", "Runtime (s)", "run_time.svg",
              marker="s", legend_loc="upper left")
    bar_plot("profit", "Profit ($)", "profit.svg", legend_loc="upper left")
    pareto_plot("pareto.svg")
    pareto_small_multiples("served_customers", "Service rate (%)",
                           "pareto_all_service.svg", sharey=True, ylim=(0, 103))
    pareto_small_multiples("profit", "Profit (\\$k)",
                           "pareto_all_profit.svg", sharey=False, divide=1000.0)


if __name__ == "__main__":
    main()
