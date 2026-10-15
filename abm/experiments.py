"""Monte Carlo experiments, sensitivity analysis and multi-criteria strategy ranking for FORBIOM-ABM.

Usage:  py experiments.py [--seeds 50]
Writes CSV outputs to ./results.
"""
from __future__ import annotations

import argparse
import copy
import json
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from abm import REGIONS, STRATEGIES, YEARS, BiomassABM

HERE = Path(__file__).resolve().parent
RES = HERE / "results"

DEMAND = {"Low": 0.03, "Base": 0.08, "High": 0.15}
SENSITIVITY = {
    "MT price -20%": {"prices": {"mt": 880.0}},
    "MT price +20%": {"prices": {"mt": 1320.0}},
    "Lumber price -20%": {"prices": {"lumber": 240.0}},
    "Capex +30%": "capex+30",
    "Discount rate 10%": {"discount": 0.10},
    "Heat value -30%": "heat-30",
}
SOCIAL_DISCOUNT = 0.04
MIN_GAIN = 0.0  # weighted gain over full S5 (in units of the S0->S5 change) required to adopt a variant
SCALE_FLOOR = {"risk_unprofitable": 0.10}
LATE = range(2041, 2046)
MID_LATE = range(2036, 2046)

CRITERIA = {  # metric: direction
    "util_late": 1, "va_npv": 1, "rural_jobs_late": 1, "ind_income_npv": 1,
    "carbon_cum": 1, "public_cost": -1, "risk_unprofitable": -1,
}
CRIT_LABEL = {
    "util_late": "Fibre utilization 2041-45", "va_npv": "Value added (NPV)", "rural_jobs_late": "Rural/northern jobs",
    "ind_income_npv": "Indigenous community income (NPV)", "carbon_cum": "Net carbon benefit",
    "public_cost": "Public cost", "risk_unprofitable": "Share of new plants unprofitable",
}
WEIGHTS = {
    "Equal": dict.fromkeys(CRITERIA, 1 / 7),
    "Economic priority": {"util_late": .20, "va_npv": .35, "rural_jobs_late": .10, "ind_income_npv": .10,
                          "carbon_cum": .10, "public_cost": .10, "risk_unprofitable": .05},
    "Community priority": {"util_late": .10, "va_npv": .10, "rural_jobs_late": .25, "ind_income_npv": .35,
                           "carbon_cum": .10, "public_cost": .05, "risk_unprofitable": .05},
    "Climate priority": {"util_late": .20, "va_npv": .15, "rural_jobs_late": .10, "ind_income_npv": .10,
                         "carbon_cum": .35, "public_cost": .05, "risk_unprofitable": .05},
}


def build_overrides(demand: float, sens) -> dict:
    from abm import BASE_PARAMS
    ov: dict = {"demand_growth": demand}
    if sens is None:
        return ov
    if sens == "capex+30":
        tech = copy.deepcopy(BASE_PARAMS["tech"])
        for k in ("mt_hub", "mt_urban", "spoke", "bioheat", "pellet"):
            tech[k]["capex"] *= 1.3
        ov["tech"] = tech
    elif sens == "heat-30":
        ov["heat_value_odt"] = {r: v * 0.7 for r, v in BASE_PARAMS["heat_value_odt"].items()}
    else:
        ov.update(copy.deepcopy(sens))
    return ov


