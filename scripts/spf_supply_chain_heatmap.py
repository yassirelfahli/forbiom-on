"""
Spatial supply-chain style heat map: SPF (spruce–pine–fir) engineered-wood biomass
density by Ontario FMU, from processed FRI polygons joined to official FMU boundaries.

Requires: geopandas, matplotlib, pandas, shapely
"""
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import pyogrio
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

# ── CRS (Ontario MNR Lambert, NAD83) ──────────────────────────────────────────
TARGET_CRS = "EPSG:3161"

# Merchantable volume proxy from FRI processing (m³ stand total)
VOL_COL = "Gross_Total_Volume"

# Density for softwood → tonnes (engineered wood proxy)
TONNES_PER_M3 = 0.45

# Row slices when reading large FRI GeoPackages (memory-safe)
DEFAULT_FRI_CHUNK = 15_000

# Ontario FRI two-letter species codes commonly treated as SPF (spruce, pine, true firs)
# Sources: FRI / OGFRI species lists — excludes hardwoods (e.g. Pt, Bw, Mh).
SPF_CODES = {
    # Spruce
    "Sb",
    "Sw",
    "Sr",
    "Se",
    "Sn",
    "Sx",
    # Pine
    "Pj",
    "Pr",
    "Pw",
    "Pc",
    "Pm",
    "Pn",
    "Pg",
    "Pp",
    "Ps",
    "Px",
    # Balsam fir
    "Bf",
}

# "Species  pct  Species pct ..." (e.g. "Sb 70 Pt 30")
COMP_PAIR_RE = re.compile(
    r"\b([A-Za-z]{1,3})\s+(\d+(?:\.\d+)?)\b",
    flags=re.UNICODE,
)


def normalize_code(token: str) -> str:
    t = token.strip()
    if len(t) < 2:
        return ""
    # Keep leading two letters as FRI code (Sb, Pj, …)
    return t[0].upper() + t[1].lower()


def spf_fraction_from_spcomp(spcomp: object, leadspc: object) -> float:
    """
    Return fraction [0, 1] of stand composition attributed to SPF species,
    from OSPCOMP/SPCOMP volume (or stem) percent pairs.
    If composition is missing, use LEADSPC: 1.0 if SPF else 0.0.
    """
    text = spcomp if pd.notna(spcomp) else ""
    total = 0.0
    spf_sum = 0.0
    for m in COMP_PAIR_RE.finditer(str(text)):
        code = normalize_code(m.group(1))
        try:
            pct = float(m.group(2))
        except ValueError:
            continue
        total += pct
        if code in SPF_CODES:
            spf_sum += pct

    if total > 0:
        return float(min(1.0, max(0.0, spf_sum / total)))

    # Fallback: leading species only
    if pd.notna(leadspc):
        c = normalize_code(str(leadspc).strip())
        if c in SPF_CODES:
            return 1.0
    return 0.0


