import geopandas as gpd
import folium
from folium import plugins
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import numpy as np
import os
import math

# ═════════════════════════════════════════════════════════════════════════════
#  PATHS
# ═════════════════════════════════════════════════════════════════════════════
SHP_FMU = r"C:\Users\dell\Downloads\FORMGMT_extracted\LIO-2025-12-11\FOREST_MANAGEMENT_UNIT.shp"
SHP_FAC = r"C:\Users\dell\Downloads\Forest_Processing_Facility_extracted\Forest_Processing_Facility.shp"
OUT_DIR = r"C:\Users\dell\OneDrive\Bureau\Rasoul"

# ═════════════════════════════════════════════════════════════════════════════
#  LOAD SHAPEFILES
# ═════════════════════════════════════════════════════════════════════════════
gdf_fmu = gpd.read_file(SHP_FMU)
gdf_fmu["AREA_KM2"] = (gdf_fmu["SYS_AREA"] / 1e6).round(0).astype(int)

gdf_fac = gpd.read_file(SHP_FAC)
gdf_fac["geometry"] = gdf_fac.geometry.apply(
    lambda g: g.geoms[0] if g.geom_type == "MultiPoint" else g
)
gdf_fac = gpd.GeoDataFrame(gdf_fac, geometry="geometry", crs=gdf_fac.crs)

STUDY = {
    "Trout Lake Forest":     "TroutLake",
    "Abitibi River Forest":  "Abitibi",
    "Algoma Forest":         "Algoma",
    "Kenora Forest":         "Kenora",
    "Nipissing Forest":      "Nipissing",
    "Algonquin Park Forest": "Algonquin",
}

COLORS = {
    "TroutLake": "#e41a1c", "Abitibi": "#ff7f00", "Algoma": "#4daf4a",
    "Kenora": "#984ea3", "Nipissing": "#377eb8", "Algonquin": "#a65628",
}

# ═════════════════════════════════════════════════════════════════════════════
#  FORBIOM MODEL DATA (from GAMS source)
# ═════════════════════════════════════════════════════════════════════════════
transportBase = {
    ("TroutLake","Abitibi"):38,  ("TroutLake","Algoma"):42,  ("TroutLake","Kenora"):100,
    ("TroutLake","Nipissing"):14,("TroutLake","Algonquin"):9,
    ("Abitibi","TroutLake"):26,  ("Abitibi","Algoma"):35,    ("Abitibi","Kenora"):75,
    ("Abitibi","Nipissing"):25,  ("Abitibi","Algonquin"):32,
    ("Algoma","TroutLake"):31,   ("Algoma","Abitibi"):28,    ("Algoma","Kenora"):60,
    ("Algoma","Nipissing"):31,   ("Algoma","Algonquin"):38,
    ("Kenora","TroutLake"):79,   ("Kenora","Abitibi"):61,    ("Kenora","Algoma"):49,
    ("Kenora","Nipissing"):79,   ("Kenora","Algonquin"):87,
    ("Nipissing","TroutLake"):14,("Nipissing","Abitibi"):27, ("Nipissing","Algoma"):31,
    ("Nipissing","Kenora"):79,   ("Nipissing","Algonquin"):8,
    ("Algonquin","TroutLake"):9, ("Algonquin","Abitibi"):34, ("Algonquin","Algoma"):38,
    ("Algonquin","Kenora"):87,   ("Algonquin","Nipissing"):8,
}

speciesMix = {
    "TroutLake": {"Spruce":.50,"JackPine":.30,"WhiteBirch":.10,"TolerantHdwds":.00,
                  "WhitePine":.00,"RedPine":.00,"Aspen":.10},
    "Abitibi":   {"Spruce":.60,"JackPine":.20,"WhiteBirch":.10,"TolerantHdwds":.00,
                  "WhitePine":.00,"RedPine":.00,"Aspen":.10},
    "Kenora":    {"Spruce":.40,"JackPine":.40,"WhiteBirch":.10,"TolerantHdwds":.00,
                  "WhitePine":.00,"RedPine":.05,"Aspen":.05},
    "Algoma":    {"Spruce":.10,"JackPine":.05,"WhiteBirch":.10,"TolerantHdwds":.40,
                  "WhitePine":.30,"RedPine":.05,"Aspen":.00},
    "Nipissing": {"Spruce":.10,"JackPine":.05,"WhiteBirch":.10,"TolerantHdwds":.30,
                  "WhitePine":.40,"RedPine":.05,"Aspen":.00},
    "Algonquin": {"Spruce":.05,"JackPine":.00,"WhiteBirch":.10,"TolerantHdwds":.50,
                  "WhitePine":.30,"RedPine":.05,"Aspen":.00},
}

initialStock = {
    "TroutLake":28999, "Abitibi":107775, "Algoma":54885,
    "Kenora":49746, "Nipissing":45262, "Algonquin":36725,
}

baseDemand = {
    "TroutLake": {"Lumber":3.5,"Pulpwood":3.0,"CLT":0.17,"Glulam":0.17},
    "Abitibi":   {"Lumber":5.0,"Pulpwood":6.0,"CLT":0.17,"Glulam":0.17},
    "Algoma":    {"Lumber":4.5,"Pulpwood":5.0,"CLT":0.17,"Glulam":0.17},
    "Kenora":    {"Lumber":2.5,"Pulpwood":2.0,"CLT":0.17,"Glulam":0.17},
    "Nipissing": {"Lumber":6.5,"Pulpwood":7.0,"CLT":0.17,"Glulam":0.17},
    "Algonquin": {"Lumber":4.0,"Pulpwood":4.0,"CLT":0.17,"Glulam":0.17},
}

millCap = {"Lumber":10, "Pulpwood":10, "CLT":1.0, "Glulam":1.0}

siteClass = {
    "TroutLake":"SC2", "Abitibi":"SC2", "Algoma":"SC1",
    "Kenora":"SC3", "Nipissing":"SC1", "Algonquin":"SC1",
}

basePrice = {"CLT":700, "Glulam":575, "Lumber":375, "Pulpwood":75}
yieldFactor = {"CLT":0.82, "Glulam":0.85, "Lumber":0.90, "Pulpwood":0.98}
lumberInput = {"CLT":1.20, "Glulam":1.10, "Lumber":0, "Pulpwood":0}
carbonEmit = {"CLT":0.15, "Glulam":0.17, "Lumber":0.065, "Pulpwood":0.01}
carbonStore = {"CLT":0.70, "Glulam":0.70, "Lumber":0.40, "Pulpwood":0.07}

SPECIES_COLORS = {
    "Spruce":"#2ca02c","JackPine":"#1f77b4","WhiteBirch":"#d4a017",
    "TolerantHdwds":"#8B4513","WhitePine":"#17becf","RedPine":"#e377c2","Aspen":"#bcbd22",
}
PRODUCT_COLORS = {"CLT":"#d62728","Glulam":"#ff7f0e","Lumber":"#2ca02c","Pulpwood":"#9467bd"}

FACILITY_TYPE_MAP = {
    "Sawmill - Large":"Sawmill", "Sawmill - Medium":"Sawmill", "Sawmill - Small":"Sawmill",
    "Pulp / Paper / Paperboard":"Pulp/Paper",
    "Composite":"Composite/Veneer", "Veneer":"Composite/Veneer",
    "Pellets":"Biomass/Energy", "Energy":"Biomass/Energy", "Fuelwood":"Biomass/Energy",
    "Whole Tree Chipper":"Other", "Other Facility":"Other",
}
FACILITY_COLORS = {
    "Sawmill":"#2ca02c", "Pulp/Paper":"#9467bd",
    "Composite/Veneer":"#ff7f0e", "Biomass/Energy":"#8c564b", "Other":"#7f7f7f",
}
FACILITY_ICONS = {
    "Sawmill":"industry", "Pulp/Paper":"cogs",
    "Composite/Veneer":"cubes", "Biomass/Energy":"fire", "Other":"wrench",
}
FACILITY_PRODUCT_MAP = {
    "Sawmill":"Lumber (Primary)", "Pulp/Paper":"Pulpwood (Primary)",
    "Composite/Veneer":"CLT/Glulam (Secondary)", "Biomass/Energy":"Biomass byproducts",
    "Other":"Other processing",
}

# ═════════════════════════════════════════════════════════════════════════════
#  PREPARE GEODATA
# ═════════════════════════════════════════════════════════════════════════════
gdf_study = gdf_fmu[gdf_fmu["FMU_NAME"].isin(STUDY.keys())].copy()
gdf_study["model_r"] = gdf_study["FMU_NAME"].map(STUDY)
gdf_study_wgs = gdf_study.to_crs("EPSG:4326")
gdf_study_proj = gdf_study.to_crs("EPSG:3347")
gdf_all_wgs = gdf_fmu.to_crs("EPSG:4326")
gdf_all_proj = gdf_fmu.to_crs("EPSG:3347")

centroids_proj = gdf_study_proj.set_index("model_r").geometry.centroid
centroids_wgs = gpd.GeoSeries(centroids_proj, crs="EPSG:3347").to_crs("EPSG:4326")
region_coords = {r: (centroids_wgs[r].y, centroids_wgs[r].x) for r in STUDY.values()}
centroids_xy = {r: (centroids_proj[r].x, centroids_proj[r].y) for r in STUDY.values()}

# Spatial join: facilities -> study FMU
fac_wgs = gdf_fac.to_crs("EPSG:4269")
study_for_join = gdf_fmu[gdf_fmu["FMU_NAME"].isin(STUDY.keys())].to_crs("EPSG:4269")
fac_in_study = gpd.sjoin(fac_wgs, study_for_join[["FMU_NAME","geometry"]],
                          how="inner", predicate="within")
