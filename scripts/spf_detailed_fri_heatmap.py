"""
Stand-level SPF biomass density heat maps for selected FRI inventories only.

Reads the five ZIP geodatabases you specify (not the full Ontario FMU layer),
processes each like process_fri_data.py, then maps each forest in its own panel
with a green ramp (tonnes SPF biomass per hectare per polygon).

Requires: geopandas, matplotlib, pandas, pyogrio, shapely (same stack as process_fri_data).
"""
from __future__ import annotations

import argparse
import gc
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
# Reuse FRI pipeline + SPF parsing
import process_fri_data as fri_proc
from spf_supply_chain_heatmap import TONNES_PER_M3, spf_fraction_from_spcomp

# Five inventories (matches filenames under FRI data/)
DEFAULT_FMUS: tuple[str, ...] = (
    "Abitibi River",
    "Algoma",
    "Algonquin Park",
    "Kenora",
    "Trout Lake",
)


def green_cmap() -> LinearSegmentedColormap:
    colors = ["#f7fcf5", "#ccebc5", "#7cbc5c", "#2b8c4b", "#00441b"]
    return LinearSegmentedColormap.from_list("spf_detail", colors, N=256)


def add_spf_tpha(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """SPF-attributed tonnes and t/ha from Gross_Total_Volume × composition × 0.45 t/m³."""
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


def plot_one_forest(
    ax,
    gdf: gpd.GeoDataFrame,
    title: str,
    simplify_m: float,
    p_lo: float,
    p_hi: float,
    cmap,
) -> tuple[float, float]:
    """Plot stand polygons colored by SPF_TPHA; return vmin, vmax used."""
    plot_gdf = gdf
    if simplify_m and simplify_m > 0:
        plot_gdf = gdf.copy()
        plot_gdf["geometry"] = plot_gdf.geometry.simplify(simplify_m)

    vals = plot_gdf["SPF_TPHA"].to_numpy(dtype=float)
    valid = np.isfinite(vals) & (vals >= 0)
    if valid.any():
        vmin, vmax = np.nanpercentile(vals[valid], [p_lo, p_hi])
        if vmin >= vmax:
            vmax = vmin + 1e-6
    else:
        vmin, vmax = 0.0, 1.0

    plot_gdf.plot(
        ax=ax,
        column="SPF_TPHA",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        linewidth=0.08,
        edgecolor="#1a3d1a33",
        legend=False,
    )
    minx, miny, maxx, maxy = plot_gdf.total_bounds
    pad_x = (maxx - minx) * 0.02 + 500
    pad_y = (maxy - miny) * 0.02 + 500
    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title(title, fontsize=11, fontweight="bold", pad=6, color="#0d260d")
    return vmin, vmax


def main() -> None:
    p = argparse.ArgumentParser(description="Detailed SPF heat maps for selected FRI ZIPs.")
    p.add_argument(
        "--fmus",
        nargs="*",
        default=list(DEFAULT_FMUS),
        help="FMU keys from process_fri_data.FRI_REGISTRY (default: five non-Nipissing ZIPs).",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "spf_detailed_fri_heatmap.png",
    )
    p.add_argument(
        "--simplify-m",
        type=float,
        default=25.0,
        help="Simplify geometries for plotting only (metres, EPSG:3347). 0 = no simplify.",
    )
    p.add_argument(
        "--percentile-lo",
        type=float,
        default=2.0,
        help="Lower percentile for color scale within each panel (caps outliers).",
    )
    p.add_argument(
        "--percentile-hi",
        type=float,
        default=98.0,
        help="Upper percentile for color scale within each panel.",
    )
    p.add_argument("--dpi", type=int, default=200)
    args = p.parse_args()

    if not fri_proc.FRI_DIR.is_dir():
        sys.exit(f"Missing FRI data folder: {fri_proc.FRI_DIR}")

    names = args.fmus
    for n in names:
        if n not in fri_proc.FRI_REGISTRY:
            sys.exit(f"Unknown FMU '{n}'. Valid keys: {list(fri_proc.FRI_REGISTRY)}")

    n_panels = len(names)
    ncols = 3
    nrows = (n_panels + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(6.2 * ncols, 5.4 * nrows))
    axes_flat = np.atleast_1d(axes).ravel()
    cmap = green_cmap()

    for i, name in enumerate(names):
        ax = axes_flat[i]
        print(f"Loading & processing {name} …")
        meta = fri_proc.FRI_REGISTRY[name]
        gdf = fri_proc.process_region(name, meta)
        gdf = add_spf_tpha(gdf)
        print(f"  Plotting {len(gdf):,} stands (SPF t/ha median {gdf['SPF_TPHA'].median():.2f})")

        vmin, vmax = plot_one_forest(
            ax,
            gdf,
            title=name.replace(" ", "\n"),
            simplify_m=args.simplify_m,
            p_lo=args.percentile_lo,
            p_hi=args.percentile_hi,
            cmap=cmap,
        )
        ax.text(
            0.02,
            0.98,
            f"{args.percentile_lo:.0f}–{args.percentile_hi:.0f}% scale:\n{vmin:.1f}–{vmax:.1f} t/ha",
            transform=ax.transAxes,
            va="top",
            fontsize=7,
            color="#1a1a1a",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#b0c4a0", alpha=0.9),
        )

        del gdf
        gc.collect()

    for j in range(len(names), len(axes_flat)):
        axes_flat[j].set_visible(False)

    fig.subplots_adjust(left=0.04, right=0.98, top=0.90, bottom=0.05, wspace=0.06, hspace=0.16)

    fig.suptitle(
        "Stand-level SPF supply proxy — selected FRI inventories only\n"
        f"Merchantable volume × SPF composition × {TONNES_PER_M3} t/m³  |  CRS {fri_proc.TARGET_CRS}",
        fontsize=12,
        fontweight="bold",
        color="#0d260d",
        y=0.98,
    )
    fig.patch.set_facecolor("#f4f8f4")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(args.out, dpi=args.dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
