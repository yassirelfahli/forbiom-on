import geopandas as gpd
import folium
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

SHP = r"C:\Users\dell\Downloads\FORMGMT_extracted\LIO-2025-12-11\FOREST_MANAGEMENT_UNIT.shp"
OUT_DIR = r"C:\Users\dell\OneDrive\Bureau\Rasoul"

gdf = gpd.read_file(SHP)
gdf["AREA_KM2"] = (gdf["SYS_AREA"] / 1e6).round(0).astype(int)

STUDY_REGIONS = [
    "Trout Lake Forest",
    "Abitibi River Forest",
    "Algoma Forest",
    "Kenora Forest",
    "Nipissing Forest",
    "Algonquin Park Forest",
]

STUDY_COLORS = {
    "Trout Lake Forest":      "#e41a1c",
    "Abitibi River Forest":   "#ff7f00",
    "Algoma Forest":          "#4daf4a",
    "Kenora Forest":          "#984ea3",
    "Nipissing Forest":       "#377eb8",
    "Algonquin Park Forest":  "#a65628",
}

gdf["is_study"] = gdf["FMU_NAME"].isin(STUDY_REGIONS)

# ── reproject to WGS84 for Folium ────────────────────────────────────────────
gdf_wgs = gdf.to_crs("EPSG:4326")
centre_proj = gdf_wgs[gdf_wgs["is_study"]].geometry.to_crs("EPSG:3347").centroid
centre_wgs = gpd.GeoSeries(centre_proj, crs="EPSG:3347").to_crs("EPSG:4326")
centre = [centre_wgs.y.mean(), centre_wgs.x.mean()]

# ══════════════════════════════════════════════════════════════════════════════
#  1. INTERACTIVE FOLIUM MAP
# ══════════════════════════════════════════════════════════════════════════════
m = folium.Map(location=centre, zoom_start=5, tiles=None)

folium.TileLayer(
    tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    attr="OpenStreetMap contributors / CARTO",
    name="CartoDB Light",
    control=False,
).add_to(m)
folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri",
    name="Satellite",
).add_to(m)

# Background FMUs (muted)
bg_group = folium.FeatureGroup(name="Other FMUs", show=True)
for _, row in gdf_wgs[~gdf_wgs["is_study"]].iterrows():
    popup_html = f"""
    <div style="font-family:Arial;min-width:200px">
      <h4 style="margin:0 0 6px;color:#777">{row['FMU_NAME']}</h4>
      <table style="font-size:12px">
        <tr><td><b>Code</b></td><td>{row['FMU_CODE']}</td></tr>
        <tr><td><b>Region</b></td><td>{row['REGION']}</td></tr>
        <tr><td><b>District</b></td><td>{row['DISTRICT']}</td></tr>
        <tr><td><b>Area</b></td><td>{row['AREA_KM2']:,} km2</td></tr>
      </table>
    </div>"""
    folium.GeoJson(
        row["geometry"].__geo_interface__,
        style_function=lambda _f: {
            "fillColor": "#d0d0d0",
            "color": "#bbb",
            "weight": 0.8,
            "fillOpacity": 0.35,
        },
        highlight_function=lambda _f: {
            "fillOpacity": 0.55,
            "weight": 1.5,
            "color": "#666",
        },
        tooltip=folium.Tooltip(row["FMU_NAME"]),
        popup=folium.Popup(popup_html, max_width=260),
    ).add_to(bg_group)
bg_group.add_to(m)

# Study region FMUs (highlighted)
study_group = folium.FeatureGroup(name="Study Regions", show=True)
for _, row in gdf_wgs[gdf_wgs["is_study"]].iterrows():
    color = STUDY_COLORS[row["FMU_NAME"]]
    popup_html = f"""
    <div style="font-family:Arial;min-width:240px">
      <h4 style="margin:0 0 6px;color:{color}">* {row['FMU_NAME']}</h4>
      <table style="font-size:12px;border-collapse:collapse;width:100%">
        <tr><td><b>Code</b></td><td>{row['FMU_CODE']}</td></tr>
        <tr><td><b>Region</b></td><td>{row['REGION']}</td></tr>
        <tr><td><b>District</b></td><td>{row['DISTRICT']}</td></tr>
        <tr><td><b>Licensee</b></td><td>{row['LIC_NAME']}</td></tr>
        <tr><td><b>Area</b></td><td>{row['AREA_KM2']:,} km2</td></tr>
        <tr><td><b>Licence #</b></td><td>{row['LIC_NUM']}</td></tr>
        <tr><td><b>Start year</b></td><td>{row['START_YEAR']}</td></tr>
        <tr><td><b>End year</b></td><td>{row['END_YEAR']}</td></tr>
      </table>
    </div>"""
    folium.GeoJson(
        row["geometry"].__geo_interface__,
        style_function=lambda _f, c=color: {
            "fillColor": c,
            "color": "#222",
            "weight": 2.5,
            "fillOpacity": 0.7,
        },
        highlight_function=lambda _f, c=color: {
            "fillColor": c,
            "fillOpacity": 0.9,
            "weight": 3.5,
            "color": "#000",
        },
        tooltip=folium.Tooltip(
            f"<b>STUDY REGION:</b> {row['FMU_NAME']}",
            sticky=True,
        ),
        popup=folium.Popup(popup_html, max_width=300),
    ).add_to(study_group)

    # Bold label for study regions
    c_proj = gpd.GeoSeries([row["geometry"]], crs="EPSG:4326").to_crs("EPSG:3347").centroid.to_crs("EPSG:4326")
    cy, cx = c_proj.y.values[0], c_proj.x.values[0]
    short = row["FMU_NAME"].replace(" Forest", "")
    folium.Marker(
        location=[cy, cx],
        icon=folium.DivIcon(
            html=f'<div style="font-size:10px;font-weight:bold;color:{color};'
                 f'white-space:nowrap;text-shadow:0 0 4px #fff, 0 0 4px #fff, 0 0 4px #fff">'
                 f'{short}</div>',
            icon_size=(140, 22),
            icon_anchor=(70, 11),
        ),
    ).add_to(study_group)

