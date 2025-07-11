import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go
import time

# --- PARAMÈTRES NEON ---
DB_CONFIG = {
    "dbname": "neondb",
    "user": "neondb_owner",
    "password": "npg_GJ6XsHumk0Yz",
    "host": "ep-lucky-base-a22m3jwu-pooler.eu-central-1.aws.neon.tech",
    "port": 5432,
    "sslmode": "require"
}

# --- PARAMÈTRES VISU ---
COLOR_MIN = 0
COLOR_MAX = 10000
MARKER_SIZE = 4
FONT_SIZE = 14

# --- FONCTION POUR CHARGER LES DATES DISPONIBLES ---
@st.cache_data(ttl=10)  # Met en cache pendant 10 secondes
def get_available_dates():
    with psycopg2.connect(**DB_CONFIG) as conn:
        df = pd.read_sql("SELECT date FROM data_fibre ORDER BY date", conn)
    return df["date"].tolist()

# --- FONCTION POUR CHARGER LES XYZ ---
@st.cache_data
def get_xyz_points():
    with psycopg2.connect(**DB_CONFIG) as conn:
        df = pd.read_sql("SELECT x, y, z FROM xyz_points ORDER BY id", conn)
    return df

# --- FONCTION POUR RÉCUPÉRER LES VALEURS À UNE DATE ---
def get_values_for_date(selected_date):
    with psycopg2.connect(**DB_CONFIG) as conn:
        query = "SELECT values FROM data_fibre WHERE date = %s"
        df = pd.read_sql(query, conn, params=[selected_date])
    return df.iloc[0]["values"] if not df.empty else []

# --- INTERFACE STREAMLIT ---
st.set_page_config(layout="wide")
st.title("XYZ Data – Colorisation dynamique par données temporelles")

xyz = get_xyz_points()
dates = get_available_dates()

# Slider pour choisir la date
selected_index = st.slider("Choisissez une date", 0, len(dates)-1, step=1, format="%d", label_visibility="collapsed")
selected_date = dates[selected_index]
st.markdown(f"### Date sélectionnée : {selected_date}")

# Requête pour la date choisie
values = get_values_for_date(selected_date)

# Vérifie cohérence taille
if len(values) != len(xyz):
    st.error("Erreur : Nombre de valeurs ne correspond pas au nombre de points XYZ.")
else:
    # Scatter 3D Plotly
    fig = go.Figure(data=[
        go.Scatter3d(
            x=xyz["x"], y=xyz["y"], z=xyz["z"],
            mode="markers",
            marker=dict(
                size=MARKER_SIZE,
                color=values,
                colorscale="Bluered",
                cmin=COLOR_MIN,
                cmax=COLOR_MAX,
                opacity=0.85,
                colorbar=dict(title="Valeur")
            ),
            hovertemplate="<b>X</b>: %{x:.2f}<br><b>Y</b>: %{y:.2f}<br><b>Z</b>: %{z:.2f}<br><b>Valeur</b>: %{marker.color:.2f}<extra></extra>"
        )
    ])
    fig.update_layout(
        scene=dict(
            xaxis_title="X", yaxis_title="Y", zaxis_title="Z"
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        template="simple_white"
    )
    st.plotly_chart(fig, use_container_width=True)