fac_in_study["model_r"] = fac_in_study["FMU_NAME"].map(STUDY)
fac_in_study["fac_group"] = fac_in_study["FACILITY_T"].map(FACILITY_TYPE_MAP).fillna("Other")
fac_wgs["fac_group"] = fac_wgs["FACILITY_T"].map(FACILITY_TYPE_MAP).fillna("Other")

centre = [np.mean([c[0] for c in region_coords.values()]),
          np.mean([c[1] for c in region_coords.values()])]

max_stock = max(initialStock.values())

def arc_style(avg_cost):
    if avg_cost <= 15:
        return 4, "#2166ac", None
    elif avg_cost <= 35:
        return 3, "#4393c3", "8 4"
    elif avg_cost <= 50:
        return 2, "#636363", "6 4"
    else:
        return 1.5, "#bdbdbd", "4 4"

def arc_style_mpl(avg_cost):
    if avg_cost <= 15:
        return 2.5, "#2166ac", "-"
    elif avg_cost <= 35:
        return 1.8, "#4393c3", "--"
    elif avg_cost <= 50:
        return 1.2, "#636363", ":"
    else:
        return 0.8, "#bdbdbd", ":"

def offset_point(lat1, lon1, lat2, lon2, frac=0.12):
    """Offset midpoint perpendicular to avoid overlapping arcs."""
    mx, my = (lat1+lat2)/2, (lon1+lon2)/2
    dx, dy = lat2-lat1, lon2-lon1
    length = math.sqrt(dx*dx + dy*dy) or 1
    return mx + frac*(-dy)/length, my + frac*(dx)/length


# ═════════════════════════════════════════════════════════════════════════════
#  MAP 1: INTERACTIVE NETWORK FLOW MAP
# ═════════════════════════════════════════════════════════════════════════════
print("Building Map 1: Network Flow ...")
m1 = folium.Map(location=centre, zoom_start=5, tiles=None)

folium.TileLayer(
    tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    attr="OpenStreetMap / CARTO", name="CartoDB Light", control=False,
).add_to(m1)
folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m1)
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri", name="Satellite",
).add_to(m1)

# Background FMUs
bg = folium.FeatureGroup(name="Other Ontario FMUs", show=True)
for _, row in gdf_all_wgs[~gdf_all_wgs["FMU_NAME"].isin(STUDY.keys())].iterrows():
    folium.GeoJson(
        row["geometry"].__geo_interface__,
        style_function=lambda _f: {"fillColor":"#e8e8e8","color":"#ccc","weight":0.5,"fillOpacity":0.30},
        tooltip=folium.Tooltip(row["FMU_NAME"]),
    ).add_to(bg)
bg.add_to(m1)

# Study region polygons with full model-data popups
rg = folium.FeatureGroup(name="Study Regions (nodes)", show=True)
for _, row in gdf_study_wgs.iterrows():
    r = row["model_r"]
    color = COLORS[r]
    stock = initialStock[r]
    sc = siteClass[r]
    mix = speciesMix[r]
    dem = baseDemand[r]
    top3 = sorted(mix.items(), key=lambda x: -x[1])[:3]
    top3_str = ", ".join(f"{s} {int(v*100)}%" for s,v in top3 if v > 0)

    fac_here = fac_in_study[fac_in_study["model_r"]==r]
    fac_count = len(fac_here)
    fac_active = len(fac_here[fac_here["OPERATING_"]=="Active"])

    species_bars = "".join(
        f'<div style="display:inline-block;width:{max(int(v*100),1)}px;height:14px;'
        f'background:{SPECIES_COLORS[s]};margin:0" title="{s}: {int(v*100)}%"></div>'
        for s,v in mix.items() if v > 0
    )
    prod_rows = "".join(
        f'<tr><td style="color:{PRODUCT_COLORS[p]}"><b>{p}</b></td>'
        f'<td>${basePrice[p]}/m3</td>'
        f'<td>{dem[p]:.2f}</td><td>{millCap[p]:.1f}</td>'
        f'<td>{yieldFactor[p]:.2f}</td></tr>'
        for p in ["Lumber","Pulpwood","CLT","Glulam"]
    )
    carbon_rows = "".join(
        f'<tr><td style="color:{PRODUCT_COLORS[p]}">{p}</td>'
        f'<td>{carbonEmit[p]:.3f}</td><td>{carbonStore[p]:.2f}</td>'
        f'<td style="color:{"#c00" if carbonEmit[p]>carbonStore[p] else "#080"}">'
        f'{carbonStore[p]-carbonEmit[p]:+.3f}</td></tr>'
        for p in ["Lumber","Pulpwood","CLT","Glulam"]
    )
    transport_rows = "".join(
        f'<tr><td>{rr}</td><td>${transportBase[(r,rr)]}/m3</td><td>20 M m3/yr</td>'
        f'<td>0.018</td></tr>'
        for rr in STUDY.values() if rr != r
    )
    fac_rows = ""
    for _, fr in fac_here.iterrows():
        fg = fr["fac_group"]
        fac_rows += (
            f'<tr><td><span style="color:{FACILITY_COLORS.get(fg,"#777")}">&#9632;</span> '
            f'{fr["FACILITY_C"][:35]}</td><td>{fr["FACILITY_T"]}</td>'
            f'<td>{fr["OPERATING_"]}</td></tr>'
        )

    popup_html = f"""
    <div style="font-family:Arial;min-width:420px;max-width:500px;font-size:11px">
      <h3 style="margin:0 0 6px;color:{color};border-bottom:3px solid {color};padding-bottom:4px">
        Node: {r}</h3>

      <table style="border-collapse:collapse;width:100%">
        <tr><td><b>Initial Roundwood Stock</b></td><td>{stock:,} M m3</td></tr>
        <tr><td><b>Site Class</b></td><td>{sc}</td></tr>
        <tr><td><b>Max Harvest Rate</b></td><td>1% of stock per year</td></tr>
        <tr><td><b>Harvest Cost</b></td><td>$38/m3 (base)</td></tr>
        <tr><td><b>Processing Facilities</b></td><td>{fac_count} ({fac_active} active)</td></tr>
      </table>

      <h4 style="margin:8px 0 3px">Species Composition</h4>
      <div style="border:1px solid #ccc;border-radius:3px;overflow:hidden;height:14px;width:100%">
        {species_bars}</div>
      <div style="font-size:10px;color:#666;margin-top:2px">{top3_str}</div>

      <h4 style="margin:8px 0 3px">Product Parameters</h4>
      <table style="border-collapse:collapse;width:100%;font-size:10px">
        <tr style="background:#f0f0f0"><th>Product</th><th>Price</th>
            <th>Demand (M m3)</th><th>Mill Cap (M m3)</th><th>Yield</th></tr>
        {prod_rows}
      </table>

      <h4 style="margin:8px 0 3px">Carbon Accounting (tCO2/m3)</h4>
      <table style="border-collapse:collapse;width:100%;font-size:10px">
        <tr style="background:#f0f0f0"><th>Product</th><th>Emission</th>
            <th>Storage</th><th>Net</th></tr>
        {carbon_rows}
      </table>

      <h4 style="margin:8px 0 3px">Transport Arcs from {r}</h4>
      <table style="border-collapse:collapse;width:100%;font-size:10px">
        <tr style="background:#f0f0f0"><th>To</th><th>Cost</th><th>Arc Cap</th>
            <th>tCO2/m3</th></tr>
        {transport_rows}
      </table>

      <h4 style="margin:8px 0 3px">Processing Facilities in FMU</h4>
      <table style="border-collapse:collapse;width:100%;font-size:10px">
        <tr style="background:#f0f0f0"><th>Name</th><th>Type</th><th>Status</th></tr>
        {fac_rows if fac_rows else '<tr><td colspan="3" style="color:#999">None within FMU boundary</td></tr>'}
      </table>
    </div>"""

    folium.GeoJson(
        row["geometry"].__geo_interface__,
        style_function=lambda _f, c=color: {
            "fillColor":c,"color":"#222","weight":2.5,"fillOpacity":0.55,
        },
        highlight_function=lambda _f, c=color: {
            "fillColor":c,"fillOpacity":0.85,"weight":3.5,"color":"#000",
        },
        tooltip=folium.Tooltip(
            f"<b>{r}</b> | Stock: {stock:,} M m3 | Mills: {fac_count} | {top3_str}"
        ),
        popup=folium.Popup(popup_html, max_width=520),
    ).add_to(rg)
rg.add_to(m1)

# Facilities layer
fac_group = folium.FeatureGroup(name="Processing Facilities (111 mills)", show=True)
fac_wgs_4326 = gdf_fac.to_crs("EPSG:4326")
fac_wgs_4326["fac_group"] = fac_wgs_4326["FACILITY_T"].map(FACILITY_TYPE_MAP).fillna("Other")
for _, fr in fac_wgs_4326.iterrows():
    fg = fr["fac_group"]
    fc = FACILITY_COLORS.get(fg, "#777")
    fi = FACILITY_ICONS.get(fg, "wrench")
    fp = FACILITY_PRODUCT_MAP.get(fg, "")
    status = fr["OPERATING_"]
    opacity = 1.0 if status == "Active" else 0.5

    folium.Marker(
        location=[fr.geometry.y, fr.geometry.x],
        icon=folium.Icon(color="white", icon_color=fc, icon=fi, prefix="fa"),
        tooltip=folium.Tooltip(
            f"<b>{fr['FACILITY_C'][:40]}</b><br>{fr['FACILITY_T']} | {status}<br>"
            f"<i>{fp}</i> | {fr['LOCATION']}"
        ),
        popup=folium.Popup(
            f"<div style='font-family:Arial;min-width:200px'>"
            f"<h4 style='color:{fc};margin:0 0 4px'>{fr['FACILITY_C']}</h4>"
            f"<b>Type:</b> {fr['FACILITY_T']}<br>"
            f"<b>Model product:</b> {fp}<br>"
            f"<b>Location:</b> {fr['LOCATION']}<br>"
            f"<b>Status:</b> {status}</div>",
            max_width=280,
        ),
    ).add_to(fac_group)