def summarize_run(df: pd.DataFrame, plants: pd.DataFrame) -> pd.DataFrame:
    disc = {y: (1 + SOCIAL_DISCOUNT) ** -(y - YEARS[0]) for y in YEARS}
    df = df.copy()
    df["disc"] = df.year.map(disc)
    rows = []
    groups = [(r, df[df.region == r], plants[plants.region == r]) for r in REGIONS + ["GTA"]]
    groups.append(("Ontario", df, plants))
    for name, d, pl in groups:
        late = d[d.year.isin(LATE)]
        ml = d[d.year.isin(MID_LATE)]
        last = d[d.year == YEARS[-1]]
        ltmd_late = late.ltmd.sum()
        rural = ml[ml.region != "GTA"]
        built = len(pl)
        rows.append({
            "region": name,
            "util_late": late.harvest.sum() / ltmd_late if ltmd_late > 0 else np.nan,
            "util_2026": d[d.year == YEARS[0]].harvest.sum() / max(1.0, d[d.year == YEARS[0]].ltmd.sum()),
            "harvest_cum_Mm3": d.harvest.sum() / 1e6,
            "harvest_SW_late": late.harvest_SW.sum() / len(LATE),
            "harvest_PO_late": late.harvest_PO.sum() / len(LATE),
            "harvest_HW_late": late.harvest_HW.sum() / len(LATE),
            "mt_cum_k": d.mt.sum() / 1e3,
            "panel_cum_k": d.panel.sum() / 1e3,
            "panel_local_cum_k": d.panel_local.sum() / 1e3,
            "bioheat_cum_kodt": d.bioheat_odt.sum() / 1e3,
            "pellet_cum_kodt": d.pellet_odt.sum() / 1e3,
            "forest_res_used_cum_kodt": d.get("forest_res_used", pd.Series(0)).fillna(0).sum() / 1e3,
            "mill_surplus_used_cum_kodt": d.get("mill_surplus_used", pd.Series(0)).fillna(0).sum() / 1e3,
            "jobs_late": ml.jobs.sum() / len(MID_LATE),
            "rural_jobs_late": rural.jobs.sum() / len(MID_LATE),
            "ind_jobs_late": ml.ind_jobs.sum() / len(MID_LATE),
            "ind_income_npv": (d.ind_income * d.disc).sum() / 1e6,
            "ind_equity_income_cum": d.ind_equity_income.sum() / 1e6,
            "ind_contractor_vol_late": late.ind_contractor_vol.sum() / len(LATE),
            "va_npv": (d.value_added * d.disc).sum() / 1e6,
            "carbon_cum": d.c_net_benefit.sum() / 1e6,
            "c_storage_cum": d.c_storage.sum() / 1e6,
            "c_avoided_cum": d.c_avoided.sum() / 1e6,
            "c_emissions_cum": d.c_emissions.sum() / 1e6,
            "public_cost": last.public_cost_cum.sum() / 1e6,
            "plants_built": built,
            "risk_unprofitable": (pl.cum_profit < 0).mean() if built else 0.0,
            "n_mt_hub": last.n_mt_hub.sum(), "n_mt_urban": last.n_mt_urban.sum(), "n_spoke": last.n_spoke.sum(),
            "n_bioheat": last.n_bioheat.sum(), "n_pellet": last.n_pellet.sum(),
        })
    return pd.DataFrame(rows)


