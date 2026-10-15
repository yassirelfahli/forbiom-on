"""Summary tables for the Activity 3 report (reads ./results, writes ./results/tables)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from abm import REGIONS, STRATEGIES, load_calibration

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
TAB = RES / "tables"

STRAT_ORDER = ["S0", "S1", "S2", "S3", "S4", "S5", "S6"]
STRAT_NAME = {k: v["name"] for k, v in STRATEGIES.items()} | {"S6": "Regionally differentiated portfolio"}
METRICS = ["util_late", "harvest_cum_Mm3", "mt_cum_k", "panel_cum_k", "panel_local_cum_k", "bioheat_cum_kodt",
           "pellet_cum_kodt", "rural_jobs_late", "ind_jobs_late", "ind_income_npv", "va_npv", "carbon_cum",
           "public_cost", "risk_unprofitable", "plants_built"]


def q05(x): return x.quantile(0.05)
def q95(x): return x.quantile(0.95)


def main() -> None:
    TAB.mkdir(parents=True, exist_ok=True)
    s = pd.read_csv(RES / "runs_summary.csv")
    base = s[s.scenario == "Base"]

    prov = base[base.region == "Ontario"].groupby("strategy")[METRICS].agg(["mean", q05, q95]).loc[STRAT_ORDER]
    prov.to_csv(TAB / "provincial_base.csv")

    reg = base[base.region.isin(REGIONS)].groupby(["strategy", "region"])[
        METRICS + ["util_2026", "harvest_SW_late", "harvest_PO_late", "harvest_HW_late", "n_mt_hub", "n_spoke",
                   "n_bioheat", "n_pellet", "ind_contractor_vol_late"]].mean()
    reg.to_csv(TAB / "regional_base.csv")

    cal = load_calibration()
    ts = pd.read_csv(RES / "timeseries_base_mean.csv")
    s0 = ts[(ts.strategy == "S0") & (ts.year == 2026)].set_index("region")
    calib = pd.DataFrame({
        "observed_harvest": cal.ACT_total, "simulated_2026": s0.loc[REGIONS, "harvest"],
        "LTMD": cal.LTMD_total, "observed_util": cal.utilization,
    })
    calib["sim_util"] = calib.simulated_2026 / calib.LTMD
    calib["error_pct"] = (calib.simulated_2026 / calib.observed_harvest - 1) * 100
    calib.to_csv(TAB / "calibration_check.csv")

    by_dem = s[s.region == "Ontario"].groupby(["scenario", "strategy"])[
        ["util_late", "va_npv", "rural_jobs_late", "ind_income_npv", "carbon_cum", "mt_cum_k"]].mean()
    by_dem.to_csv(TAB / "provincial_by_demand.csv")

    sens = pd.read_csv(RES / "sensitivity_summary.csv")
    sens_t = sens[sens.region == "Ontario"].groupby(["scenario", "strategy"])[
        ["util_late", "va_npv", "rural_jobs_late", "ind_income_npv", "carbon_cum", "risk_unprofitable"]].mean()
    sens_t.to_csv(TAB / "sensitivity_ontario.csv")

    pl = pd.read_csv(RES / "plants.csv")
    pl = pl[pl.scenario == "Base"]
    nseeds = base.seed.nunique()
    plant_t = pl.groupby(["strategy", "tech", "region"]).agg(
        built_per_run=("pid", "size"), share_unprofitable=("cum_profit", lambda x: (x < 0).mean()),
        mean_cum_profit_M=("cum_profit", lambda x: x.mean() / 1e6), share_active_2045=("active", "mean"))
    plant_t["built_per_run"] /= nseeds
    plant_t.to_csv(TAB / "plants_base.csv")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 60)
    print(calib.round(3).to_string())
    m = prov.xs("mean", axis=1, level=1)
    print(m.round(3).to_string())
    print(prov[[("util_late", "q05"), ("util_late", "q95"), ("ind_income_npv", "q05"), ("ind_income_npv", "q95"),
                ("va_npv", "q05"), ("va_npv", "q95")]].round(3).to_string())
    print(reg.loc[["S0", "S6"]].round(2).to_string())
    print(by_dem.round(3).to_string())
    print(sens_t.loc[(slice(None), ["S0", "S5", "S6"]), :].round(3).to_string())
    print(plant_t.loc["S6"].round(2).to_string())
    rs = pd.read_csv(RES / "regional_scores.csv")
    for w in ["Equal", "Economic priority", "Community priority", "Climate priority"]:
        best = rs.loc[rs[rs.strategy != "S6"].groupby("region")[f"score_{w}"].idxmax(), ["region", "strategy"]]
        print(w, dict(zip(best.region, best.strategy)))


if __name__ == "__main__":
    main()