fac_group.add_to(m1)

# Directed trade arcs (both directions shown with curve offsets)
arc_group = folium.FeatureGroup(name="Trade Arcs (directed, $/m3 + cap)", show=True)
for (r1,r2), cost in transportBase.items():
    lat1, lon1 = region_coords[r1]
    lat2, lon2 = region_coords[r2]
    w, c, d = arc_style(cost)

    # Slight offset for direction
    mid_lat, mid_lon = offset_point(lat1, lon1, lat2, lon2, frac=0.06)

    points = [[lat1, lon1], [mid_lat, mid_lon], [lat2, lon2]]

    tt = (
        f"<b>{r1} --> {r2}</b><br>"
        f"Cost: ${cost}/m3<br>"
        f"Arc capacity: 20 M m3/yr<br>"
        f"Emission: 0.018 tCO2/m3"
    )
    folium.PolyLine(
        locations=points, weight=w, color=c, opacity=0.7,
        dash_array=d, tooltip=folium.Tooltip(tt),
    ).add_to(arc_group)

    # Arrowhead at destination
    folium.RegularPolygonMarker(
        location=[lat2 + 0.08*(mid_lat-lat2), lon2 + 0.08*(mid_lon-lon2)],
        number_of_sides=3, radius=5, color=c, fill=True,
        fill_color=c, fill_opacity=0.8, rotation=0,
    ).add_to(arc_group)

arc_group.add_to(m1)

# Cost labels at arc midpoints (undirected, averaged)
label_group_arcs = folium.FeatureGroup(name="Arc Cost Labels", show=True)
drawn_pairs = set()
for (r1,r2), cost in transportBase.items():
    pair = tuple(sorted([r1,r2]))
    if pair in drawn_pairs:
        continue
    drawn_pairs.add(pair)
    cost_rev = transportBase.get((r2,r1), cost)
    avg = (cost + cost_rev) / 2
    lat1, lon1 = region_coords[r1]
    lat2, lon2 = region_coords[r2]
    mid_lat, mid_lon = (lat1+lat2)/2, (lon1+lon2)/2

    folium.Marker(
        location=[mid_lat, mid_lon],
        icon=folium.DivIcon(
            html=f'<div style="font-size:9px;font-weight:bold;color:#333;'
                 f'background:rgba(255,255,255,0.9);padding:1px 4px;border-radius:3px;'
                 f'white-space:nowrap;text-align:center;border:1px solid #aaa">'
                 f'${int(avg)}/m3</div>',
            icon_size=(55,18), icon_anchor=(27,9),
        ),
    ).add_to(label_group_arcs)
label_group_arcs.add_to(m1)

# Stock bubbles + region labels
node_labels = folium.FeatureGroup(name="Node Labels & Stock Bubbles", show=True)
for r, (lat, lon) in region_coords.items():
    color = COLORS[r]
    stock = initialStock[r]
    radius = 12 + 25 * (stock / max_stock)
    folium.CircleMarker(
        location=[lat, lon], radius=radius,
        color=color, fill=True, fill_color=color, fill_opacity=0.20, weight=2,
    ).add_to(node_labels)
    folium.Marker(
        location=[lat, lon],
        icon=folium.DivIcon(
            html=f'<div style="font-size:11px;font-weight:bold;color:{color};'
                 f'white-space:nowrap;text-align:center;'
                 f'text-shadow:0 0 4px #fff,0 0 4px #fff,0 0 4px #fff">'
                 f'{r}<br><span style="font-size:9px;color:#333">'
                 f'{stock:,} M m3</span></div>',
            icon_size=(140,36), icon_anchor=(70,18),
        ),
    ).add_to(node_labels)
node_labels.add_to(m1)

# Legend
region_leg = "".join(
    f'<span style="background:{COLORS[r]};display:inline-block;width:12px;height:12px;'
    f'margin-right:5px;border-radius:2px;border:1px solid #555"></span>{r}<br>'
    for r in STUDY.values()
)
fac_leg = "".join(
    f'<span style="color:{FACILITY_COLORS[fg]}">&#9632;</span> {fg} '
    f'<small>({FACILITY_PRODUCT_MAP[fg]})</small><br>'
    for fg in FACILITY_COLORS
)
legend_html = f"""
<div style="position:fixed;bottom:20px;left:20px;z-index:1000;
     background:white;padding:14px 16px;border-radius:10px;
     box-shadow:0 3px 12px rgba(0,0,0,.35);font-family:Arial;font-size:11px;
     line-height:1.7;max-height:85vh;overflow-y:auto;max-width:240px">
  <b style="font-size:14px;color:#1a1a2e">FORBIOM Network Flow</b><br>
  <span style="font-size:9px;color:#666">Multi-commodity NLP (GAMS)</span>
  <hr style="margin:5px 0;border-color:#eee">
  <b>Regions (r)</b><br>{region_leg}
  <hr style="margin:5px 0;border-color:#eee">
  <b>Facilities</b><br>{fac_leg}
  <hr style="margin:5px 0;border-color:#eee">
  <b>Arc Cost ($/m3)</b><br>
  <span style="display:inline-block;width:24px;height:3px;background:#2166ac;margin-right:4px;vertical-align:middle"></span>&lt;$15<br>
  <span style="display:inline-block;width:24px;height:0;border-top:2px dashed #4393c3;margin-right:4px;vertical-align:middle"></span>$15-35<br>
  <span style="display:inline-block;width:24px;height:0;border-top:2px dotted #636363;margin-right:4px;vertical-align:middle"></span>$35-50<br>
  <span style="display:inline-block;width:24px;height:0;border-top:1px dotted #bdbdbd;margin-right:4px;vertical-align:middle"></span>&gt;$50<br>
  <hr style="margin:5px 0;border-color:#eee">
  <b>Bubble size</b> = Roundwood stock<br>
  <small style="color:#888">Click nodes / arcs / mills for details</small>
</div>"""
m1.get_root().html.add_child(folium.Element(legend_html))

# Title
title_html = """
<div style="position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:1000;
     background:rgba(26,26,46,0.93);padding:10px 28px;border-radius:8px;
     font-family:Arial;text-align:center;box-shadow:0 2px 10px rgba(0,0,0,.3)">
  <span style="color:white;font-size:17px;font-weight:bold">
    FORBIOM &mdash; Network Flow Model</span><br>
  <span style="color:#bbb;font-size:11px">
    6 Regions &bull; 4 Products &bull; 30 Directed Arcs &bull; 111 Mills &bull; 2020-2030
  </span>
</div>"""
m1.get_root().html.add_child(folium.Element(title_html))

# Value chain overlay
chain_html = """
<div style="position:fixed;top:80px;right:20px;z-index:1000;
     background:white;padding:12px 16px;border-radius:10px;
     box-shadow:0 3px 12px rgba(0,0,0,.3);font-family:Arial;font-size:11px;
     max-width:250px">
  <b style="font-size:12px;color:#1a1a2e">Value Chain (per node)</b>
  <div style="margin-top:6px;padding:6px;background:#f8f9fa;border-radius:6px;line-height:1.7">
    <div style="text-align:center;padding:3px;background:#8B4513;color:white;border-radius:3px;
         margin-bottom:3px;font-size:10px">ROUNDWOOD STOCK</div>
    <div style="text-align:center;color:#888;font-size:9px">&darr; harvest &le; 1%/yr &darr;</div>
    <div style="display:flex;gap:3px;margin:3px 0">
      <div style="flex:1;text-align:center;padding:3px;background:#2ca02c;color:white;
           border-radius:3px;font-size:9px">Lumber<br>y=0.90</div>
      <div style="flex:1;text-align:center;padding:3px;background:#9467bd;color:white;
           border-radius:3px;font-size:9px">Pulpwood<br>y=0.98</div>
    </div>
    <div style="text-align:center;color:#888;font-size:9px">&darr; lumber as input &darr;</div>
    <div style="display:flex;gap:3px;margin:3px 0">
      <div style="flex:1;text-align:center;padding:3px;background:#d62728;color:white;
           border-radius:3px;font-size:9px">CLT<br>1.2 m3/m3</div>
      <div style="flex:1;text-align:center;padding:3px;background:#ff7f0e;color:white;
           border-radius:3px;font-size:9px">Glulam<br>1.1 m3/m3</div>
    </div>
    <hr style="margin:4px 0;border-color:#eee">
    <div style="font-size:9px;color:#555">
      <b>Obj</b> = Revenue - HarvestCost -<br>
      ProcCost - TransCost - CarbonCost<br>
      <b>Carbon price:</b> $170/tCO2
    </div>
  </div>
</div>"""
m1.get_root().html.add_child(folium.Element(chain_html))

folium.LayerControl(collapsed=False).add_to(m1)
path1 = os.path.join(OUT_DIR, "forbiom_network_map.html")
m1.save(path1)
print(f"  -> {path1}")


# ═════════════════════════════════════════════════════════════════════════════
#  MAP 2: INTERACTIVE SUPPLY CHAIN MAP
# ═════════════════════════════════════════════════════════════════════════════
print("Building Map 2: Supply Chain ...")
m2 = folium.Map(location=centre, zoom_start=5, tiles=None)

