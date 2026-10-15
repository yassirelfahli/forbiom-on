"""Figures for the Activity 3 ABM report (reads ./results, writes ./figures)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from abm import REGIONS, load_calibration

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
FIG = HERE / "figures"
STRATS = ["S0", "S1", "S2", "S3", "S4", "S5", "S6"]
SHORT = {"S0": "S0 BAU", "S1": "S1 Urban MT", "S2": "S2 North hubs", "S3": "S3 Community",
         "S4": "S4 Hub-spoke", "S5": "S5 Hub-spoke+policy", "S6": "S6 Regional portfolio"}
COLORS = {"S0": "#7f7f7f", "S1": "#9467bd", "S2": "#1f77b4", "S3": "#2ca02c", "S4": "#ff7f0e", "S5": "#d62728", "S6": "#8c1d40"}
REG_LABEL = {"TroutLake": "Trout Lake", "Abitibi": "Abitibi River", "Algoma": "Algoma", "Kenora": "Kenora",
             "Nipissing": "Nipissing", "Algonquin": "Algonquin Park"}

plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150})


def save(fig, name: str) -> None:
    fig.savefig(FIG / f"{name}.png", bbox_inches="tight", dpi=200)
    plt.close(fig)


def fig_architecture() -> None:
    fig, ax = plt.subplots(figsize=(9, 5.4))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 62)
    ax.axis("off")

    def box(x, y, w, h, text, fc, fs=8, bold=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2", fc=fc, ec="#333", lw=0.8))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, weight="bold" if bold else "normal", wrap=True)

    def arrow(x1, y1, x2, y2, txt="", style="-|>", color="#333"):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=10, color=color, lw=0.9))
        if txt:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.8, txt, fontsize=6.5, ha="center", color="#333")

    box(1, 49, 22, 10, "Environment\nprice shocks (AR-1),\nfire/disturbance,\ndemand growth", "#fff3c4", fs=7.5)
    box(27, 49, 22, 10, "FMU managers (6)\nrelease LTMD volume,\nallocate fibre\n(priority rules)", "#d9ead3", fs=7.5)
    box(53, 49, 22, 10, "Harvest contractors\nIndigenous-owned & other;\nlogistic supply response", "#d9ead3", fs=7.5)
    box(79, 49, 20, 10, "Policy agent\ngrants, equity, procurement,\nallocation priority,\nclean-heat incentive", "#f4cccc", fs=7)

    box(4, 26, 40, 15, "Processors (incumbents + entrants)\nincumbent sawmills, OSB/pulp, hardwood mills;\nmass-timber hubs (log-to-CLT/glulam);\nurban CLT plants; community log-to-panel spokes;\nbioheat plants; pellet plants", "#cfe2f3", fs=7.5)
    box(58, 26, 28, 15, "Regional fibre markets\n(softwood, poplar, hardwood)\nendogenous log prices;\nresidue pools (mill & forest)", "#ead1dc", fs=7.5)

    box(1, 4, 23, 13, "Markets\nS. Ontario mass timber &\nprefab panels; northern\nhousing; community heat;\nexport pellets; commodities", "#fff3c4")
    box(29, 4, 30, 13, "Investment & exit decisions\nadaptive expectations, NPV,\nlogistic build probability,\nlearning-by-doing, 2-yr lag", "#cfe2f3")
    box(64, 4, 35, 13, "Outcome accounting (annual, by region)\nutilization, value added, jobs, Indigenous\njobs & income, public cost, carbon\nstorage/avoided/emitted, plant risk", "#d9d2e9")

    arrow(23, 54, 27, 54)
    arrow(49, 54, 53, 54)
    arrow(64, 49, 72, 41.5, "supply offers")
    arrow(40, 49, 62, 41.5, "available volume")
    arrow(44.5, 33.5, 57.5, 33.5, "", "<|-|>")
    ax.text(51, 35.2, "fibre demand /\nallocation", fontsize=6.5, ha="center")
    arrow(89, 49, 40, 41.5, "")
    arrow(12, 49, 20, 41.5, "")
    arrow(15, 26, 12, 17.5, "products")
    arrow(30, 26, 40, 17.5, "")
    arrow(59, 10, 64, 10)
    arrow(24, 10, 29, 10, "prices")
    arrow(47, 17.5, 38, 26, "new plants", color="#8c1d40")
    ax.text(50, 61.2, "FORBIOM-ABM: agent interactions in each annual time step (2026-2045)", ha="center", fontsize=9.5, weight="bold")
    save(fig, "fig01_architecture")


def fig_calibration() -> None:
    cal = pd.read_csv(RES / "tables" / "calibration_check.csv", index_col=0).loc[REGIONS]
    reg = load_calibration()
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    x = np.arange(len(REGIONS))
    ax = axes[0]
    ax.bar(x - 0.2, cal.observed_harvest / 1e3, 0.4, label="Observed 2019-24 avg (ARWoodS)", color="#999")
    ax.bar(x + 0.2, cal.simulated_2026 / 1e3, 0.4, label="Simulated 2026 (S0, mean of 50 runs)", color="#1f77b4")
    ax.set_xticks(x, [REG_LABEL[r] for r in REGIONS], rotation=25, ha="right")
    ax.set_ylabel("Harvest (1,000 m3/yr)")
    ax.set_title("(a) Calibration: harvest by FMU")
    ax.legend(frameon=False, fontsize=7)
    ax = axes[1]
    bottom = np.zeros(len(REGIONS))
    cols = {"SW": "#2b6e3f", "PO": "#c9a227", "HW": "#8c564b"}
    for f in ["SW", "PO", "HW"]:
        used = reg[f"ACT_{f}"].values / 1e3
        gap = (reg[f"LTMD_{f}"] - reg[f"ACT_{f}"]).clip(lower=0).values / 1e3
        ax.bar(x, used, 0.6, bottom=bottom, color=cols[f], label=f"{f} harvested")
        bottom += used
        ax.bar(x, gap, 0.6, bottom=bottom, color=cols[f], alpha=0.3, hatch="///", edgecolor="white", label=f"{f} unused LTMD")
        bottom += gap
    ax.set_xticks(x, [REG_LABEL[r] for r in REGIONS], rotation=25, ha="right")
    ax.set_ylabel("Volume (1,000 m3/yr)")
    ax.set_title("(b) Long-term managed volume vs harvest, 2019-24")
    ax.legend(frameon=False, fontsize=6.5, ncol=2)
    save(fig, "fig02_calibration")


def fig_util_paths() -> None:
    q = pd.read_csv(RES / "util_quantiles_base.csv")
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    for s in ["S0", "S1", "S2", "S3", "S4", "S6"]:
        d = q[q.strategy == s]
        ax.plot(d.year, d["0.5"] * 100, color=COLORS[s], label=SHORT[s], lw=1.6)
        ax.fill_between(d.year, d["0.05"] * 100, d["0.95"] * 100, color=COLORS[s], alpha=0.10)
    ax.set_ylabel("Harvest / LTMD (%)")
    ax.set_xticks(range(2026, 2046, 2))
    ax.set_title("Provincial fibre utilization, six FMUs (median and 5-95% Monte Carlo band, base demand)")
    ax.legend(frameon=False, ncol=3, fontsize=7.5, loc="upper left")
    ax.set_ylim(0, 100)
    save(fig, "fig03_utilization_paths")


def fig_regional_heatmap() -> None:
    reg = pd.read_csv(RES / "tables" / "regional_base.csv")
    piv = reg.pivot(index="strategy", columns="region", values="util_late").loc[STRATS, REGIONS] * 100
    base = reg[reg.strategy == "S0"].set_index("region").loc[REGIONS, "util_2026"] * 100
    data = pd.concat([pd.DataFrame([base.values], index=["Observed/2026"], columns=REGIONS), piv])
    fig, ax = plt.subplots(figsize=(7.5, 4))
    im = ax.imshow(data.values, cmap="YlGn", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(REGIONS)), [REG_LABEL[r] for r in REGIONS], rotation=20, ha="right")
    ax.set_yticks(range(len(data)), ["2026 (calibrated)"] + [SHORT[s] for s in STRATS])
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            v = data.values[i, j]
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8, color="white" if v > 60 else "black")
    ax.axhline(0.5, color="black", lw=1)
    fig.colorbar(im, ax=ax, label="Harvest / LTMD, 2041-45 (%)")
    ax.set_title("Regional fibre utilization by strategy (mean of 50 runs, base demand)")
    save(fig, "fig04_regional_utilization")


def fig_plants() -> None:
    reg = pd.read_csv(RES / "tables" / "regional_base.csv")
    d = reg[reg.strategy == "S6"].set_index("region").loc[REGIONS]
    techs = [("n_mt_hub", "Mass-timber hub", "#1f77b4"), ("n_spoke", "Community log-to-panel spoke", "#2ca02c"),
             ("n_bioheat", "Community bioheat", "#d62728"), ("n_pellet", "Pellet plant", "#c9a227")]
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    x = np.arange(len(REGIONS))
    bottom = np.zeros(len(REGIONS))
    for col, lab, c in techs:
        ax.bar(x, d[col], 0.6, bottom=bottom, label=lab, color=c)
        bottom += d[col].values
    ax.set_xticks(x, [REG_LABEL[r] for r in REGIONS])
    ax.set_ylabel("Plants operating in 2045 (mean per run)")
    ax.set_title("Emergent regional technology portfolio under S6 (base demand)")
    ax.legend(frameon=False, fontsize=7.5, ncol=2)
    save(fig, "fig05_plants_by_region")


def fig_indicators() -> None:
    prov = pd.read_csv(RES / "tables" / "provincial_base.csv", header=[0, 1], index_col=0)
    items = [("rural_jobs_late", "Rural/northern direct jobs\n(FTE, 2036-45 avg)", 1),
             ("ind_jobs_late", "Indigenous direct jobs\n(FTE, 2036-45 avg)", 1),
             ("ind_income_npv", "Indigenous community income\n(NPV 4%, $M)", 1),
             ("va_npv", "Value added\n(NPV 4%, $M)", 1),
             ("carbon_cum", "Net carbon benefit\n(MtCO2e, 2026-45)", 1),
             ("public_cost", "Public cost\n(grants & programs, $M)", 1)]
    fig, axes = plt.subplots(2, 3, figsize=(10, 5.6))
    for ax, (m, lab, _) in zip(axes.flat, items):
        mean = prov[(m, "mean")].loc[STRATS]
        lo = prov[(m, "q05")].loc[STRATS]
        hi = prov[(m, "q95")].loc[STRATS]
        ax.bar(range(len(STRATS)), mean, color=[COLORS[s] for s in STRATS],
               yerr=[(mean - lo).clip(lower=0), (hi - mean).clip(lower=0)], capsize=2, error_kw={"lw": 0.7})
        ax.set_xticks(range(len(STRATS)), STRATS)
        ax.set_title(lab, fontsize=8.5)
    fig.suptitle("Provincial outcomes by strategy (mean, 5-95% interval; 50 runs, base demand)", fontsize=10)
    fig.tight_layout()
    save(fig, "fig06_indicators")


def fig_mcda() -> None:
    from experiments import WEIGHTS
    base = pd.read_csv(RES / "provincial_scores_Base.csv", index_col=0).loc[STRATS]
    rob = pd.read_csv(RES / "rank_robustness.csv", index_col=0).loc[STRATS]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8), gridspec_kw={"width_ratios": [1, 2]})
    sc = base[[f"score_{w}" for w in WEIGHTS]].values
    ax = axes[0]
    im = ax.imshow(sc, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(WEIGHTS)), [w.replace(" priority", "") for w in WEIGHTS], rotation=25, ha="right")
    ax.set_yticks(range(len(STRATS)), [SHORT[s] for s in STRATS])
    for i in range(sc.shape[0]):
        for j in range(sc.shape[1]):
            ax.text(j, i, f"{sc[i, j]:.2f}", ha="center", va="center", fontsize=7.5)
    ax.set_title("(a) MCDA score by weighting")
    ax = axes[1]
    r = rob.values
    im2 = ax.imshow(r, cmap="RdYlGn_r", vmin=1, vmax=7, aspect="auto")
    ax.set_xticks(range(rob.shape[1]), rob.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(STRATS)), [SHORT[s] for s in STRATS])
    for i in range(r.shape[0]):
        for j in range(r.shape[1]):
            ax.text(j, i, f"{r[i, j]:.0f}", ha="center", va="center", fontsize=8)
    ax.set_title("(b) Rank (equal weights) across demand scenarios and sensitivities")
    fig.tight_layout()
    save(fig, "fig07_mcda")


def fig_fibre_groups() -> None:
    reg = pd.read_csv(RES / "tables" / "regional_base.csv")
    cal = load_calibration()
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.4), sharey=False)
    for ax, f, name in zip(axes, ["SW", "PO", "HW"], ["Softwood (SPF, pines, cedar, other conifer)", "Poplar/aspen", "Hardwood (birch, tolerant hardwoods)"]):
        x = np.arange(len(REGIONS))
        ltmd = cal[f"LTMD_{f}"].values / 1e3
        s0 = reg[reg.strategy == "S0"].set_index("region").loc[REGIONS, f"harvest_{f}_late"].values / 1e3
        s6 = reg[reg.strategy == "S6"].set_index("region").loc[REGIONS, f"harvest_{f}_late"].values / 1e3
        ax.bar(x, ltmd, 0.7, color="#ddd", label="LTMD")
        ax.bar(x - 0.15, s0, 0.3, color=COLORS["S0"], label="S0 harvest 2041-45")
        ax.bar(x + 0.15, s6, 0.3, color=COLORS["S6"], label="S6 harvest 2041-45")
        ax.set_xticks(x, [REG_LABEL[r] for r in REGIONS], rotation=35, ha="right", fontsize=7)
        ax.set_title(name, fontsize=8.5)
    axes[0].set_ylabel("1,000 m3/yr")
    axes[0].legend(frameon=False, fontsize=7)
    fig.suptitle("Fibre mobilized by species group: softwood gap closes, poplar and hardwood gaps persist", fontsize=10)
    fig.tight_layout()
    save(fig, "fig08_fibre_groups")


def fig_demand() -> None:
    d = pd.read_csv(RES / "tables" / "provincial_by_demand.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4))
    for ax, m, lab in [(axes[0], "util_late", "Fibre utilization 2041-45 (%)"), (axes[1], "ind_income_npv", "Indigenous community income (NPV, $M)")]:
        x = np.arange(len(STRATS))
        for k, (sc, c) in enumerate([("Low", "#9ecae1"), ("Base", "#3182bd"), ("High", "#08519c")]):
            v = d[d.scenario == sc].set_index("strategy").loc[STRATS, m] * (100 if m == "util_late" else 1)
            ax.bar(x + (k - 1) * 0.27, v, 0.27, color=c, label=f"{sc} demand growth")
        ax.set_xticks(x, STRATS)
        ax.set_title(lab, fontsize=9)
    axes[0].legend(frameon=False, fontsize=7)
    save(fig, "fig09_demand_scenarios")


def fig_indigenous_regional() -> None:
    reg = pd.read_csv(RES / "tables" / "regional_base.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    x = np.arange(len(REGIONS))
    for ax, m, lab in [(axes[0], "ind_jobs_late", "Indigenous direct jobs (FTE, 2036-45)"),
                       (axes[1], "ind_income_npv", "Indigenous community income (NPV, $M)")]:
        for k, s in enumerate(["S0", "S2", "S3", "S6"]):
            v = reg[reg.strategy == s].set_index("region").loc[REGIONS, m]
            ax.bar(x + (k - 1.5) * 0.2, v, 0.2, color=COLORS[s], label=SHORT[s])
        ax.set_xticks(x, [REG_LABEL[r] for r in REGIONS], rotation=20, ha="right")
        ax.set_title(lab, fontsize=9)
    axes[0].legend(frameon=False, fontsize=7)
    save(fig, "fig10_indigenous_regional")


def main() -> None:
    FIG.mkdir(exist_ok=True)
    fig_architecture()
    fig_calibration()
    fig_util_paths()
    fig_regional_heatmap()
    fig_plants()
    fig_indicators()
    fig_mcda()
    fig_fibre_groups()
    fig_demand()
    fig_indigenous_regional()
    print("figures written to", FIG)


if __name__ == "__main__":
    main()
