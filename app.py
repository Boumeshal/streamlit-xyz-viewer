import streamlit as st
import pandas as pd
import psycopg2
import json
from collections import OrderedDict

# Connexion DB
@st.cache_resource
def get_conn():
    return psycopg2.connect(
        dbname="neondb",
        user="neondb_owner",
        password="npg_GJ6XsHumk0Yz",
        host="ep-lucky-base-a22m3jwu-pooler.eu-central-1.aws.neon.tech",
        port=5432,
        sslmode="require"
    )

conn = get_conn()

# Récupère XYZ
df_xyz = pd.read_sql("SELECT x, y, z FROM xyz_points ORDER BY id", conn)
n_points = len(df_xyz)

# Récupère toutes les dates dispo
df_dates = pd.read_sql("SELECT date FROM data_fibre ORDER BY date", conn)
all_dates = df_dates["date"].tolist()

# Initialisation d'un cache limité (10 dernières dates)
CACHE_LIMIT = 10
value_cache = OrderedDict()

def get_values(date):
    if date in value_cache:
        value_cache.move_to_end(date)  # Marquer comme récemment utilisé
        return value_cache[date]

    # Sinon, charger depuis DB
    query = "SELECT values FROM data_fibre WHERE date = %s"
    df = pd.read_sql(query, conn, params=[date])

    if len(df) == 0:
        return []

    vals = df["values"][0]
    if isinstance(vals, str):
        try:
            vals = json.loads(vals)
        except:
            return []

    # Mise en cache
    if isinstance(vals, list) and len(vals) == n_points:
        value_cache[date] = vals
        if len(value_cache) > CACHE_LIMIT:
            value_cache.popitem(last=False)  # Supprimer l’entrée la plus ancienne
        return vals
    return []

# Interface
st.title("XYZ Viewer optimisé")
selected_date = st.selectbox("📅 Choisissez une date", all_dates)

values = get_values(selected_date)

# Débogage
st.write(f"🔢 Valeurs chargées : {len(values)} / XYZ : {n_points}")
if len(values) != n_points:
    st.error("Erreur : Taille des valeurs ne correspond pas aux XYZ.")
    st.stop()

# Affichage Plotly
import plotly.graph_objects as go

fig = go.Figure(data=[
    go.Scatter3d(
        x=df_xyz["x"], y=df_xyz["y"], z=df_xyz["z"],
        mode="markers",
        marker=dict(
            size=3,
            color=values,
            colorscale="Viridis",
            opacity=0.8,
            cmin=0,
            cmax=10000
        ),
        hovertemplate="X: %{x:.2f}<br>Y: %{y:.2f}<br>Z: %{z:.2f}<br>Valeur: %{marker.color:.2f}<extra></extra>"
    )
])
fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
st.plotly_chart(fig, use_container_width=True)