folium.TileLayer(
    tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    attr="OpenStreetMap / CARTO", name="CartoDB Light", control=False,
).add_to(m2)
folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m2)

# Background
bg2 = folium.FeatureGroup(name="Other FMUs", show=True)
for _, row in gdf_all_wgs[~gdf_all_wgs["FMU_NAME"].isin(STUDY.keys())].iterrows():
    folium.GeoJson(
        row["geometry"].__geo_interface__,
        style_function=lambda _f: {"fillColor":"#e8e8e8","color":"#ccc","weight":0.5,"fillOpacity":0.25},
        tooltip=folium.Tooltip(row["FMU_NAME"]),
    ).add_to(bg2)
bg2.add_to(m2)

# Study regions colored by dominant species type (boreal vs hardwood)
forest_layer = folium.FeatureGroup(name="Forest Regions (species-colored)", show=True)
for _, row in gdf_study_wgs.iterrows():
    r = row["model_r"]
    mix = speciesMix[r]
    boreal_frac = mix["Spruce"] + mix["JackPine"] + mix.get("Aspen",0)
    hardwood_frac = mix["TolerantHdwds"] + mix["WhitePine"] + mix.get("RedPine",0)
    if boreal_frac > hardwood_frac:
        fill = "#2d6a4f"
    else:
        fill = "#6b4226"

    top3 = sorted(mix.items(), key=lambda x: -x[1])[:3]
    top3_str = ", ".join(f"{s} {int(v*100)}%" for s,v in top3 if v > 0)

    species_bars = "".join(
        f'<div style="display:inline-block;width:{max(int(v*150),1)}px;height:16px;'
        f'background:{SPECIES_COLORS[s]};margin:0" title="{s}: {int(v*100)}%"></div>'
        for s,v in mix.items() if v > 0
    )
    species_legend = "".join(
        f'<span style="color:{SPECIES_COLORS[s]}">&#9632;</span> {s} ({int(v*100)}%) '
        for s,v in mix.items() if v > 0
    )

    popup_html = f"""
    <div style="font-family:Arial;min-width:300px;font-size:11px">
      <h3 style="margin:0 0 6px;color:{COLORS[r]};border-bottom:3px solid {COLORS[r]};
          padding-bottom:4px">{r} -- Forest Composition</h3>
      <p><b>Dominant type:</b> {"Boreal softwood" if boreal_frac>hardwood_frac else "Hardwood/mixed"}</p>
      <h4 style="margin:8px 0 3px">Species Bar</h4>
      <div style="border:1px solid #ccc;border-radius:4px;overflow:hidden;height:16px;width:100%">
        {species_bars}</div>
      <div style="font-size:10px;margin-top:4px">{species_legend}</div>
      <h4 style="margin:8px 0 3px">Site Class: {siteClass[r]}</h4>
      <p style="font-size:10px;color:#555">
        Initial stock: {initialStock[r]:,} M m3<br>
        Sustainable harvest: {initialStock[r]*0.01:,.0f} M m3/yr (1%)<br>
        Growth replenishes stock annually (stochastic shock +/-12%)
      </p>
    </div>"""

    folium.GeoJson(
        row["geometry"].__geo_interface__,
        style_function=lambda _f, f=fill: {
            "fillColor":f,"color":"#222","weight":2,"fillOpacity":0.50,
        },
        highlight_function=lambda _f: {"fillOpacity":0.75,"weight":3,"color":"#000"},
        tooltip=folium.Tooltip(f"<b>{r}</b> | {top3_str}"),
        popup=folium.Popup(popup_html, max_width=400),
    ).add_to(forest_layer)
forest_layer.add_to(m2)

# Facility markers by product-chain layer
for fg in ["Sawmill","Pulp/Paper","Composite/Veneer","Biomass/Energy","Other"]:
    fg_layer = folium.FeatureGroup(
        name=f"Facilities: {fg} ({FACILITY_PRODUCT_MAP.get(fg,'')})", show=True
    )
    subset = fac_wgs_4326[fac_wgs_4326["fac_group"]==fg]
    for _, fr in subset.iterrows():
        fc = FACILITY_COLORS[fg]
        fi = FACILITY_ICONS[fg]
        status = fr["OPERATING_"]

        size_map = {"Sawmill - Large":10, "Sawmill - Medium":7, "Sawmill - Small":5}
        radius = size_map.get(fr["FACILITY_T"], 7)

        folium.CircleMarker(
            location=[fr.geometry.y, fr.geometry.x],
            radius=radius,
            color=fc, fill=True, fill_color=fc,
            fill_opacity=0.85 if status=="Active" else 0.3,
            weight=1.5 if status=="Active" else 0.5,
            tooltip=folium.Tooltip(
                f"<b>{fr['FACILITY_C'][:40]}</b><br>"
                f"{fr['FACILITY_T']} | {status}<br>"
                f"<i>FORBIOM product: {FACILITY_PRODUCT_MAP.get(fg,'')}</i>"
            ),
            popup=folium.Popup(
                f"<div style='font-family:Arial;min-width:220px'>"
                f"<h4 style='color:{fc};margin:0 0 4px'>{fr['FACILITY_C']}</h4>"
                f"<b>Type:</b> {fr['FACILITY_T']}<br>"
                f"<b>FORBIOM tier:</b> {FACILITY_PRODUCT_MAP.get(fg,'')}<br>"
                f"<b>Location:</b> {fr['LOCATION']}<br>"
                f"<b>Status:</b> {status}<br>"
                f"<b>Mill cap (model):</b> "
                f"{'10 M m3/yr' if fg in ('Sawmill','Pulp/Paper') else '1.0 M m3/yr'}"
                f"</div>",
                max_width=300,
            ),
        ).add_to(fg_layer)
    fg_layer.add_to(m2)

# Region labels
for r, (lat, lon) in region_coords.items():
    folium.Marker(
        location=[lat, lon],
        icon=folium.DivIcon(
            html=f'<div style="font-size:11px;font-weight:bold;color:{COLORS[r]};'
                 f'white-space:nowrap;text-align:center;'
                 f'text-shadow:0 0 5px #fff,0 0 5px #fff,0 0 5px #fff">'
                 f'{r}</div>',
            icon_size=(130,20), icon_anchor=(65,10),
        ),
    ).add_to(m2)

# Legend
sc_legend = f"""
<div style="position:fixed;bottom:20px;left:20px;z-index:1000;
     background:white;padding:14px 16px;border-radius:10px;
     box-shadow:0 3px 12px rgba(0,0,0,.35);font-family:Arial;font-size:11px;
     line-height:1.7;max-width:260px">
  <b style="font-size:14px;color:#1a1a2e">FORBIOM Supply Chain</b><br>
  <span style="font-size:9px;color:#666">Forest --> Primary --> Secondary</span>
  <hr style="margin:5px 0;border-color:#eee">
  <b>Forest Type</b><br>
  <span style="background:#2d6a4f;display:inline-block;width:12px;height:12px;margin-right:5px;border-radius:2px"></span>Boreal softwood<br>
  <span style="background:#6b4226;display:inline-block;width:12px;height:12px;margin-right:5px;border-radius:2px"></span>Hardwood / mixed<br>
  <hr style="margin:5px 0;border-color:#eee">
  <b>Facility Types</b><br>
  {fac_leg}
  <hr style="margin:5px 0;border-color:#eee">
  <b>Circle size</b> = Mill size (L/M/S)<br>
  <small style="color:#888">Toggle facility layers on/off</small>
</div>"""
m2.get_root().html.add_child(folium.Element(sc_legend))

# Inset: objective function
obj_html = """
<div style="position:fixed;top:10px;right:20px;z-index:1000;
     background:white;padding:14px 16px;border-radius:10px;
     box-shadow:0 3px 12px rgba(0,0,0,.3);font-family:Arial;font-size:11px;
     max-width:320px">
  <b style="font-size:13px;color:#1a1a2e">FORBIOM Objective & Constraints</b>
  <div style="margin-top:6px;font-size:10px;line-height:1.6;font-family:monospace;
       background:#f8f9fa;padding:8px;border-radius:4px">
    <b>max</b> Obj = Revenue - HarvestCost<br>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- ProcCost - TransCost<br>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- CarbonPrice * Emissions<br><br>
    <b>s.t.</b><br>
    &bull; stock(r,y) = stock(r,y-1) + growth - harvest<br>
    &bull; harvest(r,y) &le; 1% of stock<br>
    &bull; production(r,p) &le; millCap(r,p)<br>
    &bull; sales(r,p,y) &le; demandCap(r,p,y)<br>
    &bull; exports(r,rr,p,y) &le; arcCap = 20 M m3/yr<br>
    &bull; lumber balance: prod + imports<br>
    &nbsp;&nbsp;= sales + exports + CLT/Glulam input<br>
    &bull; carbon: emit = f(prod) + f(transport)<br>
    &bull; storage = g(prod); net = emit - store
  </div>
</div>"""
m2.get_root().html.add_child(folium.Element(obj_html))

title2 = """
<div style="position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:1000;
     background:rgba(26,26,46,0.93);padding:10px 28px;border-radius:8px;
     font-family:Arial;text-align:center;box-shadow:0 2px 10px rgba(0,0,0,.3)">
  <span style="color:white;font-size:17px;font-weight:bold">
    FORBIOM &mdash; Supply Chain & Facilities</span><br>
  <span style="color:#bbb;font-size:11px">
    Forest Resources &bull; 111 Processing Facilities &bull; Primary + Secondary Tiers
  </span>
</div>"""
m2.get_root().html.add_child(folium.Element(title2))

