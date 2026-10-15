"""
Batch-unzip Ontario FRI File Geodatabases, harmonize attributes, compute placeholder
biomass, aggregate by FMU, and export GeoPackage outputs.

Requires: geopandas, pandas, pyogrio, shapely
"""
from __future__ import annotations

import gc
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio

try:
    import shapely
    from shapely import force_2d as _force_2d_scalar
except ImportError:
    shapely = None  # type: ignore
    _force_2d_scalar = None  # type: ignore


def force_2d_geometries(geom_series: gpd.GeoSeries):
    """Strip Z; prefer vectorized shapely.force_2d (Shapely 2+) for large layers."""
    arr = geom_series.values
    n = len(arr)
    if shapely is not None and hasattr(shapely, "force_2d"):
        batch = 15_000
        if n <= batch:
            try:
                return shapely.force_2d(arr)
            except Exception:
                pass
        else:
            parts = []
            for i in range(0, n, batch):
                try:
                    parts.append(shapely.force_2d(arr[i : i + batch]))
                except Exception:
                    parts.append(
                        np.array(
                            [
                                _force_2d_scalar(g)
                                for g in arr[i : i + batch]
                            ],
                            dtype=object,
                        )
                    )
            return np.concatenate(parts)
    if _force_2d_scalar is not None:
        return np.array([_force_2d_scalar(g) for g in arr], dtype=object)
    from shapely.ops import transform

    def _drop_z(geom):
        return transform(lambda x, y, z=None: (x, y), geom)

    return np.array([_drop_z(g) for g in arr], dtype=object)

# ═════════════════════════════════════════════════════════════════════════════
#  PATHS & CONSTANTS
# ═════════════════════════════════════════════════════════════════════════════
FRI_DIR = Path(__file__).resolve().parent / "FRI data"
OUT_DIR = Path(__file__).resolve().parent
TARGET_CRS = "EPSG:3347"
BIOMASS_FACTOR = 0.5  # placeholder: Biomass_Tonnes = Gross_Total_Volume * BIOMASS_FACTOR
YIELD_PROXY_SCALE = 10.0  # placeholder scale in Gross_Total_Volume proxy (replace with yield tables)
# Large FMU inventories (e.g. Nipissing ~130k polys) need chunked reads to avoid OOM
GDB_READ_CHUNK_SIZE = 20_000
# to_crs() can allocate huge float arrays for dense vertices; process row slices
TO_CRS_CHUNK_ROWS = 4_000

FRI_REGISTRY: dict[str, dict[str, Any]] = {
    "Nipissing": {
        "zip": "7ef7f1e9-6db6-4f56-86d4-cd7f2cb9c82a-NiF.zip",
        "layer": "Nipissing_Forest_3D",
        "is_3d": True,
    },
    "Abitibi River": {
        "zip": "pp_FRI_FIMv2_AbitibiRiver_2011_2D.zip",
        "layer": "Polygon_Forest_Updated24072018",
    },
    "Algoma": {
        "zip": "pp_FRI_FIMv2_AlgomaForest_2013_2D.zip",
        "layer": "Algoma_Forest_2D",
    },
    "Algonquin Park": {
        "zip": "pp_FRI_FIMv2_AlgonquinPark_2011_2D.zip",
        "layer": "Polygon_Forest_2D",
    },
    "Kenora": {
        "zip": "pp_FRI_FIMv2_KenoraForest_(644)_2015_2D.zip",
        "layer": "Polygon_Forest_Kenora_2D",
    },
    "Trout Lake": {
        "zip": "pp_FRI_FIMv2_TroutLakeForest(120)_2013_2D.zip",
        "layer": "__all_polygon__",
    },
}


def find_gdb(root: Path) -> Path:
    """Return the first .gdb directory under root."""
    for p in root.rglob("*.gdb"):
        if p.is_dir():
            return p
    raise FileNotFoundError(f"No File Geodatabase (.gdb) found under {root}")