def default_fmu_shapefile() -> Path | None:
    p = Path(__file__).resolve().parent
    candidates = [
        Path(r"C:\Users\dell\Downloads\FORMGMT_extracted\LIO-2025-12-11\FOREST_MANAGEMENT_UNIT.shp"),
        p / "FOREST_MANAGEMENT_UNIT.shp",
        p / "data" / "FOREST_MANAGEMENT_UNIT.shp",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def iter_fri_chunks(path: Path, layer: str, chunk_size: int):
    """Yield GeoDataFrame chunks from a FRI GeoPackage."""
    info = pyogrio.read_info(path, layer=layer)
    nfeat = info.get("features")
    if isinstance(nfeat, int) and nfeat > 0:
        for start in range(0, nfeat, chunk_size):
            chunk = gpd.read_file(path, layer=layer, rows=slice(start, start + chunk_size))
            yield chunk
        return
    start = 0
    while True:
        chunk = gpd.read_file(path, layer=layer, rows=slice(start, start + chunk_size))
        if chunk.empty:
            break
        yield chunk
        start += len(chunk)
        if len(chunk) < chunk_size:
            break


def aggregate_fri_to_fmu_chunked(
    fri_path: Path,
    layer: str,
    fmu: gpd.GeoDataFrame,
    chunk_size: int,
) -> pd.DataFrame:
    """
    Scan FRI in chunks; reproject to EPSG:3161; forested-only; SPF tonnes; spatial join to FMUs.
    Returns one row per FMU with total SPF biomass, forest ha, and tonnes/ha.
    """
    fmu_min = fmu[["FMU_NAME", "geometry"]].copy()
    tot_tonnes = defaultdict(float)
    tot_ha = defaultdict(float)
    n_polys = 0

    for raw in iter_fri_chunks(fri_path, layer, chunk_size):
        if raw.crs is None:
            raise ValueError(f"FRI layer has no CRS: {fri_path}")
        chunk = raw.to_crs(TARGET_CRS)
        chunk = forested_only(chunk)
        if chunk.empty:
            continue
        n_polys += len(chunk)
        chunk = add_spf_biomass(chunk)
        ha_col = "AREA_HA" if "AREA_HA" in chunk.columns else None
        if ha_col is None:
            chunk = chunk.copy()
            chunk["AREA_HA"] = chunk.geometry.area / 10000.0
            ha_col = "AREA_HA"

        pts = chunk.copy()
        pts["geometry"] = pts.geometry.representative_point()
        # Avoid FMU_NAME clash with inventory tags (sjoin would suffix _left/_right)
        if "FMU_NAME" in pts.columns:
            pts = pts.drop(columns=["FMU_NAME"])
        joined = gpd.sjoin(pts, fmu_min, predicate="within", how="inner")
        if joined.empty:
            continue
        joined = joined.drop(columns=["index_right"], errors="ignore")
        for name, grp in joined.groupby("FMU_NAME"):
            tot_tonnes[name] += float(grp["SPF_BIOMASS_TONNES"].sum())
            tot_ha[name] += float(grp[ha_col].sum())

    if not tot_tonnes:
        raise RuntimeError(
            "No forested FRI polygons joined to an FMU (check CRS, boundaries, and POLYTYPE)."
        )

    rows = []
    for name in sorted(tot_tonnes.keys()):
        t = tot_tonnes[name]
        h = tot_ha[name]
        tph = t / h if h > 0 else np.nan
        rows.append(
            {
                "FMU_NAME": name,
                "Total_SPF_Biomass_Tonnes": t,
                "Total_Forest_HA": h,
                "Tonnes_per_HA": tph,
            }
        )
    agg = pd.DataFrame(rows)
    print(f"  Processed {n_polys:,} forested polygons (chunk size {chunk_size:,}).")
    return agg


def load_fmu(path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        raise ValueError(f"FMU layer has no CRS: {path}")
    gdf = gdf.to_crs(TARGET_CRS)
    if "FMU_NAME" not in gdf.columns:
        raise ValueError(
            "FMU shapefile must include an 'FMU_NAME' column (LIO FOREST_MANAGEMENT_UNIT)."
        )
    return gdf


def forested_only(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if "POLYTYPE" not in gdf.columns:
        return gdf
    pt = gdf["POLYTYPE"].astype(str).str.strip().str.upper()
    return gdf.loc[pt == "FOR"].copy()


def add_spf_biomass(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Per-polygon SPF tonnes from merchantable volume × SPF share × t/m³."""
    if VOL_COL not in gdf.columns:
        raise ValueError(f"FRI data must include '{VOL_COL}' (run process_fri_data.py).")

    spcomp = gdf["SPCOMP"] if "SPCOMP" in gdf.columns else pd.Series("", index=gdf.index)
    leads = gdf["LEADSPC"] if "LEADSPC" in gdf.columns else pd.Series(np.nan, index=gdf.index)

    frac = pd.Series(
        [spf_fraction_from_spcomp(a, b) for a, b in zip(spcomp, leads)],
        index=gdf.index,
        dtype="float64",
    )
    gdf = gdf.copy()
    gdf["SPF_COMP_FRAC"] = frac
    vol = pd.to_numeric(gdf[VOL_COL], errors="coerce").fillna(0.0)
    gdf["SPF_MERCH_VOL_M3"] = vol * gdf["SPF_COMP_FRAC"]
    gdf["SPF_BIOMASS_TONNES"] = gdf["SPF_MERCH_VOL_M3"] * TONNES_PER_M3
    return gdf


def green_cmap() -> LinearSegmentedColormap:
    colors = ["#f7fcf5", "#e5f5e0", "#a1d99b", "#41ab5d", "#238b45", "#00441b"]
    return LinearSegmentedColormap.from_list("spf_green", colors, N=256)


def plot_heatmap(
    fmu_plot: gpd.GeoDataFrame,
    column: str,
    out_png: Path,
    title: str,
) -> None:
    has_data = fmu_plot[column].notna() & (fmu_plot[column] > 0)
    if not has_data.any():
        print("Warning: no positive values to plot; writing empty-map figure.")
        vmin, vmax = 0.0, 1.0
    else:
        vmin = float(fmu_plot.loc[has_data, column].min())
        vmax = float(fmu_plot.loc[has_data, column].max())
        if vmin == vmax:
            vmax = vmin + 1e-6

    fig, ax = plt.subplots(1, 1, figsize=(14, 12))
    fig.patch.set_facecolor("#f8faf8")
    ax.set_facecolor("#eef4ee")

    cmap = green_cmap()
    nodata = fmu_plot[~has_data]
    if not nodata.empty:
        nodata.plot(ax=ax, color="#e8e8e8", edgecolor="#ffffff", linewidth=0.4)
    fmu_plot[has_data].plot(
        ax=ax,
        column=column,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        edgecolor="#ffffff",
        linewidth=0.35,
        legend=False,
    )

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.035, pad=0.02, shrink=0.75)
    cbar.set_label("SPF biomass density (tonnes / ha)", fontsize=11)

    ax.set_title(title, fontsize=15, fontweight="bold", pad=12)
    ax.set_axis_off()
    plt.tight_layout()
    plt.savefig(out_png, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SPF biomass FMU heat map from FRI + LIO FMU boundaries.")
    p.add_argument(
        "--fri",
        type=Path,
        default=Path(__file__).resolve().parent / "FRI_master_polygons.gpkg",
        help="Processed FRI GeoPackage (default: ./FRI_master_polygons.gpkg)",
    )
    p.add_argument("--fri-layer", default="polygons", help="Layer name in FRI GPKG")
    p.add_argument(
        "--fmu-shp",
        type=Path,
        default=None,
        help="LIO FOREST_MANAGEMENT_UNIT.shp (default: auto-detect common paths)",
    )
    p.add_argument(
        "--regions",
        nargs="*",
        default=None,
        help="Optional FMU_NAME values to include in the map (e.g. seven study regions). "
        "Default: all FMUs that received a stand join.",
    )
    p.add_argument(
        "--out-png",
        type=Path,
        default=Path(__file__).resolve().parent / "spf_fmu_biomass_heatmap.png",
    )
    p.add_argument(
        "--out-csv",
        type=Path,
        default=Path(__file__).resolve().parent / "spf_fmu_biomass_summary.csv",
    )
    p.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_FRI_CHUNK,
        help="Rows per read when scanning FRI GeoPackage (lower uses less RAM).",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    fri_path = args.fri
    if not fri_path.is_file():
        raise SystemExit(f"FRI file not found: {fri_path}")

    fmu_path = args.fmu_shp or default_fmu_shapefile()
    if fmu_path is None or not Path(fmu_path).is_file():
        raise SystemExit(
            "FMU shapefile not found. Place FOREST_MANAGEMENT_UNIT.shp next to this script "
            "or pass --fmu-shp (LIO FORMGMT download)."
        )
    fmu_path = Path(fmu_path)

    print(f"Loading FMU boundaries: {fmu_path}")
    fmu = load_fmu(fmu_path)

    layer = args.fri_layer or "polygons"
    print(f"Scanning FRI (chunked): {fri_path} layer={layer}")
    agg = aggregate_fri_to_fmu_chunked(fri_path, layer, fmu, args.chunk_size)
    print(
        f"  Total SPF biomass (all joined FMUs): {agg['Total_SPF_Biomass_Tonnes'].sum():,.0f} t"
    )
    print(f"  FMUs with inventory (interior-point join): {len(agg)}")

    fmu_merged = fmu.merge(agg, on="FMU_NAME", how="left")

    if args.regions:
        names = set(args.regions)
        fmu_plot = fmu_merged[fmu_merged["FMU_NAME"].isin(names)].copy()
        missing = names - set(fmu_merged["FMU_NAME"])
        if missing:
            print(f"  Note: unknown FMU_NAME in --regions (skipped): {sorted(missing)}")
    else:
        fmu_plot = fmu_merged[fmu_merged["Total_Forest_HA"].notna()].copy()

    if fmu_plot.empty:
        raise SystemExit("No FMU polygons to plot (check --regions or join results).")

    agg.to_csv(args.out_csv, index=False)
    print(f"Wrote summary table: {args.out_csv}")

    plot_heatmap(
        fmu_plot,
        "Tonnes_per_HA",
        args.out_png,
        title="Ontario FMU — SPF biomass density (engineered wood proxy)\n"
        f"Merchantable volume × SPF share × {TONNES_PER_M3} t/m³",
    )
    print(f"Wrote map: {args.out_png}")
    print("Done.")


if __name__ == "__main__":
    main()