folium.LayerControl(collapsed=False).add_to(m2)
path2 = os.path.join(OUT_DIR, "forbiom_supply_chain.html")
m2.save(path2)
print(f"  -> {path2}")


# ═════════════════════════════════════════════════════════════════════════════
#  MAP 3: STATIC PUBLICATION FIGURE (300 DPI)
# ═════════════════════════════════════════════════════════════════════════════
print("Building Map 3: Static OR figure ...")

fig, ax = plt.subplots(1, 1, figsize=(20, 16))
fig.patch.set_facecolor("white")
ax.set_facecolor("#eef2f7")

# Background FMUs
gdf_all_proj[~gdf_all_proj["FMU_NAME"].isin(STUDY.keys())].plot(
    ax=ax, color="#dde3ea", edgecolor="white", linewidth=0.4, alpha=0.6
)

# Study regions with stock-based intensity
for _, row in gdf_study_proj.iterrows():
    r = row["model_r"]
    stock_frac = initialStock[r] / max_stock
    alpha = 0.4 + 0.5 * stock_frac
    gdf_study_proj[gdf_study_proj.index == _].plot(
        ax=ax, color=COLORS[r], edgecolor="#222", linewidth=2.2, alpha=alpha
    )

# Transport arcs
drawn = set()
for (r1,r2), cost in transportBase.items():
    pair = tuple(sorted([r1,r2]))
    if pair in drawn:
        continue
    drawn.add(pair)
    cost_rev = transportBase.get((r2,r1), cost)
    avg = (cost + cost_rev) / 2
    x1, y1 = centroids_xy[r1]
    x2, y2 = centroids_xy[r2]
    lw, c, ls = arc_style_mpl(avg)

    ax.annotate(
        "", xy=(x2,y2), xytext=(x1,y1),
        arrowprops=dict(arrowstyle="-|>", color=c, lw=lw, ls=ls,
                        connectionstyle="arc3,rad=0.1", alpha=0.6),
        zorder=2,
    )
    dx, dy = x2-x1, y2-y1
    length = math.sqrt(dx*dx+dy*dy) or 1
    mx, my = (x1+x2)/2 + 0.08*(-dy), (y1+y2)/2 + 0.08*(dx)
    ax.annotate(
        f"${int(avg)}", xy=(mx, my), ha="center", va="center",
        fontsize=6.5, color="#333", fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#bbb", alpha=0.9, lw=0.5),
        zorder=5,
    )

# Facility points
fac_proj = gdf_fac.to_crs("EPSG:3347")
fac_proj["fac_group"] = fac_proj["FACILITY_T"].map(FACILITY_TYPE_MAP).fillna("Other")
for fg in ["Sawmill","Pulp/Paper","Composite/Veneer","Biomass/Energy","Other"]:
    subset = fac_proj[fac_proj["fac_group"]==fg]
    if len(subset) == 0:
        continue
    active = subset[subset["OPERATING_"]=="Active"]
    inactive = subset[subset["OPERATING_"]!="Active"]
    fc = FACILITY_COLORS[fg]
    if len(active) > 0:
        ax.scatter(
            active.geometry.x, active.geometry.y,
            c=fc, s=25, edgecolors="#222", linewidths=0.5,
            zorder=8, label=f"{fg} (active)",
            marker="^" if fg in ("Sawmill","Pulp/Paper") else "s",
        )
    if len(inactive) > 0:
        ax.scatter(
            inactive.geometry.x, inactive.geometry.y,
            c=fc, s=15, edgecolors="#888", linewidths=0.3,
            zorder=7, alpha=0.4,
            marker="^" if fg in ("Sawmill","Pulp/Paper") else "s",
        )

# Stacked capacity/demand bars at each region
fig.canvas.draw()
bar_w_frac = 0.028
bar_h_frac = 0.08
products_order = ["Lumber","Pulpwood","CLT","Glulam"]

for r, (cx, cy) in centroids_xy.items():
    pos_data = ax.transData.transform((cx, cy))
    pos_fig = fig.transFigure.inverted().transform(pos_data)

    bx = pos_fig[0] + 0.025
    by = pos_fig[1] - bar_h_frac/2

    bx = max(0.02, min(bx, 0.95 - bar_w_frac*2.5))
    by = max(0.05, min(by, 0.95 - bar_h_frac))

    bar_ax = fig.add_axes([bx, by, bar_w_frac*2.2, bar_h_frac])

    caps = [millCap[p] for p in products_order]
    dems = [baseDemand[r][p] for p in products_order]
    x_pos = np.arange(len(products_order))

    bar_ax.bar(x_pos - 0.18, caps, 0.32, color=[PRODUCT_COLORS[p] for p in products_order],
               alpha=0.8, edgecolor="#222", linewidth=0.5, label="Mill Cap")
    bar_ax.bar(x_pos + 0.18, dems, 0.32, color=[PRODUCT_COLORS[p] for p in products_order],
               alpha=0.4, edgecolor="#222", linewidth=0.5, hatch="//", label="Demand")

    bar_ax.set_xticks(x_pos)
    bar_ax.set_xticklabels(["L","P","C","G"], fontsize=5)
    bar_ax.tick_params(axis="y", labelsize=4, length=2)
    bar_ax.set_ylabel("M m3", fontsize=4, labelpad=1)
    bar_ax.set_title(r, fontsize=6, fontweight="bold", color=COLORS[r], pad=2)
    bar_ax.spines["top"].set_visible(False)
    bar_ax.spines["right"].set_visible(False)
    bar_ax.spines["left"].set_linewidth(0.4)
    bar_ax.spines["bottom"].set_linewidth(0.4)

# Region labels
for r, (cx, cy) in centroids_xy.items():
    stock = initialStock[r]
    color = COLORS[r]
    ax.annotate(
        f"{r}\n{stock:,} M m3",
        xy=(cx, cy), ha="center", va="center",
        fontsize=7.5, fontweight="bold", color="white",
        bbox=dict(boxstyle="round,pad=0.3", fc=color, ec="#222", lw=1, alpha=0.9),
        zorder=10,
    )

# Legends
region_patches = [
    mpatches.Patch(fc=COLORS[r], ec="#222", lw=1, label=r) for r in STUDY.values()
]
fac_handles = [
    plt.Line2D([0],[0], marker="^", color="w", markerfacecolor=FACILITY_COLORS["Sawmill"],
               markersize=6, markeredgecolor="#222", label="Sawmill"),
    plt.Line2D([0],[0], marker="^", color="w", markerfacecolor=FACILITY_COLORS["Pulp/Paper"],
               markersize=6, markeredgecolor="#222", label="Pulp/Paper"),
    plt.Line2D([0],[0], marker="s", color="w", markerfacecolor=FACILITY_COLORS["Composite/Veneer"],
               markersize=5, markeredgecolor="#222", label="Composite/Veneer"),
    plt.Line2D([0],[0], marker="s", color="w", markerfacecolor=FACILITY_COLORS["Biomass/Energy"],
               markersize=5, markeredgecolor="#222", label="Biomass/Energy"),
]
arc_handles = [
    plt.Line2D([0],[0], color="#2166ac", lw=2.5, ls="-",  label="< $15/m3"),
    plt.Line2D([0],[0], color="#4393c3", lw=1.8, ls="--", label="$15-35/m3"),
    plt.Line2D([0],[0], color="#636363", lw=1.2, ls=":",  label="$35-50/m3"),
    plt.Line2D([0],[0], color="#bdbdbd", lw=0.8, ls=":",  label="> $50/m3"),
]
bar_handles = [
    mpatches.Patch(fc="#aaa", ec="#222", lw=0.5, alpha=0.8, label="Mill capacity"),
    mpatches.Patch(fc="#aaa", ec="#222", lw=0.5, alpha=0.4, label="Base demand", hatch="//"),
]

leg1 = ax.legend(handles=region_patches, title="Study Regions",
                 loc="lower right", fontsize=8, title_fontsize=9,
                 framealpha=0.95, edgecolor="#ccc", fancybox=True)
ax.add_artist(leg1)

leg2 = ax.legend(handles=fac_handles + arc_handles, title="Facilities & Transport",
                 loc="upper right", fontsize=7, title_fontsize=8,
                 framealpha=0.95, edgecolor="#ccc", fancybox=True)
ax.add_artist(leg2)

ax.legend(handles=bar_handles, title="Capacity Bars",
          loc="upper left", fontsize=7, title_fontsize=8,
          framealpha=0.95, edgecolor="#ccc", fancybox=True)

# Carbon + model summary text box
summary_text = (
    "FORBIOM: Multi-commodity NLP\n"
    "max Obj = Revenue - HarvestCost - ProcCost\n"
    "           - TransCost - CarbonPrice*Emit\n"
    "\n"
    "Products: Lumber, Pulpwood (Primary)\n"
    "          CLT, Glulam (Secondary)\n"
    "Carbon price: $170/tCO2\n"
    "Arc capacity: 20 M m3/yr\n"
    "Harvest: max 1% stock/yr\n"
    "Prices: 3% annual growth"
)
ax.text(
    0.01, 0.99, summary_text, transform=ax.transAxes,
    fontsize=7, fontfamily="monospace", va="top",
    bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="#1a1a2e", lw=1.5, alpha=0.95),
    zorder=20,
)