def read_gdb_layer_chunked(gdb_path: Path, layer: str) -> gpd.GeoDataFrame:
    """Read one vector layer, using row slices if the layer is very large."""
    info = pyogrio.read_info(gdb_path, layer=layer)
    n = info.get("features")
    if n == 0:
        return gpd.read_file(gdb_path, layer=layer)
    # Known modest size: one shot
    if isinstance(n, int) and n > 0 and n <= GDB_READ_CHUNK_SIZE:
        return gpd.read_file(gdb_path, layer=layer)
    if isinstance(n, int) and n > GDB_READ_CHUNK_SIZE:
        parts: list[gpd.GeoDataFrame] = []
        for start in range(0, n, GDB_READ_CHUNK_SIZE):
            end = min(start + GDB_READ_CHUNK_SIZE, n)
            chunk = gpd.read_file(gdb_path, layer=layer, rows=slice(start, end))
            parts.append(chunk)
        out = pd.concat(parts, ignore_index=True)
        return gpd.GeoDataFrame(out, geometry="geometry", crs=parts[0].crs)
    # Unknown or expensive count (None / -1): read in chunks until exhausted
    parts = []
    start = 0
    while True:
        chunk = gpd.read_file(
            gdb_path, layer=layer, rows=slice(start, start + GDB_READ_CHUNK_SIZE)
        )
        if chunk.empty:
            break
        parts.append(chunk)
        start += len(chunk)
        if len(chunk) < GDB_READ_CHUNK_SIZE:
            break
    if not parts:
        return gpd.GeoDataFrame()
    out = pd.concat(parts, ignore_index=True)
    return gpd.GeoDataFrame(out, geometry="geometry", crs=parts[0].crs)


def _polygon_geometry_types() -> set[str]:
    return {
        "Polygon",
        "MultiPolygon",
        "Polygon Z",
        "MultiPolygon Z",
        "Polygon M",
        "MultiPolygon M",
        "Polygon ZM",
        "MultiPolygon ZM",
    }


def load_gdb_layer(gdb_path: Path, layer: str, fmu_name: str) -> gpd.GeoDataFrame:
    """Read one layer from a GDB; optionally concat all polygon layers (Trout Lake)."""
    if layer == "__all_polygon__":
        parts = []
        poly_types = _polygon_geometry_types()
        for name, geom_type in pyogrio.list_layers(gdb_path):
            if geom_type is None or geom_type not in poly_types:
                continue
            # Skip topology QC / error layers
            if name.startswith("T_") or "Error" in name or "Dirty" in name:
                continue
            gdf = read_gdb_layer_chunked(gdb_path, name)
            if gdf.empty:
                continue
            gdf = gdf.assign(_source_layer=name)
            parts.append(gdf)
        if not parts:
            raise ValueError(f"No polygon layers read from {gdb_path}")
        out = pd.concat(parts, ignore_index=True)
        out = gpd.GeoDataFrame(out, geometry="geometry", crs=out.crs)
    else:
        out = read_gdb_layer_chunked(gdb_path, layer)
    out["FMU_NAME"] = fmu_name
    return out


