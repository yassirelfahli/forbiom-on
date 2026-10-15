"""Build ABM calibration tables from ARWoodS (harvest vs. LTMD) and eFAR (jobs, flows).

Outputs (in ./calibration):
  regions.csv          LTMD and actual harvest by FMU region and fibre class (m3/yr, 2019-2024 avg)
  efar_jobs.csv        direct facility jobs per 1,000 m3 roundwood consumed, by facility type
  efar_fmu_flows.csv   roundwood delivered from the six FMUs to facility types (m3, 2020-2022 avg)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "calibration"

ARWOODS = Path(r"C:\Users\dell\Downloads\arwoods_update_2025\EXTRACT_ARWoodS_2025_EN.csv")
EFAR = Path(r"C:\Users\dell\OneDrive\Bureau\Rasoul\Abdelhak\eFAR_Summary_Data_16Sept2024.xlsx")

FMU_TO_REGION = {
    "Trout Lake Forest": "TroutLake",
    "Abitibi River Forest": "Abitibi",
    "Algoma Forest": "Algoma",
    "Kenora Forest": "Kenora",
    "Nipissing Forest": "Nipissing",
    "Algonquin Park Forest": "Algonquin",
}
SPG_TO_FIBRE = {"SPF": "SW", "PWR": "SW", "OC": "SW", "CE": "SW", "PO": "PO", "BW": "HW", "TOL": "HW"}
CAL_YEARS = range(2019, 2025)


def arwoods_calibration() -> pd.DataFrame:
    df = pd.read_csv(ARWOODS, encoding="latin1")
    df = df[df.MuName.isin(FMU_TO_REGION) & (df.FT == "Merch") & df.FiscalYear.isin(CAL_YEARS)].copy()
    df["region"] = df.MuName.map(FMU_TO_REGION)
    df["fibre"] = df.SPG.map(SPG_TO_FIBRE)
    g = df.groupby(["region", "fibre"])[["ActHarv_Vol", "LTMD_Vol"]].sum() / len(CAL_YEARS)
    wide = g.unstack("fibre").fillna(0.0)
    wide.columns = [f"{'ACT' if a == 'ActHarv_Vol' else 'LTMD'}_{f}" for a, f in wide.columns]
    wide = wide.reindex(list(FMU_TO_REGION.values()))
    wide["ACT_total"] = wide.filter(like="ACT_").sum(axis=1)
    wide["LTMD_total"] = wide.filter(like="LTMD_").sum(axis=1)
    wide["utilization"] = wide.ACT_total / wide.LTMD_total
    return wide.reset_index().rename(columns={"index": "region"})


def efar_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    x = pd.ExcelFile(EFAR)
    fi = x.parse("Facility Info Section", header=1)
    c = x.parse("Section C", header=1)
    ab = x.parse("Section A & B", header=1).dropna(axis=1, how="all")
    years = [2020, 2021, 2022]

    emp = (
        fi[fi.YEAR.isin(years)]
        .groupby("FacilityTypeName")[["FacilityEmployees", "WoodlandsEmployees"]]
        .sum()
        / len(years)
    )
    cons = c[(c.Section == "C1") & c.Year.isin(years)].groupby("Facility Type").Volume.sum() / len(years)
    jobs = emp.join(cons.rename("roundwood_m3"), how="inner")
    jobs = jobs[jobs.roundwood_m3 > 0]
    jobs["facility_jobs_per_1000m3"] = jobs.FacilityEmployees / jobs.roundwood_m3 * 1000
    jobs["woodlands_jobs_per_1000m3"] = jobs.WoodlandsEmployees / jobs.roundwood_m3 * 1000

    key = {
        "Trout Lake": "TroutLake", "Abitibi River": "Abitibi", "Algoma Forest": "Algoma",
        "Kenora Forest": "Kenora", "Nipissing Forest": "Nipissing", "Algonquin Park": "Algonquin",
    }
    ab["region"] = None
    for k, v in key.items():
        ab.loc[ab.Source.astype(str).str.contains(k), "region"] = v
    flows = (
        ab[ab.region.notna() & ab.Year.isin(years)]
        .groupby(["region", "Facility Type"]).Volume.sum()
        .div(len(years)).unstack(fill_value=0.0)
    )
    return jobs.reset_index().rename(columns={"index": "facility_type"}), flows.reset_index()


def main() -> None:
    OUT.mkdir(exist_ok=True)
    reg = arwoods_calibration()
    reg.to_csv(OUT / "regions.csv", index=False)
    jobs, flows = efar_tables()
    jobs.to_csv(OUT / "efar_jobs.csv", index=False)
    flows.to_csv(OUT / "efar_fmu_flows.csv", index=False)
    pd.set_option("display.width", 200)
    print(reg.round(3).to_string(index=False))
    print(jobs.round(3).to_string(index=False))
    print(flows.round(0).to_string(index=False))


if __name__ == "__main__":
    main()