# Carbon table
carbon_text = (
    "Carbon (tCO2/m3)  Emit   Store  Net\n"
    "  Lumber           0.065  0.40  +0.335\n"
    "  Pulpwood          0.010  0.07  +0.060\n"
    "  CLT              0.150  0.70  +0.550\n"
    "  Glulam            0.170  0.70  +0.530"
)
ax.text(
    0.01, 0.72, carbon_text, transform=ax.transAxes,
    fontsize=6.5, fontfamily="monospace", va="top",
    bbox=dict(boxstyle="round,pad=0.4", fc="#fffff0", ec="#888", lw=0.8, alpha=0.95),
    zorder=20,
)

ax.set_title(
    "FORBIOM: Ontario Forest Bioeconomy Optimization Model\n"
    "Network Flow Structure with Processing Facilities",
    fontsize=15, fontweight="bold", pad=14, color="#1a1a2e",
)
ax.set_axis_off()

fig.text(
    0.5, 0.01,
    "Source: Ontario LIO (2025) | Forest Processing Facilities | FORBIOM (GAMS NLP)"
    " | Bars: L=Lumber, P=Pulpwood, C=CLT, G=Glulam",
    fontsize=7, color="#666", ha="center",
)

path3 = os.path.join(OUT_DIR, "forbiom_or_figure.png")
plt.savefig(path3, dpi=300, bbox_inches="tight", facecolor="white")
plt.close()
print(f"  -> {path3}")


# ═════════════════════════════════════════════════════════════════════════════
#  MAP 4: MODEL EXPLAINER -- FROM FOREST TO MARKET
# ═════════════════════════════════════════════════════════════════════════════
print("Building Map 4: Model Explainer ...")

MARKET_HUBS = {
    "Greater Toronto Area": (43.65, -79.38),
    "Ottawa-Gatineau":      (45.42, -75.70),
    "Sudbury / North Bay":  (46.49, -81.00),
    "Thunder Bay":          (48.38, -89.25),
    "Sault Ste. Marie":     (46.52, -84.33),
}

# Assign each study region to its nearest market hub(s) for conceptual demand arrows
REGION_TO_HUBS = {
    "TroutLake":  ["Thunder Bay"],
    "Abitibi":    ["Sudbury / North Bay"],
    "Algoma":     ["Sault Ste. Marie", "Greater Toronto Area"],
    "Kenora":     ["Thunder Bay"],
    "Nipissing":  ["Ottawa-Gatineau", "Greater Toronto Area"],
    "Algonquin":  ["Ottawa-Gatineau", "Greater Toronto Area"],
}

STAGE_COLORS = {
    "forest":    "#1b7340",
    "primary":   "#2ca02c",
    "pulp":      "#9467bd",
    "secondary": "#ff7f0e",
    "market":    "#d62728",
}

fac_4326 = gdf_fac.to_crs("EPSG:4326")
fac_4326["fac_group"] = fac_4326["FACILITY_T"].map(FACILITY_TYPE_MAP).fillna("Other")
fac_4326["mill_size"] = fac_4326["FACILITY_T"].map({
    "Sawmill - Large": "Large", "Sawmill - Medium": "Medium", "Sawmill - Small": "Small",
}).fillna("")

# Spatial join facilities to ALL FMUs (not just study) for nearest-region logic
fac_all_join = gpd.sjoin(
    fac_wgs, gdf_fmu[["FMU_NAME","geometry"]].to_crs("EPSG:4269"),
    how="left", predicate="within"
)
fac_4326["host_fmu"] = fac_all_join["FMU_NAME"].values

# Which study region is each facility closest to?
def nearest_study_region(lat, lon):
    best_r, best_d = None, 1e9
    for r, (rlat, rlon) in region_coords.items():
        d = math.sqrt((lat - rlat)**2 + (lon - rlon)**2)
        if d < best_d:
            best_d = d
            best_r = r
    return best_r

fac_4326["nearest_study"] = fac_4326.apply(
    lambda row: nearest_study_region(row.geometry.y, row.geometry.x), axis=1
)

m4 = folium.Map(location=[48.5, -83.0], zoom_start=5, tiles=None)

folium.TileLayer(
    tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    attr="OpenStreetMap / CARTO", name="CartoDB Light", control=False,
).add_to(m4)
folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m4)
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri", name="Satellite",
).add_to(m4)

# ── STAGE 1: Forest Harvest Zones ────────────────────────────────────────────
bg4 = folium.FeatureGroup(name="Context: Other Ontario FMUs", show=True)
for _, row in gdf_all_wgs[~gdf_all_wgs["FMU_NAME"].isin(STUDY.keys())].iterrows():
    folium.GeoJson(
        row["geometry"].__geo_interface__,
        style_function=lambda _f: {
            "fillColor":"#e8e8e8","color":"#d0d0d0","weight":0.4,"fillOpacity":0.25
        },
    ).add_to(bg4)
bg4.add_to(m4)

s1 = folium.FeatureGroup(name="STAGE 1: Forest Harvest Zones", show=True)
for _, row in gdf_study_wgs.iterrows():
    r = row["model_r"]
    stock = initialStock[r]
    stock_frac = stock / max_stock
    fill_opacity = 0.35 + 0.45 * stock_frac
    mix = speciesMix[r]
    top3 = sorted(mix.items(), key=lambda x: -x[1])[:3]
    top3_str = ", ".join(f"{s} {int(v*100)}%" for s,v in top3 if v > 0)
    sc = siteClass[r]
    harv = stock * 0.01

    species_bars = "".join(
        f'<div style="display:inline-block;width:{max(int(v*120),1)}px;height:14px;'
        f'background:{SPECIES_COLORS[s]};margin:0" title="{s}: {int(v*100)}%"></div>'
        for s,v in mix.items() if v > 0
    )

    popup_html = f"""
    <div style="font-family:Arial;min-width:300px;font-size:11px">
      <h3 style="margin:0 0 6px;color:{STAGE_COLORS['forest']};
          border-bottom:3px solid {STAGE_COLORS['forest']};padding-bottom:4px">
        Stage 1: {r} -- Forest Resource</h3>
      <table style="border-collapse:collapse;width:100%">
        <tr><td><b>Standing timber</b></td><td>{stock:,} million m3</td></tr>
        <tr><td><b>Site class</b></td><td>{sc}</td></tr>
        <tr><td><b>Sustainable harvest</b></td><td>~{harv:,.0f} million m3/yr (1% of stock)</td></tr>
      </table>
      <h4 style="margin:8px 0 3px">Tree species in this forest</h4>
      <div style="border:1px solid #ccc;border-radius:4px;overflow:hidden;height:14px;width:100%">
        {species_bars}</div>
      <div style="font-size:10px;color:#666;margin-top:3px">{top3_str}</div>
      <p style="margin-top:8px;font-size:10px;color:#555;border-left:3px solid {STAGE_COLORS['forest']};
         padding-left:6px">
        <b>What happens here:</b> Trees are harvested as roundwood logs, then trucked
        to nearby sawmills and pulp mills for processing. The model limits harvest to
        1% of standing stock per year to ensure long-term sustainability.
      </p>
    </div>"""

    folium.GeoJson(
        row["geometry"].__geo_interface__,
        style_function=lambda _f, fo=fill_opacity: {
            "fillColor": STAGE_COLORS["forest"],
            "color": "#1a5c30", "weight": 2.2, "fillOpacity": fo,
        },
        highlight_function=lambda _f: {
            "fillOpacity": 0.8, "weight": 3.5, "color": "#000",
        },
        tooltip=folium.Tooltip(
            f"<b>FOREST: {r}</b><br>"
            f"Standing timber: {stock:,} M m3<br>"
            f"Harvest capacity: ~{harv:,.0f} M m3/yr<br>"
            f"Species: {top3_str}"
        ),
        popup=folium.Popup(popup_html, max_width=380),
    ).add_to(s1)

    # Region label
    lat, lon = region_coords[r]
    folium.Marker(
        location=[lat, lon],
        icon=folium.DivIcon(
            html=f'<div style="font-size:10px;font-weight:bold;color:white;'
                 f'background:{STAGE_COLORS["forest"]};padding:2px 6px;border-radius:4px;'
                 f'white-space:nowrap;text-align:center;border:1px solid #0a3d1f;'
                 f'box-shadow:0 1px 3px rgba(0,0,0,.3)">'
                 f'{r}<br><span style="font-size:8px;font-weight:normal">'
                 f'{stock:,} M m3</span></div>',
            icon_size=(130, 38), icon_anchor=(65, 19),
        ),
    ).add_to(s1)
s1.add_to(m4)

# ── STAGE 2: Primary Processing Mills ────────────────────────────────────────
s2_saw = folium.FeatureGroup(name="STAGE 2a: Sawmills (Lumber)", show=True)
s2_pulp = folium.FeatureGroup(name="STAGE 2b: Pulp & Paper Mills", show=True)

sawmills_4326 = fac_4326[fac_4326["fac_group"] == "Sawmill"]
pulpmills_4326 = fac_4326[fac_4326["fac_group"] == "Pulp/Paper"]

size_radius = {"Large": 9, "Medium": 6, "Small": 4}