study_group.add_to(m)

# Legend
legend_items = "".join(
    f'<span style="background:{c};display:inline-block;width:14px;height:14px;'
    f'margin-right:6px;border-radius:2px;border:1px solid #555"></span>'
    f'{name.replace(" Forest","")}<br>'
    for name, c in STUDY_COLORS.items()
)
legend_html = f"""
<div style="position:fixed;bottom:30px;left:30px;z-index:1000;
     background:white;padding:14px 18px;border-radius:8px;
     box-shadow:0 2px 10px rgba(0,0,0,.35);font-family:Arial;font-size:13px;
     line-height:1.8">
  <b style="font-size:15px">Study Regions</b><br><br>
  {legend_items}
  <br>
  <span style="background:#d0d0d0;display:inline-block;width:14px;height:14px;
        margin-right:6px;border-radius:2px;border:1px solid #bbb"></span>
  <span style="color:#888">Other FMUs</span><br>
  <br><small style="color:#888">Click any FMU for details</small>
</div>"""
m.get_root().html.add_child(folium.Element(legend_html))

folium.LayerControl(collapsed=False).add_to(m)

interactive_path = os.path.join(OUT_DIR, "ontario_fmu_interactive.html")
m.save(interactive_path)
print(f"[1/2] Interactive map saved -> {interactive_path}")

# ══════════════════════════════════════════════════════════════════════════════
#  2. STATIC MATPLOTLIB MAP  (publication-quality)
# ══════════════════════════════════════════════════════════════════════════════
gdf_proj = gdf.to_crs("EPSG:3347")

fig, ax = plt.subplots(1, 1, figsize=(16, 13))
fig.patch.set_facecolor("#f5f7fa")
ax.set_facecolor("#dce6f0")

# Background FMUs: muted grey
gdf_proj[~gdf_proj["is_study"]].plot(
    ax=ax, color="#ccd5de", edgecolor="white", linewidth=0.6, alpha=0.7
)

# Study regions: vivid colours with thick dark borders
for _, row in gdf_proj[gdf_proj["is_study"]].iterrows():
    color = STUDY_COLORS[row["FMU_NAME"]]
    gdf_proj[gdf_proj.index == _].plot(
        ax=ax, color=color, edgecolor="#222", linewidth=2.2, alpha=0.85
    )

# Label ALL FMUs (study = bold + coloured, others = subtle)
for _, row in gdf_proj.iterrows():
    c = row["geometry"].centroid
    short = row["FMU_NAME"].replace(" Forest", "")
    if row["is_study"]:
        ax.annotate(
            short,
            xy=(c.x, c.y),
            ha="center", va="center",
            fontsize=7.5, color="white",
            fontweight="bold",
            bbox=dict(
                boxstyle="round,pad=0.25",
                fc=STUDY_COLORS[row["FMU_NAME"]],
                ec="#222", lw=0.8, alpha=0.9,
            ),
        )
    else:
        ax.annotate(
            short,
            xy=(c.x, c.y),
            ha="center", va="center",
            fontsize=4.5, color="#666",
            fontstyle="italic",
        )

# Legend
patches = [
    mpatches.Patch(
        facecolor=STUDY_COLORS[name],
        edgecolor="#222", linewidth=1.2,
        label=name.replace(" Forest", ""),
    )
    for name in STUDY_REGIONS
]
patches.append(mpatches.Patch(facecolor="#ccd5de", edgecolor="#bbb", label="Other FMUs"))

legend = ax.legend(
    handles=patches,
    title="Study Regions",
    loc="lower right",
    framealpha=0.95,
    fontsize=10,
    title_fontsize=12,
    edgecolor="#ccc",
    fancybox=True,
    shadow=True,
)

ax.set_title(
    "Ontario Forest Management Units\nStudy Regions Highlighted",
    fontsize=18, fontweight="bold", pad=16, color="#1a1a2e",
)
ax.set_axis_off()

ax.annotate(
    "N", xy=(0.97, 0.96), xycoords="axes fraction",
    fontsize=16, ha="center", va="center", fontweight="bold", color="#333",
)
ax.annotate(
    "|", xy=(0.97, 0.935), xycoords="axes fraction",
    fontsize=14, ha="center", va="center", color="#333",
)
ax.annotate(
    "V", xy=(0.97, 0.975), xycoords="axes fraction",
    fontsize=10, ha="center", va="center", fontweight="bold", color="#333",
    rotation=180,
)

fig.text(
    0.01, 0.01,
    "Source: Ontario Land Information Office (LIO), 2025",
    fontsize=8, color="#666",
)

static_path = os.path.join(OUT_DIR, "ontario_fmu_static.png")
plt.tight_layout()
plt.savefig(static_path, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()
print(f"[2/2] Static map saved -> {static_path}")
print("Done!")
