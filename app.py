import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import psycopg2
import time

# --- Connexion Neon ---
conn = psycopg2.connect(
    dbname="neondb",
    user="neondb_owner",
    password="npg_GJ6XsHumk0Yz",
    host="ep-lucky-base-a22m3jwu-pooler.eu-central-1.aws.neon.tech",
    port=5432,
    sslmode="require"
)

# --- Fonction : récupérer tous les identifiants de date (triés décroissant) ---
@st.cache_data
def get_all_dates():
    df = pd.read_sql("SELECT id, date FROM data_fibre ORDER BY date DESC", conn)
    return df

# --- Fonction : récupérer xyz une seule fois ---
@st.cache_data
def load_xyz():
    return pd.read_sql("SELECT x, y, z FROM xyz_points ORDER BY id", conn)

# --- Fonction : chargement dynamique en 3s ---
def load_dates_dynamic(start_index, max_seconds=3.0, max_loaded_dates=50):
    df_all_dates = get_all_dates()
    df_xyz = load_xyz()
    n_points = len(df_xyz)

    valid_data = {}
    t_start = time.time()
    i = start_index

    while i < len(df_all_dates):
        id_, date_ = df_all_dates.iloc[i]
        query = "SELECT values FROM data_fibre WHERE id = %s"
        df = pd.read_sql(query, conn, params=[id_])
        if not df.empty:
            values = df["values"].iloc[0]
            if len(values) == n_points:
                valid_data[date_] = values

        if time.time() - t_start >= max_seconds or len(valid_data) >= max_loaded_dates:
            break
        i += 1

    return valid_data, i

# --- Page config ---
st.set_page_config(layout="wide")
st.title("📊 XYZ Viewer – Dynamique avec pagination ≤ 3s")

# --- Sessions ---
if "date_index" not in st.session_state:
    st.session_state.date_index = 0
if "data_cache" not in st.session_state:
    st.session_state.data_cache = {}

# --- Charger XYZ une seule fois ---
df_xyz = load_xyz()
n_points = len(df_xyz)

# --- Chargement initial (si cache vide) ---
if not st.session_state.data_cache:
    with st.spinner("Chargement initial des données..."):
        initial_data, new_index = load_dates_dynamic(0)
        st.session_state.data_cache.update(initial_data)
        st.session_state.date_index = new_index

# --- Bouton pour pagination (limité à 3s) ---
if st.button("⬇ Charger plus de dates (≤ 3s)"):
    new_data, new_index = load_dates_dynamic(st.session_state.date_index)
    st.session_state.data_cache.update(new_data)
    st.session_state.date_index = new_index

# --- Récupération des dates chargées ---
dates_loaded = list(st.session_state.data_cache.keys())
if not dates_loaded:
    st.error("❌ Aucune date valide chargée en moins de 3s.")
    st.stop()

# --- Slider de navigation ---
index = st.slider("📅 Sélectionner une date", 0, len(dates_loaded) - 1, 0)
selected_date = dates_loaded[index]
values = st.session_state.data_cache[selected_date]

# --- Vérification ---
if len(values) != n_points:
    st.error(f"❌ {len(values)} valeurs ≠ {n_points} XYZ")
    st.stop()

# --- Affichage ---
st.markdown(f"### Date sélectionnée : `{selected_date}`")
st.success(f"✅ {len(values)} valeurs associées aux {n_points} points XYZ")

fig = go.Figure(data=[go.Scatter3d(
    x=df_xyz["x"], y=df_xyz["y"], z=df_xyz["z"],
    mode='markers',
    marker=dict(
        size=3,
        color=values,
        colorscale="Turbo",
        cmin=0,
        cmax=10000,
        colorbar=dict(title="Valeur")
    ),
    hovertemplate="X: %{x:.2f}<br>Y: %{y:.2f}<br>Z: %{z:.2f}<br>Val: %{marker.color:.2f}<extra></extra>"
)])
fig.update_layout(
    margin=dict(l=0, r=0, t=40, b=0),
    scene=dict(xaxis_title="X", yaxis_title="Y", zaxis_title="Z")
)
st.plotly_chart(fig, use_container_width=True)