for _, fr in sawmills_4326.iterrows():
    status = fr["OPERATING_"]
    if status != "Active":
        continue
    r = size_radius.get(fr["mill_size"], 6)
    popup_html = f"""
    <div style="font-family:Arial;min-width:260px;font-size:11px">
      <h4 style="margin:0 0 4px;color:{STAGE_COLORS['primary']};
          border-bottom:2px solid {STAGE_COLORS['primary']};padding-bottom:3px">
        Stage 2: {fr['FACILITY_C']}</h4>
      <table style="border-collapse:collapse;width:100%">
        <tr><td><b>Type</b></td><td>{fr['FACILITY_T']}</td></tr>
        <tr><td><b>Location</b></td><td>{fr['LOCATION']}</td></tr>
        <tr><td><b>FORBIOM product</b></td><td>Lumber (Primary tier)</td></tr>
        <tr><td><b>Model capacity</b></td><td>Up to 10 million m3/yr per region</td></tr>
        <tr><td><b>Yield factor</b></td><td>0.90 (90% of roundwood becomes lumber)</td></tr>
        <tr><td><b>Base price</b></td><td>$375/m3</td></tr>
      </table>
      <p style="margin-top:6px;font-size:10px;color:#555;border-left:3px solid {STAGE_COLORS['primary']};
         padding-left:6px">
        <b>Role in supply chain:</b> Receives roundwood logs from nearby forests,
        processes them into dimensional lumber. Some lumber is sold directly; some
        feeds secondary mills that produce CLT and Glulam.
      </p>
    </div>"""

    folium.CircleMarker(
        location=[fr.geometry.y, fr.geometry.x],
        radius=r, color="#1a7a1a", fill=True,
        fill_color=STAGE_COLORS["primary"], fill_opacity=0.85, weight=1.5,
        tooltip=folium.Tooltip(
            f"<b>SAWMILL: {fr['FACILITY_C'][:35]}</b><br>"
            f"{fr['FACILITY_T']} | {fr['LOCATION']}<br>"
            f"Produces: Lumber ($375/m3)"
        ),
        popup=folium.Popup(popup_html, max_width=320),
    ).add_to(s2_saw)

for _, fr in pulpmills_4326.iterrows():
    status = fr["OPERATING_"]
    if status != "Active":
        continue
    popup_html = f"""
    <div style="font-family:Arial;min-width:260px;font-size:11px">
      <h4 style="margin:0 0 4px;color:{STAGE_COLORS['pulp']};
          border-bottom:2px solid {STAGE_COLORS['pulp']};padding-bottom:3px">
        Stage 2: {fr['FACILITY_C']}</h4>
      <table style="border-collapse:collapse;width:100%">
        <tr><td><b>Type</b></td><td>{fr['FACILITY_T']}</td></tr>
        <tr><td><b>Location</b></td><td>{fr['LOCATION']}</td></tr>
        <tr><td><b>FORBIOM product</b></td><td>Pulpwood (Primary tier)</td></tr>
        <tr><td><b>Model capacity</b></td><td>Up to 10 million m3/yr per region</td></tr>
        <tr><td><b>Yield factor</b></td><td>0.98 (98% of roundwood becomes pulp)</td></tr>
        <tr><td><b>Base price</b></td><td>$75/m3</td></tr>
      </table>
      <p style="margin-top:6px;font-size:10px;color:#555;border-left:3px solid {STAGE_COLORS['pulp']};
         padding-left:6px">
        <b>Role in supply chain:</b> Converts roundwood into pulp and paper products.
        Lower value per m3 but higher yield. Carbon storage is minimal (0.07 tCO2/m3)
        compared to engineered wood products.
      </p>
    </div>"""

    folium.CircleMarker(
        location=[fr.geometry.y, fr.geometry.x],
        radius=10, color="#6a3d9a", fill=True,
        fill_color=STAGE_COLORS["pulp"], fill_opacity=0.85, weight=2,
        tooltip=folium.Tooltip(
            f"<b>PULP MILL: {fr['FACILITY_C'][:35]}</b><br>"
            f"{fr['LOCATION']}<br>"
            f"Produces: Pulpwood ($75/m3)"
        ),
        popup=folium.Popup(popup_html, max_width=320),
    ).add_to(s2_pulp)

s2_saw.add_to(m4)
s2_pulp.add_to(m4)

# ── Harvest flow lines: FMU centroids -> nearby primary mills (AntPath) ──────
s2_flows = folium.FeatureGroup(name="FLOW: Forest -> Primary Mills (harvest)", show=True)

for r_name, (rlat, rlon) in region_coords.items():
    nearby_saw = sawmills_4326[
        (sawmills_4326["nearest_study"] == r_name) &
        (sawmills_4326["OPERATING_"] == "Active")
    ]
    for _, fr in nearby_saw.head(5).iterrows():
        plugins.AntPath(
            locations=[[rlat, rlon], [fr.geometry.y, fr.geometry.x]],
            color=STAGE_COLORS["forest"], weight=2, opacity=0.6,
            delay=1200, dash_array=[12, 20],
            tooltip=folium.Tooltip(
                f"Roundwood: {r_name} forest -> {fr['FACILITY_C'][:30]}"
            ),
        ).add_to(s2_flows)

    nearby_pulp = pulpmills_4326[
        (pulpmills_4326["nearest_study"] == r_name) &
        (pulpmills_4326["OPERATING_"] == "Active")
    ]
    for _, fr in nearby_pulp.iterrows():
        plugins.AntPath(
            locations=[[rlat, rlon], [fr.geometry.y, fr.geometry.x]],
            color=STAGE_COLORS["pulp"], weight=2.5, opacity=0.7,
            delay=1000, dash_array=[10, 18],
            tooltip=folium.Tooltip(
                f"Roundwood: {r_name} forest -> {fr['FACILITY_C'][:30]} (pulp)"
            ),
        ).add_to(s2_flows)

s2_flows.add_to(m4)

# ── STAGE 3: Secondary Processing Mills ──────────────────────────────────────
s3 = folium.FeatureGroup(name="STAGE 3: Secondary Mills (CLT / Glulam)", show=True)

composite_4326 = fac_4326[fac_4326["fac_group"] == "Composite/Veneer"]

for _, fr in composite_4326.iterrows():
    status = fr["OPERATING_"]
    if status != "Active":
        continue

    popup_html = f"""
    <div style="font-family:Arial;min-width:280px;font-size:11px">
      <h4 style="margin:0 0 4px;color:{STAGE_COLORS['secondary']};
          border-bottom:2px solid {STAGE_COLORS['secondary']};padding-bottom:3px">
        Stage 3: {fr['FACILITY_C']}</h4>
      <table style="border-collapse:collapse;width:100%">
        <tr><td><b>Type</b></td><td>{fr['FACILITY_T']}</td></tr>
        <tr><td><b>Location</b></td><td>{fr['LOCATION']}</td></tr>
        <tr><td><b>FORBIOM products</b></td><td>CLT ($700/m3) + Glulam ($575/m3)</td></tr>
        <tr><td><b>Model capacity</b></td><td>1.0 million m3/yr each</td></tr>
        <tr><td><b>Lumber input</b></td><td>1.2 m3 lumber per m3 CLT; 1.1 per m3 Glulam</td></tr>
        <tr><td><b>Carbon storage</b></td><td>0.70 tCO2/m3 (highest of all products)</td></tr>
      </table>
      <p style="margin-top:6px;font-size:10px;color:#555;border-left:3px solid {STAGE_COLORS['secondary']};
         padding-left:6px">
        <b>Role in supply chain:</b> Takes lumber from sawmills and manufactures
        high-value engineered wood products (Cross-Laminated Timber and Glulam beams).
        These are the key products for the mass-timber construction market and have the
        highest carbon storage benefit.
      </p>
    </div>"""

    folium.RegularPolygonMarker(
        location=[fr.geometry.y, fr.geometry.x],
        number_of_sides=4, radius=10, rotation=45,
        color="#cc6600", fill=True,
        fill_color=STAGE_COLORS["secondary"], fill_opacity=0.9, weight=2,
        tooltip=folium.Tooltip(
            f"<b>SECONDARY MILL: {fr['FACILITY_C'][:35]}</b><br>"
            f"{fr['FACILITY_T']} | {fr['LOCATION']}<br>"
            f"Produces: CLT ($700/m3) + Glulam ($575/m3)"
        ),
        popup=folium.Popup(popup_html, max_width=340),
    ).add_to(s3)

s3.add_to(m4)

# ── Lumber -> Secondary mill flow lines ──────────────────────────────────────
s3_flows = folium.FeatureGroup(name="FLOW: Sawmills -> Secondary Mills (lumber input)", show=True)

for _, cfr in composite_4326[composite_4326["OPERATING_"] == "Active"].iterrows():
    clat, clon = cfr.geometry.y, cfr.geometry.x
    nearest_r = nearest_study_region(clat, clon)
    nearby_saws = sawmills_4326[
        (sawmills_4326["nearest_study"] == nearest_r) &
        (sawmills_4326["OPERATING_"] == "Active") &
        (sawmills_4326["mill_size"] == "Large")
    ]
    for _, sfr in nearby_saws.head(3).iterrows():
        plugins.AntPath(
            locations=[[sfr.geometry.y, sfr.geometry.x], [clat, clon]],
            color=STAGE_COLORS["secondary"], weight=2.5, opacity=0.7,
            delay=800, dash_array=[8, 16],
            tooltip=folium.Tooltip(
                f"Lumber: {sfr['FACILITY_C'][:25]} -> {cfr['FACILITY_C'][:25]} (CLT/Glulam)"
            ),
        ).add_to(s3_flows)

s3_flows.add_to(m4)

# ── STAGE 4: Market Demand Hubs ──────────────────────────────────────────────
s4 = folium.FeatureGroup(name="STAGE 4: Market Demand Hubs (conceptual)", show=True)

