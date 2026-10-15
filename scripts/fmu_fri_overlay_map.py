"""
Official Ontario FMU boundaries (LIO FORMGMT) + stand-level FRI overlay for selected forests.

Reads FOREST_MANAGEMENT_UNIT from the FORMGMT zip, loads each FRI inventory from the
paths you provide, and draws one panel per forest: SPF biomass density (t/ha) with the
LIO FMU outline on top, plus active sawmills (LIO Forest_Processing_Facility) as green circles.

Requires: geopandas, matplotlib, pandas, pyogrio, shapely (same as process_fri_data).
"""
from __future__ import annotations

import argparse
import gc
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import process_fri_data as fri_proc
from matplotlib.colors import LinearSegmentedColormap
from spf_supply_chain_heatmap import TONNES_PER_M3, spf_fraction_from_spcomp

# Registry keys must match process_fri_data.FRI_REGISTRY; LIO names match FOREST_MANAGEMENT_UNIT.FMU_NAME
PANELS_DEFAULT: list[tuple[str, str, Path]] = [
    (
        "Kenora",
        "Kenora Forest",
        Path(r"c:\Users\dell\Downloads\pp_FRI_FIMv2_KenoraForest_(644)_2015_2D.zip"),
    ),
    (
        "Algoma",
        "Algoma Forest",
        Path(r"c:\Users\dell\Downloads\pp_FRI_FIMv2_AlgomaForest_2013_2D.zip"),
    ),
    (
        "Abitibi River",
        "Abitibi River Forest",
        Path(r"c:\Users\dell\Downloads\pp_FRI_FIMv2_AbitibiRiver_2011_2D.zip"),
    ),
    (
        "Algonquin Park",
        "Algonquin Park Forest",
        Path(r"c:\Users\dell\Downloads\pp_FRI_FIMv2_AlgonquinPark_2011_2D.zip"),
    ),
    (
        "Trout Lake",
        "Trout Lake Forest",
        Path(r"c:\Users\dell\Downloads\pp_FRI_FIMv2_TroutLakeForest(120)_2013_2D.zip"),
    ),
]

FORMGMT_ZIP_DEFAULT = Path(r"c:\Users\dell\Downloads\FORMGMT (1).zip")
# LIO Forest Processing Facility (same source as build_forbiom_map.py)
SAWMILL_SHP_DEFAULT = Path(
    r"c:\Users\dell\Downloads\Forest_Processing_Facility_extracted\Forest_Processing_Facility.shp"
)
FACILITY_TYPE_MAP = {
    "Sawmill - Large": "Sawmill",
    "Sawmill - Medium": "Sawmill",
    "Sawmill - Small": "Sawmill",
}
PLOT_CRS = fri_proc.TARGET_CRS  # EPSG:3347 — matches process_fri_data output


def load_sawmills(shp_path: Path) -> gpd.GeoDataFrame:
    """Active sawmill points from LIO Forest_Processing_Facility shapefile."""
    if not shp_path.is_file():
        raise FileNotFoundError(f"Sawmills / facilities shapefile not found: {shp_path}")
    gdf = gpd.read_file(shp_path)
    gdf["geometry"] = gdf.geometry.apply(
        lambda g: g.geoms[0] if g is not None and g.geom_type == "MultiPoint" else g
    )
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=gdf.crs)
    gdf = gdf.to_crs(PLOT_CRS)
    if "FACILITY_T" not in gdf.columns:
        raise ValueError("Facilities shapefile must include FACILITY_T (LIO schema).")
    gdf["fac_group"] = gdf["FACILITY_T"].map(FACILITY_TYPE_MAP).fillna("")
    saw = gdf[gdf["fac_group"] == "Sawmill"].copy()
    if "OPERATING_" in saw.columns:
        op = saw["OPERATING_"].astype(str).str.strip().str.lower()
        saw = saw[op == "active"].copy()
    return saw