def geometry_to_2d(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Strip Z/M coordinates so geometries merge cleanly."""
    gdf = gdf.copy()
    gdf["geometry"] = force_2d_geometries(gdf.geometry)
    return gdf


def _has_z_series(gdf: gpd.GeoDataFrame) -> pd.Series:
    def _hz(g):
        if g is None or g.is_empty:
            return False
        return bool(getattr(g, "has_z", False))

    return gdf.geometry.map(_hz)


def _is_memory_error(exc: BaseException) -> bool:
    t = type(exc).__name__
    if isinstance(exc, (MemoryError, OSError)):
        return True
    if "Memory" in t or "memory" in str(exc).lower() or "allocate" in str(exc).lower():
        return True
    return False


def _to_crs_with_simplify(gdf: gpd.GeoDataFrame, crs: str, tol: float) -> gpd.GeoDataFrame:
    g2 = gdf.copy()
    g2.geometry = g2.geometry.simplify(tol, preserve_topology=True)
    return g2.to_crs(crs)


def _to_crs_safe(gdf: gpd.GeoDataFrame, crs: str) -> gpd.GeoDataFrame:
    """Reproject; on memory errors bisect rows or simplify vertex-heavy geometries."""
    n = len(gdf)
    if n == 0:
        return gdf
    if n == 1:
        try:
            return gdf.to_crs(crs)
        except Exception as e:
            if not _is_memory_error(e):
                raise
            for tol in (2.0, 5.0, 10.0, 25.0, 50.0):
                try:
                    return _to_crs_with_simplify(gdf, crs, tol)
                except Exception as e2:
                    if not _is_memory_error(e2):
                        raise
            raise RuntimeError(
                "CRS transform OOM even after simplify; free RAM or process on a larger machine."
            ) from e
    try:
        return gdf.to_crs(crs)
    except Exception as e:
        if not _is_memory_error(e):
            raise
        mid = n // 2
        a = _to_crs_safe(gdf.iloc[:mid], crs)
        b = _to_crs_safe(gdf.iloc[mid:], crs)
        out = pd.concat([a, b], ignore_index=True)
        return gpd.GeoDataFrame(out, geometry="geometry", crs=crs)


def to_crs_chunked(gdf: gpd.GeoDataFrame, crs: str) -> gpd.GeoDataFrame:
    """Reproject in row slices; delegate to _to_crs_safe for each slice."""
    n = len(gdf)
    if n == 0:
        return gdf
    parts: list[gpd.GeoDataFrame] = []
    for start in range(0, n, TO_CRS_CHUNK_ROWS):
        chunk = gdf.iloc[start : start + TO_CRS_CHUNK_ROWS]
        parts.append(_to_crs_safe(chunk, crs))
    out = pd.concat(parts, ignore_index=True)
    return gpd.GeoDataFrame(out, geometry="geometry", crs=crs)


def standardize_attributes(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Rename core FRI fields to a consistent schema; reproject; area from geometry (m²)."""
    gdf = gdf.copy()
    rename_map = {
        "OSPCOMP": "SPCOMP",
        "OAGE": "AGE",
        "OHT": "HT",
        "OLEADSPC": "LEADSPC",
        "OCCLO": "CROWN_CLOSURE",
        "Shape_Area": "POLY_AREA_M2",
    }
    for old, new in rename_map.items():
        if old in gdf.columns:
            gdf = gdf.rename(columns={old: new})
    gdf = to_crs_chunked(gdf, TARGET_CRS)
    # Use planar area in target CRS (metres) for consistency across FMUs
    gdf["POLY_AREA_M2"] = gdf.geometry.area
    return gdf


def filter_forested(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Keep only forested polygons (POLYTYPE == FOR)."""
    if "POLYTYPE" not in gdf.columns:
        return gdf
    pt = gdf["POLYTYPE"].astype(str).str.strip().str.upper()
    return gdf.loc[pt == "FOR"].copy()


def add_biomass_columns(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Placeholder volume proxy (no Gross_Total_Volume in raw FRI):
    Gross_Total_Volume_m3 = STKG * HT * (CROWN_CLOSURE/100) * AREA_HA * YIELD_PROXY_SCALE
    Biomass_Tonnes = Gross_Total_Volume_m3 * BIOMASS_FACTOR
    """
    gdf = gdf.copy()
    stkg = pd.to_numeric(gdf.get("STKG"), errors="coerce").fillna(0.0)
    ht = pd.to_numeric(gdf.get("HT"), errors="coerce").fillna(0.0)
    clo = pd.to_numeric(gdf.get("CROWN_CLOSURE"), errors="coerce").fillna(0.0)
    area_m2 = pd.to_numeric(gdf.get("POLY_AREA_M2"), errors="coerce")
    area_m2 = area_m2.fillna(gdf.geometry.area)
    area_ha = area_m2 / 10000.0
    gdf["AREA_HA"] = area_ha
    closure_frac = (clo / 100.0).clip(lower=0.0, upper=1.0)
    gdf["Gross_Total_Volume"] = (
        stkg * ht * closure_frac * area_ha * YIELD_PROXY_SCALE
    )
    gdf["Biomass_Tonnes"] = gdf["Gross_Total_Volume"] * BIOMASS_FACTOR
    return gdf


def process_region(fmu_name: str, meta: dict[str, Any]) -> gpd.GeoDataFrame:
    zip_path = FRI_DIR / meta["zip"]
    if not zip_path.is_file():
        raise FileNotFoundError(f"Missing ZIP: {zip_path}")

    tmp = Path(tempfile.mkdtemp(prefix="fri_extract_"))
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp)
        gdb = find_gdb(tmp)
        gdf = load_gdb_layer(gdb, meta["layer"], fmu_name)

        if meta.get("is_3d") or _has_z_series(gdf).any():
            gdf = geometry_to_2d(gdf)

        # Attribute filter before reprojection — smaller peak memory for to_crs
        gdf = filter_forested(gdf)
        gdf = standardize_attributes(gdf)
        gdf = add_biomass_columns(gdf)

        gdf = gdf.dropna(subset=["geometry"])
        gdf = gdf[~gdf.geometry.is_empty]
        print(f"  {fmu_name}: {len(gdf)} forested polygons, crs={gdf.crs}")
        return gdf
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


UNION_CHUNK = 2_000  # hierarchical union limits peak memory on large FMUs


def _union_geometries(geom_series: gpd.GeoSeries):
    """Union all geometries; chunk large series to reduce peak memory."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    geoms = [g for g in geom_series.tolist() if g is not None and not g.is_empty]
    if not geoms:
        return Polygon()
    n = len(geoms)
    if n <= UNION_CHUNK:
        return unary_union(geoms)
    parts = []
    for i in range(0, n, UNION_CHUNK):
        parts.append(unary_union(geoms[i : i + UNION_CHUNK]))
    return unary_union(parts)


def aggregate_by_fmu(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """One row per FMU with dissolved geometry and total biomass / area."""
    totals = gdf.groupby("FMU_NAME", as_index=False).agg(
        Total_Biomass_Tonnes=("Biomass_Tonnes", "sum"),
        Total_Area_HA=("AREA_HA", "sum"),
    )
    totals["Biomass_Tonnes_Per_HA"] = (
        totals["Total_Biomass_Tonnes"] / totals["Total_Area_HA"].replace(0, float("nan"))
    )

    geom_union = []
    for name, grp in gdf.groupby("FMU_NAME"):
        geom_union.append({"FMU_NAME": name, "geometry": _union_geometries(grp.geometry)})

    geom_gdf = gpd.GeoDataFrame(geom_union, crs=gdf.crs)
    out = geom_gdf.merge(totals, on="FMU_NAME", how="left")
    return out


def main() -> None:
    if not FRI_DIR.is_dir():
        raise SystemExit(f"FRI data directory not found: {FRI_DIR}")

    print(f"FRI directory: {FRI_DIR}")
    print(f"Output directory: {OUT_DIR}\n")

    out_poly = OUT_DIR / "FRI_master_polygons.gpkg"
    out_sum = OUT_DIR / "FRI_summary_by_fmu.gpkg"
    for p in (out_poly, out_sum):
        if p.exists():
            p.unlink()

    summary_parts: list[gpd.GeoDataFrame] = []
    total_rows = 0
    for idx, (fmu_name, meta) in enumerate(FRI_REGISTRY.items()):
        print(f"Processing {fmu_name} …")
        gdf = process_region(fmu_name, meta)
        total_rows += len(gdf)
        mode = "w" if idx == 0 else "a"
        gdf.to_file(out_poly, driver="GPKG", layer="polygons", mode=mode)
        summary_parts.append(aggregate_by_fmu(gdf))
        del gdf
        gc.collect()

    summary = pd.concat(summary_parts, ignore_index=True)
    summary = gpd.GeoDataFrame(
        summary, geometry="geometry", crs=summary_parts[0].crs
    )
    summary.to_file(out_sum, driver="GPKG", layer="fmu_summary")

    print(f"\nWrote {out_poly}")
    print(f"Wrote {out_sum}")
    print(f"Master rows: {total_rows}, FMU summary rows: {len(summary)}")
    print("Done.")


if __name__ == "__main__":
    main()