for hub_name, (hlat, hlon) in MARKET_HUBS.items():
    regions_feeding = [r for r, hubs in REGION_TO_HUBS.items() if hub_name in hubs]
    regions_str = ", ".join(regions_feeding) if regions_feeding else "various"

    popup_html = f"""
    <div style="font-family:Arial;min-width:280px;font-size:11px">
      <h4 style="margin:0 0 4px;color:{STAGE_COLORS['market']};
          border-bottom:2px solid {STAGE_COLORS['market']};padding-bottom:3px">
        Stage 4: {hub_name} -- Market Demand</h4>
      <table style="border-collapse:collapse;width:100%">
        <tr><td><b>Supplied by regions</b></td><td>{regions_str}</td></tr>
        <tr><td><b>Products consumed</b></td><td>Lumber, CLT, Glulam, Pulpwood</td></tr>
      </table>
      <div style="margin-top:8px;padding:6px;background:#fff5f5;border-radius:4px;
           border-left:3px solid {STAGE_COLORS['market']};font-size:10px;color:#666">
        <b>Note:</b> In the FORBIOM model, demand is represented as regional caps
        (maximum sales per region per product per year), not as specific city-level
        destinations. These hubs are shown here to illustrate where forest products
        are ultimately consumed -- primarily in Ontario's urban construction and
        industrial markets.
      </div>
    </div>"""

    folium.Marker(
        location=[hlat, hlon],
        icon=folium.Icon(color="red", icon="star", prefix="fa"),
        tooltip=folium.Tooltip(
            f"<b>MARKET: {hub_name}</b><br>"
            f"Demand for: Lumber, CLT, Glulam, Pulpwood<br>"
            f"<i>(Conceptual -- demand modeled as regional caps in FORBIOM)</i>"
        ),
        popup=folium.Popup(popup_html, max_width=340),
    ).add_to(s4)

    folium.CircleMarker(
        location=[hlat, hlon],
        radius=18, color=STAGE_COLORS["market"], fill=True,
        fill_color=STAGE_COLORS["market"], fill_opacity=0.15, weight=2,
        dash_array="6 4",
    ).add_to(s4)

s4.add_to(m4)

# ── Demand flow lines: regions/mills -> market hubs (dashed, conceptual) ─────
s4_flows = folium.FeatureGroup(name="FLOW: Products -> Markets (conceptual)", show=True)

for r_name, hub_list in REGION_TO_HUBS.items():
    rlat, rlon = region_coords[r_name]
    for hub_name in hub_list:
        hlat, hlon = MARKET_HUBS[hub_name]
        folium.PolyLine(
            locations=[[rlat, rlon], [hlat, hlon]],
            color=STAGE_COLORS["market"], weight=2, opacity=0.4,
            dash_array="8 8",
            tooltip=folium.Tooltip(
                f"Products: {r_name} -> {hub_name}<br>"
                f"<i>(Conceptual demand flow)</i>"
            ),
        ).add_to(s4_flows)

s4_flows.add_to(m4)

# ── Legend panel ─────────────────────────────────────────────────────────────
legend4 = f"""
<div style="position:fixed;bottom:20px;left:20px;z-index:1000;
     background:white;padding:16px 18px;border-radius:12px;
     box-shadow:0 4px 16px rgba(0,0,0,.35);font-family:Arial;font-size:11px;
     line-height:1.6;max-width:270px;max-height:85vh;overflow-y:auto">

  <b style="font-size:15px;color:#1a1a2e">From Forest to Market</b><br>
  <span style="font-size:9px;color:#888">FORBIOM Supply Chain -- 4 Stages</span>

  <hr style="margin:8px 0;border-color:#eee">

  <div style="display:flex;align-items:center;margin:4px 0">
    <div style="width:18px;height:18px;background:{STAGE_COLORS['forest']};
         border-radius:3px;margin-right:8px;flex-shrink:0"></div>
    <div><b>Stage 1:</b> Forest Harvest Zones<br>
    <span style="font-size:9px;color:#666">6 FMU regions, harvest &le; 1%/yr</span></div>
  </div>

  <div style="text-align:center;color:#888;font-size:16px;margin:2px 0">&#8595;</div>

  <div style="display:flex;align-items:center;margin:4px 0">
    <div style="width:18px;height:18px;background:{STAGE_COLORS['primary']};
         border-radius:50%;margin-right:8px;flex-shrink:0"></div>
    <div><b>Stage 2a:</b> Sawmills (77)<br>
    <span style="font-size:9px;color:#666">Roundwood -> Lumber ($375/m3)</span></div>
  </div>

  <div style="display:flex;align-items:center;margin:4px 0">
    <div style="width:18px;height:18px;background:{STAGE_COLORS['pulp']};
         border-radius:50%;margin-right:8px;flex-shrink:0"></div>
    <div><b>Stage 2b:</b> Pulp Mills (5)<br>
    <span style="font-size:9px;color:#666">Roundwood -> Pulpwood ($75/m3)</span></div>
  </div>

  <div style="text-align:center;color:#888;font-size:16px;margin:2px 0">&#8595;</div>

  <div style="display:flex;align-items:center;margin:4px 0">
    <div style="width:18px;height:18px;background:{STAGE_COLORS['secondary']};
         border-radius:3px;transform:rotate(45deg);margin-right:8px;flex-shrink:0"></div>
    <div><b>Stage 3:</b> Secondary Mills (9)<br>
    <span style="font-size:9px;color:#666">Lumber -> CLT ($700) + Glulam ($575)</span></div>
  </div>

  <div style="text-align:center;color:#888;font-size:16px;margin:2px 0">&#8595;</div>

  <div style="display:flex;align-items:center;margin:4px 0">
    <div style="width:18px;height:18px;color:{STAGE_COLORS['market']};
         font-size:16px;text-align:center;line-height:18px;margin-right:8px;
         flex-shrink:0">&#9733;</div>
    <div><b>Stage 4:</b> Market Hubs (5)<br>
    <span style="font-size:9px;color:#666">GTA, Ottawa, etc. (conceptual)</span></div>
  </div>

  <hr style="margin:8px 0;border-color:#eee">

  <b>Flow Lines</b><br>
  <div style="display:flex;align-items:center;margin:3px 0">
    <div style="width:30px;height:0;border-top:3px solid {STAGE_COLORS['forest']};
         margin-right:6px"></div>
    <span style="font-size:10px">Harvest (animated, modeled)</span>
  </div>
  <div style="display:flex;align-items:center;margin:3px 0">
    <div style="width:30px;height:0;border-top:3px solid {STAGE_COLORS['secondary']};
         margin-right:6px"></div>
    <span style="font-size:10px">Lumber -> CLT/Glulam (modeled)</span>
  </div>
  <div style="display:flex;align-items:center;margin:3px 0">
    <div style="width:30px;height:0;border-top:2px dashed {STAGE_COLORS['market']};
         margin-right:6px"></div>
    <span style="font-size:10px">To market (conceptual)</span>
  </div>

  <hr style="margin:8px 0;border-color:#eee">
  <small style="color:#999">Toggle each stage on/off using layer controls.<br>
  Solid flows = modeled in FORBIOM<br>
  Dashed flows = conceptual (demand as caps)</small>
</div>"""
m4.get_root().html.add_child(folium.Element(legend4))

# ── Title bar ────────────────────────────────────────────────────────────────
title4 = """
<div style="position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:1000;
     background:rgba(26,26,46,0.94);padding:12px 32px;border-radius:10px;
     font-family:Arial;text-align:center;box-shadow:0 3px 14px rgba(0,0,0,.35)">
  <span style="color:white;font-size:18px;font-weight:bold">
    FORBIOM &mdash; From Forest to Market</span><br>
  <span style="color:#ccc;font-size:11px">
    Ontario's Wood Product Supply Chain &bull;
    Forest &rarr; Sawmills &rarr; Engineered Wood &rarr; Construction Markets
  </span>
</div>"""
m4.get_root().html.add_child(folium.Element(title4))

# ── Key parameters panel ─────────────────────────────────────────────────────
params_html = """
<div style="position:fixed;top:80px;right:20px;z-index:1000;
     background:white;padding:14px 16px;border-radius:10px;
     box-shadow:0 3px 12px rgba(0,0,0,.3);font-family:Arial;font-size:11px;
     max-width:260px">
  <b style="font-size:13px;color:#1a1a2e">Key Model Parameters</b>
  <table style="margin-top:8px;font-size:10px;border-collapse:collapse;width:100%">
    <tr style="background:#f8f8f8"><td><b>Carbon price</b></td><td>$170/tCO2</td></tr>
    <tr><td><b>Harvest limit</b></td><td>&le; 1% of stock/yr</td></tr>
    <tr style="background:#f8f8f8"><td><b>Lumber price</b></td><td>$375/m3 (3%/yr growth)</td></tr>
    <tr><td><b>CLT price</b></td><td>$700/m3</td></tr>
    <tr style="background:#f8f8f8"><td><b>Glulam price</b></td><td>$575/m3</td></tr>
    <tr><td><b>Pulpwood price</b></td><td>$75/m3</td></tr>
    <tr style="background:#f8f8f8"><td><b>Transport cap</b></td><td>20 M m3/yr per arc</td></tr>
    <tr><td><b>Planning horizon</b></td><td>2020-2030 (11 years)</td></tr>
  </table>
  <div style="margin-top:8px;padding:6px;background:#f0fff0;border-radius:4px;
       border-left:3px solid #2ca02c;font-size:10px;color:#555">
    <b>Carbon benefit:</b> CLT and Glulam store 0.70 tCO2/m3 in buildings --
    far more than their processing emissions (0.15-0.17 tCO2/m3).
    This net storage is a key policy lever.
  </div>
</div>"""
m4.get_root().html.add_child(folium.Element(params_html))

folium.LayerControl(collapsed=False).add_to(m4)

path4 = os.path.join(OUT_DIR, "forbiom_explainer.html")
m4.save(path4)
print(f"  -> {path4}")

print("All 4 maps done!")