def run_job(job: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    strat = job["strategy_def"]
    m = BiomassABM(strat, seed=job["seed"], overrides=build_overrides(job["demand"], job["sens"]))
    df = m.run()
    plants = m.plant_summary()
    summ = summarize_run(df, plants)
    for k in ("strategy", "scenario", "seed"):
        summ[k] = job[k]
        df[k] = job[k]
        plants[k] = job[k]
    keep_ts = job["scenario"] == "Base"
    return summ, (df if keep_ts else df.iloc[0:0]), plants


def run_batch(jobs: list[dict], procs: int = 6) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    with Pool(procs) as pool:
        out = pool.map(run_job, jobs, chunksize=4)
    return (pd.concat([o[0] for o in out], ignore_index=True),
            pd.concat([o[1] for o in out], ignore_index=True),
            pd.concat([o[2] for o in out], ignore_index=True))


def mcda(table: pd.DataFrame, weights: dict) -> pd.Series:
    score = pd.Series(0.0, index=table.index)
    for c, sign in CRITERIA.items():
        x = table[c].astype(float)
        rng = x.max() - x.min()
        norm = (x - x.min()) / rng if rng > 0 else pd.Series(0.5, index=x.index)
        if sign < 0:
            norm = 1 - norm
        score += weights[c] * norm
    return score


def strategy_jobs(keys_defs: dict, scenarios: dict, seeds: int, sens_name: str | None = None, sens=None) -> list[dict]:
    jobs = []
    for key, sdef in keys_defs.items():
        for sc, g in scenarios.items():
            for seed in range(seeds):
                jobs.append({"strategy": key, "strategy_def": sdef, "scenario": sens_name or sc,
                             "demand": g, "sens": sens, "seed": 1000 + seed})
    return jobs


REGIONAL_VARIANTS = {
    "full": None,
    "no mass-timber hub": ("drop", "mt_hub"),
    "no community spoke": ("drop", "spoke"),
    "no bioheat": ("drop", "bioheat"),
    "no pellet plant": ("drop", "pellet"),
    "max one spoke": ("cap", "spoke", 1),
}


def apply_variant(base: dict, region: str, variant) -> dict:
    s = copy.deepcopy(base)
    if variant is None:
        return s
    if variant[0] == "drop":
        s["techs"][variant[1]] = [r for r in s["techs"].get(variant[1], []) if r != region]
    else:
        s.setdefault("max_override", {}).setdefault(variant[1], {})[region] = variant[2]
    return s


def gain_vs_reference(t: pd.DataFrame, full: pd.Series, scale: pd.Series, weights: dict) -> pd.Series:
    """Weighted gain of each variant over the full package, each criterion scaled by the S0->S5 change."""
    g = pd.Series(0.0, index=t.index)
    for c, sign in CRITERIA.items():
        g += weights[c] * sign * (t[c] - full[c]) / scale[c]
    return g


def regional_optimization(base: dict, seeds: int, stage1: pd.DataFrame) -> tuple[dict, dict, pd.DataFrame]:
    """Per region, test S5 variants (drop one technology or cap spokes) and keep the best-scoring one."""
    jobs = []
    for r in REGIONS:
        for vname, v in REGIONAL_VARIANTS.items():
            if v is None and r != REGIONS[0]:
                continue
            key = "S5" if v is None else f"{r}|{vname}"
            jobs += strategy_jobs({key: apply_variant(base, r, v)}, {"Base": DEMAND["Base"]}, seeds)
    summ, _, _ = run_batch(jobs)
    ref = stage1[stage1.scenario == "Base"].groupby(["region", "strategy"])[list(CRITERIA)].mean()

    def scale_for(region: str) -> pd.Series:
        s = (ref.loc[(region, "S5")] - ref.loc[(region, "S0")]).abs()
        alt = ref.loc[(region, "S5")].abs()
        s = s.where(s > 1e-9, alt.where(alt > 1e-9, 1.0))
        for c, f in SCALE_FLOOR.items():
            s[c] = max(s[c], f)
        return s

    rows = []
    choice = {}
    for r in REGIONS:
        keys = ["S5"] + [f"{r}|{v}" for v in REGIONAL_VARIANTS if REGIONAL_VARIANTS[v] is not None]
        sub = summ[summ.strategy.isin(keys)]
        t = sub[sub.region == r].groupby("strategy")[list(CRITERIA)].mean()
        prov = sub[sub.region == "Ontario"].groupby("strategy")[list(CRITERIA)].mean()
        t["gain_regional"] = gain_vs_reference(t, t.loc["S5"], scale_for(r), WEIGHTS["Equal"])
        t["gain_provincial"] = gain_vs_reference(prov, prov.loc["S5"], scale_for("Ontario"), WEIGHTS["Equal"])
        t["score"] = 0.5 * t.gain_regional + 0.5 * t.gain_provincial
        t = t.rename(index=lambda k: "full" if k == "S5" else k.split("|")[1])
        t.insert(0, "region", r)
        rows.append(t.reset_index().rename(columns={"strategy": "variant"}))
        # parsimony: drop a technology in a region when doing so is no worse regionally or provincially
        ok = t[(t.score > MIN_GAIN) & (t.gain_provincial >= -0.005) & (t.public_cost < t.loc["full", "public_cost"])]
        choice[r] = ok.score.idxmax() if len(ok) else "full"
    s6 = copy.deepcopy(base)
    s6["name"] = "Regionally differentiated portfolio"
    for r, vname in choice.items():
        s6 = apply_variant(s6, r, REGIONAL_VARIANTS[vname])
    return s6, choice, pd.concat(rows, ignore_index=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=50)
    ap.add_argument("--sens-seeds", type=int, default=30)
    args = ap.parse_args()
    RES.mkdir(exist_ok=True)
    base_keys = {k: STRATEGIES[k] for k in STRATEGIES}

    # Stage 1: uniform strategies under three demand scenarios
    summ, ts, plants = run_batch(strategy_jobs(base_keys, DEMAND, args.seeds))

    # Stage 2: regional scoring of uniform strategies, then region-by-region tuning of S5 (-> S6)
    reg = summ[(summ.scenario == "Base") & summ.region.isin(REGIONS)]
    reg_mean = reg.groupby(["region", "strategy"])[list(CRITERIA)].mean().reset_index()
    parts = []
    for r in REGIONS:
        sub = reg_mean[reg_mean.region == r].set_index("strategy")
        for wname, w in WEIGHTS.items():
            sub[f"score_{wname}"] = mcda(sub, w)
        parts.append(sub.reset_index())
    reg_scores = pd.concat(parts, ignore_index=True)
    s6, choice, variants = regional_optimization(STRATEGIES["S5"], args.sens_seeds, summ)
    variants.to_csv(RES / "regional_variants.csv", index=False)
    (RES / "s6_definition.json").write_text(json.dumps({"strategy": s6, "regional_choice": choice}, indent=2))

    summ6, ts6, plants6 = run_batch(strategy_jobs({"S6": s6}, DEMAND, args.seeds))
    summ = pd.concat([summ, summ6], ignore_index=True)
    ts = pd.concat([ts, ts6], ignore_index=True)
    plants = pd.concat([plants, plants6], ignore_index=True)

    # Stage 3: sensitivity analysis (base demand)
    all_keys = {**base_keys, "S6": s6}
    sens_out = []
    for name, sens in SENSITIVITY.items():
        s_summ, _, _ = run_batch(strategy_jobs(all_keys, {"Base": DEMAND["Base"]}, args.sens_seeds, name, sens))
        sens_out.append(s_summ)
    sens_df = pd.concat(sens_out, ignore_index=True)

    # Provincial MCDA (base demand, all strategies incl. S6) + robustness across demand and sensitivities
    def prov_scores(frame: pd.DataFrame) -> pd.DataFrame:
        t = frame[frame.region == "Ontario"].groupby("strategy")[list(CRITERIA)].mean()
        for wname, w in WEIGHTS.items():
            t[f"score_{wname}"] = mcda(t, w)
        return t

    prov = {sc: prov_scores(summ[summ.scenario == sc]) for sc in DEMAND}
    for sname in SENSITIVITY:
        prov[sname] = prov_scores(sens_df[sens_df.scenario == sname])
    robust = pd.DataFrame({sc: t["score_Equal"].rank(ascending=False) for sc, t in prov.items()})

    # regional scores including S6
    reg = summ[(summ.scenario == "Base") & summ.region.isin(REGIONS)]
    reg_mean = reg.groupby(["region", "strategy"])[list(CRITERIA)].mean().reset_index()
    parts = []
    for r in REGIONS:
        sub = reg_mean[reg_mean.region == r].set_index("strategy")
        for wname, w in WEIGHTS.items():
            sub[f"score_{wname}"] = mcda(sub, w)
        parts.append(sub.reset_index())
    reg_scores_all = pd.concat(parts, ignore_index=True)

    summ.to_csv(RES / "runs_summary.csv", index=False)
    sens_df.to_csv(RES / "sensitivity_summary.csv", index=False)
    plants.to_csv(RES / "plants.csv", index=False)
    ts_mean = ts.drop(columns=["seed", "scenario"]).groupby(["strategy", "region", "year"]).mean().reset_index()
    ts_q = (ts.groupby(["strategy", "year", "seed"])[["harvest", "ltmd"]].sum().reset_index()
            .assign(util=lambda d: d.harvest / d.ltmd)
            .groupby(["strategy", "year"]).util.quantile([0.05, 0.5, 0.95]).unstack().reset_index())
    ts_mean.to_csv(RES / "timeseries_base_mean.csv", index=False)
    ts_q.to_csv(RES / "util_quantiles_base.csv", index=False)
    reg_scores.to_csv(RES / "regional_scores_stage1.csv", index=False)
    reg_scores_all.to_csv(RES / "regional_scores.csv", index=False)
    for sc, t in prov.items():
        t.to_csv(RES / f"provincial_scores_{sc.replace(' ', '_').replace('%', 'pct').replace('+', 'plus').replace('-', 'minus')}.csv")
    robust.to_csv(RES / "rank_robustness.csv")
    print("Regional choice for S6:", choice)
    print(prov["Base"].round(3).to_string())
    print(robust.to_string())


if __name__ == "__main__":
    main()
