import streamlit as st
import pandas as pd
from textwrap import dedent
import os
from dotenv import load_dotenv
import pyodbc
import folium
from folium import Element
from streamlit_folium import st_folium

st.set_page_config(page_title="Geocercas y Zonas", page_icon="🗺️", layout="wide")

def get_db_connection():
    load_dotenv()

    server = os.getenv('DB_SERVER')
    database = os.getenv('DB_DATABASE')
    username = os.getenv('DB_USERNAME')
    password = os.getenv('DB_PASSWORD')
    driver = os.getenv('DB_DRIVER', "{ODBC Driver 17 for SQL Server}")

    conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}"
    return pyodbc.connect(conn_str)

def _coerce_latlng(df, lat_col="lat", lng_col="lng"):
    for c in [lat_col, lng_col]:
        df[c] = (
            df[c].astype(str)
            .str.replace(",", ".", regex=False)
            .str.replace(r"[^0-9\.\-]", "", regex=True)
        )
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=[lat_col, lng_col])

@st.cache_resource
def obtener_geocercas():
    q = dedent("""
        SELECT g.id_geofence,
               g.geofence_name,
               gc.lat,
               gc.lng
        FROM [dev_apprisa_delivery].[dbo].tbl_geofences AS g
        JOIN [dev_apprisa_delivery].[dbo].tbl_geofences_coordinates AS gc
          ON gc.geofence = g.id_geofence
    """)
    with get_db_connection() as conn:
        df = pd.read_sql(q, conn)
    df = df.rename(columns={"geofence_name": "name"})
    df = _coerce_latlng(df, "lat", "lng")
    return df

@st.cache_resource
def obtener_zonas():
    q = dedent("""
        SELECT z.zona_name,
               z.zona_color,
               zc.lat,
               zc.lng
        FROM [dev_apprisa_delivery].[dbo].tbl_zonas AS z
        JOIN [dev_apprisa_delivery].[dbo].tbl_zonas_coordinates AS zc
          ON z.id_zona = zc.zona
    """)
    with get_db_connection() as conn:
        df = pd.read_sql(q, conn)
    df = _coerce_latlng(df, "lat", "lng")
    return df

def sanitize_color(s, fallback="#3388ff"):
    if not isinstance(s, str):
        return fallback
    s = s.strip()
    if not s:
        return fallback
    if s.startswith("#") and len(s) in (4, 7):
        return s
    for sep in (",", ";"):
        if sep in s:
            try:
                r, g, b = [int(x) for x in s.split(sep)[:3]]
                return "#{:02x}{:02x}{:02x}".format(
                    max(0, min(255, r)),
                    max(0, min(255, g)),
                    max(0, min(255, b)),
                )
            except:
                break
    if len(s) in (3, 6):
        return "#" + s
    return fallback

def build_polygons(df, group_col):
    polys = []
    for key, g in df.groupby(group_col, sort=False):
        coords = list(zip(g["lat"].astype(float), g["lng"].astype(float)))
        item = {"name": key, "coords": coords}
        if "zona_color" in g.columns:
            item["color"] = sanitize_color(g["zona_color"].iloc[0])
        polys.append(item)
    return polys

st.title("🗺️ Mapa completo de Geocercas y Zonas")

df_geo = obtener_geocercas()
df_zon = obtener_zonas()

center_lat = df_geo["lat"].mean()
center_lng = df_geo["lng"].mean()

geocercas = build_polygons(df_geo, "name")
zonas = build_polygons(df_zon, "zona_name")

m = folium.Map(location=(center_lat, center_lng), zoom_start=12, control_scale=True)

style_css = """
<style>
.zona-label{background:rgba(255,255,255,.85);border:1px solid rgba(0,0,0,.35);padding:2px 6px;border-radius:6px;box-shadow:0 1px 2px rgba(0,0,0,.25);font-size:13px;font-weight:600;pointer-events:none;color:#000;}
</style>
"""
m.get_root().html.add_child(Element(style_css))

folium.plugins.Fullscreen(position="topleft", title="Pantalla completa", title_cancel="Salir de pantalla completa").add_to(m)

for p in geocercas:
    folium.PolyLine(locations=p["coords"], color="#111111", weight=4).add_to(m)

for p in zonas:
    color = p.get("color", "#3388ff")
    poly = folium.Polygon(locations=p["coords"], fill=True, fill_opacity=0.45, weight=2, color=color, fill_color=color).add_to(m)
    folium.Tooltip(f" {p['name']}", permanent=True, direction="center", class_name="zona-label", sticky=False, opacity=1).add_to(poly)

folium.LayerControl(collapsed=False).add_to(m)

st_folium(m, height=900, width=None, returned_objects=[])