def sawmills_in_fmu(sawmills: gpd.GeoDataFrame, fmu_poly: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Points strictly inside the LIO FMU polygon(s)."""
    if sawmills.empty or fmu_poly.empty:
        return gpd.GeoDataFrame(geometry=[], crs=PLOT_CRS)
    joined = gpd.sjoin(
        sawmills,
        fmu_poly[["geometry"]],
        predicate="intersects",
        how="inner",
    )
    return joined.drop(columns=["index_right"], errors="ignore")


def green_cmap() -> LinearSegmentedColormap:
    colors = ["#f7fcf5", "#ccebc5", "#7cbc5c", "#2b8c4b", "#00441b"]
    return LinearSegmentedColormap.from_list("fmu_fri", colors, N=256)


def load_fmu_from_formgmt_zip(zip_path: Path) -> gpd.GeoDataFrame:
    """Extract LIO FOREST_MANAGEMENT_UNIT.shp from FORMGMT archive and reproject."""
    if not zip_path.is_file():
        raise FileNotFoundError(f"FORMGMT zip not found: {zip_path}")
    tmp = Path(tempfile.mkdtemp(prefix="lio_fmu_"))
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp)
        shp = next(tmp.rglob("FOREST_MANAGEMENT_UNIT.shp"), None)
        if shp is None:
            raise FileNotFoundError("FOREST_MANAGEMENT_UNIT.shp not found inside zip.")
        gdf = gpd.read_file(shp)
        if "FMU_NAME" not in gdf.columns:
            raise ValueError("Shapefile missing FMU_NAME column.")
        return gdf.to_crs(PLOT_CRS)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def process_fri_zip(zip_path: Path, registry_key: str) -> gpd.GeoDataFrame:
    """Extract one FRI gdb zip and run the same pipeline as process_fri_data.process_region."""
    if not zip_path.is_file():
        raise FileNotFoundError(f"FRI zip not found: {zip_path}")
    meta = fri_proc.FRI_REGISTRY[registry_key]
    tmp = Path(tempfile.mkdtemp(prefix="fri_one_"))
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp)
        gdb = fri_proc.find_gdb(tmp)
        gdf = fri_proc.load_gdb_layer(gdb, meta["layer"], registry_key)
        if meta.get("is_3d") or fri_proc._has_z_series(gdf).any():
            gdf = fri_proc.geometry_to_2d(gdf)
        gdf = fri_proc.filter_forested(gdf)
        gdf = fri_proc.standardize_attributes(gdf)
        gdf = fri_proc.add_biomass_columns(gdf)
        gdf = gdf.dropna(subset=["geometry"])
        gdf = gdf[~gdf.geometry.is_empty]
        return gdf
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def add_spf_tpha(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    spcomp = gdf["SPCOMP"] if "SPCOMP" in gdf.columns else pd.Series("", index=gdf.index)
    leads = gdf["LEADSPC"] if "LEADSPC" in gdf.columns else pd.Series(np.nan, index=gdf.index)
    frac = pd.Series(
        [spf_fraction_from_spcomp(a, b) for a, b in zip(spcomp, leads)],
        index=gdf.index,
        dtype="float64",
    )
    vol = pd.to_numeric(gdf["Gross_Total_Volume"], errors="coerce").fillna(0.0)
    ha = pd.to_numeric(gdf["AREA_HA"], errors="coerce").replace(0, np.nan)
    gdf["SPF_FRAC"] = frac
    gdf["SPF_TONNES"] = vol * frac * TONNES_PER_M3
    gdf["SPF_TPHA"] = gdf["SPF_TONNES"] / ha
    return gdf


def plot_panel(
    ax,
    fri: gpd.GeoDataFrame,
    fmu_outline: gpd.GeoDataFrame,
    title: str,
    simplify_m: float,
    p_lo: float,
    p_hi: float,
    cmap,
    sawmills_here: gpd.GeoDataFrame | None = None,
    sawmill_ms: float = 38.0,
) -> None:
    plot_fri = fri
    if simplify_m and simplify_m > 0:
        plot_fri = fri.copy()
        plot_fri["geometry"] = plot_fri.geometry.simplify(simplify_m)

    vals = plot_fri["SPF_TPHA"].to_numpy(dtype=float)
    valid = np.isfinite(vals) & (vals >= 0)
    if valid.any():
        vmin, vmax = np.nanpercentile(vals[valid], [p_lo, p_hi])
        if vmin >= vmax:
            vmax = vmin + 1e-6
    else:
        vmin, vmax = 0.0, 1.0

    plot_fri.plot(
        ax=ax,
        column="SPF_TPHA",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        linewidth=0.05,
        edgecolor="#0d260d22",
        legend=False,
        zorder=1,
    )

    fmu_outline.plot(
        ax=ax,
        facecolor="none",
        edgecolor="#1a0f00",
        linewidth=1.8,
        zorder=3,
    )

    if sawmills_here is not None and not sawmills_here.empty:
        sawmills_here.plot(
            ax=ax,
            color="#14802d",
            edgecolor="#f5fff5",
            linewidth=0.85,
            markersize=sawmill_ms,
            marker="o",
            zorder=5,
            legend=False,
        )

    b_f = plot_fri.total_bounds
    b_m = fmu_outline.total_bounds
    minx = min(b_f[0], b_m[0])
    miny = min(b_f[1], b_m[1])
    maxx = max(b_f[2], b_m[2])
    maxy = max(b_f[3], b_m[3])
    pad_x = (maxx - minx) * 0.03 + 800
    pad_y = (maxy - miny) * 0.03 + 800
    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title(title, fontsize=11, fontweight="bold", color="#0d260d", pad=6)
    ax.text(
        0.02,
        0.98,
        f"LIO FMU boundary + FRI\n{p_lo:.0f}–{p_hi:.0f}% color scale:\n{vmin:.1f}–{vmax:.1f} t/ha",
        transform=ax.transAxes,
        va="top",
        fontsize=6.5,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#aaa", alpha=0.92),
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="LIO FMU boundaries + FRI overlay map.")
    ap.add_argument(
        "--formgmt-zip",
        type=Path,
        default=FORMGMT_ZIP_DEFAULT,
        help="FORMGMT zip containing LIO-.../FOREST_MANAGEMENT_UNIT.shp",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "fmu_fri_overlay_map.png",
    )
    ap.add_argument("--simplify-m", type=float, default=28.0)
    ap.add_argument("--percentile-lo", type=float, default=2.0)
    ap.add_argument("--percentile-hi", type=float, default=98.0)
    ap.add_argument("--dpi", type=int, default=175)
    ap.add_argument(
        "--sawmills-shp",
        type=Path,
        default=SAWMILL_SHP_DEFAULT,
        help="LIO Forest_Processing_Facility.shp",
    )
    ap.add_argument("--no-sawmills", action="store_true", help="Omit sawmill markers")
    ap.add_argument(
        "--sawmill-marker-size",
        type=float,
        default=38.0,
        help="Matplotlib markersize for sawmill circles",
    )
    args = ap.parse_args()

    print("Loading LIO FMU boundaries ...")
    fmu_all = load_fmu_from_formgmt_zip(args.formgmt_zip)
    print(f"  {len(fmu_all)} FMUs, CRS {fmu_all.crs}")

    sawmills_all = gpd.GeoDataFrame(geometry=[], crs=PLOT_CRS)
    if not args.no_sawmills:
        print("Loading sawmills ...")
        sawmills_all = load_sawmills(args.sawmills_shp)
        print(f"  {len(sawmills_all)} active sawmill points (CRS {PLOT_CRS})")

    ncols = 3
    nrows = (len(PANELS_DEFAULT) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(6.0 * ncols, 5.2 * nrows))
    axes_flat = np.atleast_1d(axes).ravel()
    cmap = green_cmap()

    for i, (reg_key, lio_name, fri_zip) in enumerate(PANELS_DEFAULT):
        if reg_key not in fri_proc.FRI_REGISTRY:
            sys.exit(f"Unknown registry key: {reg_key}")

        ax = axes_flat[i]
        fmu_one = fmu_all[fmu_all["FMU_NAME"] == lio_name].copy()
        if fmu_one.empty:
            print(f"  WARNING: no LIO polygon for '{lio_name}' - panel skipped outline.")
            fmu_one = gpd.GeoDataFrame(geometry=[], crs=fmu_all.crs)
        else:
            fmu_one = fmu_one.dissolve(by="FMU_NAME", as_index=False)

        print(f"FRI {reg_key} <- {fri_zip.name}")
        fri = process_fri_zip(fri_zip, reg_key)
        fri = add_spf_tpha(fri)
        print(f"  {len(fri):,} forested stands (median SPF t/ha {fri['SPF_TPHA'].median():.2f})")

        if fmu_one.empty:
            plot_fri = fri.copy()
            if args.simplify_m:
                plot_fri = plot_fri.copy()
                plot_fri["geometry"] = plot_fri.geometry.simplify(args.simplify_m)
            plot_fri.plot(ax=ax, column="SPF_TPHA", cmap=cmap, legend=False)
            ax.set_title(f"{lio_name}\n(no LIO match)", fontsize=10)
            ax.set_axis_off()
        else:
            mills = (
                sawmills_in_fmu(sawmills_all, fmu_one)
                if not args.no_sawmills
                else gpd.GeoDataFrame(geometry=[], crs=PLOT_CRS)
            )
            if not args.no_sawmills:
                print(f"  Sawmills in FMU: {len(mills)}")
            plot_panel(
                ax,
                fri,
                fmu_one,
                title=lio_name.replace(" Forest", "\nForest"),
                simplify_m=args.simplify_m,
                p_lo=args.percentile_lo,
                p_hi=args.percentile_hi,
                cmap=cmap,
                sawmills_here=mills if not mills.empty else None,
                sawmill_ms=args.sawmill_marker_size,
            )

        del fri
        gc.collect()

    for j in range(len(PANELS_DEFAULT), len(axes_flat)):
        axes_flat[j].set_visible(False)

    fig.patch.set_facecolor("#f2f6f2")
    fig.suptitle(
        "LIO FMU boundaries + FRI stands (SPF biomass density) + active sawmills (green)\n"
        f"Volume proxy × SPF share × {TONNES_PER_M3} t/m³  |  CRS {PLOT_CRS}",
        fontsize=11,
        fontweight="bold",
        color="#0d260d",
        y=0.995,
    )
    fig.subplots_adjust(left=0.04, right=0.98, top=0.91, bottom=0.04, wspace=0.06, hspace=0.14)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(args.out, dpi=args.dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
