import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import psycopg2
import time
import tracemalloc

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

# --- Fonction : récupérer xyz (1 seule fois) ---
@st.cache_data
def load_xyz():
    return pd.read_sql("SELECT x, y, z FROM xyz_points ORDER BY id", conn)

# --- Fonction : charger dynamiquement des dates dans la limite de 3 secondes ---
def load_dates_dynamic(start_index, max_seconds=3.0):
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
        elapsed = time.time() - t_start
        if elapsed >= max_seconds:
            break
        i += 1
    return valid_data, i

# --- Mémoire : vider le cache si trop utilisé (avec tracemalloc) ---
def check_memory(max_mb=600):
    current, peak = tracemalloc.get_traced_memory()
    if (peak / 1024 / 1024) > max_mb:
        st.cache_data.clear()
        tracemalloc.reset_peak()

# --- Config Streamlit ---
st.set_page_config(layout="wide")
st.title("📊 XYZ Viewer – Dynamique avec pagination ≤ 3s")

# --- Initialisation du cache mémoire ---
tracemalloc.start()

# --- Variables session ---
if "date_index" not in st.session_state:
    st.session_state.date_index = 0
if "data_cache" not in st.session_state:
    st.session_state.data_cache = {}

# --- Charger XYZ une fois ---
df_xyz = load_xyz()
n_points = len(df_xyz)

# --- Bouton pour charger plus de dates ---
if st.button("⬇ Charger plus de dates (≤ 3s)"):
    new_data, new_index = load_dates_dynamic(st.session_state.date_index)
    st.session_state.data_cache.update(new_data)
    st.session_state.date_index = new_index
    check_memory()

# --- Afficher l'état actuel ---
dates_loaded = list(st.session_state.data_cache.keys())
if not dates_loaded:
    st.error("❌ Aucune date valide chargée en moins de 3s.")
    st.stop()

# --- Slider pour sélection de date ---
index = st.slider("📅 Sélectionner une date", 0, len(dates_loaded) - 1, 0)
selected_date = dates_loaded[index]
values = st.session_state.data_cache[selected_date]

# --- Vérification cohérence données ---
if len(values) != n_points:
    st.error(f"❌ Erreur : {len(values)} valeurs ≠ {n_points} XYZ")
    st.stop()

st.markdown(f"### Date sélectionnée : `{selected_date}`")
st.write("✅ Nombre de valeurs :", len(values))
st.write("✅ Nombre de points XYZ :", n_points)

# --- Affichage 3D ---
fig = go.Figure(data=[go.Scatter3d(
    x=df_xyz["x"], y=df_xyz["y"], z=df_xyz["z"],
    mode='markers',
    marker=dict(
        size=4,
        color=values,
        colorscale="Turbo",
        cmin=0,
        cmax=10000,
        colorbar=dict(title="Valeur")
    ),
    hovertemplate="<b>X</b>: %{x:.2f}<br><b>Y</b>: %{y:.2f}<br><b>Z</b>: %{z:.2f}<br><b>Valeur</b>: %{marker.color:.2f}<extra></extra>"
)])
fig.update_layout(
    margin=dict(l=0, r=0, t=40, b=0),
    scene=dict(xaxis_title="X", yaxis_title="Y", zaxis_title="Z")
)
st.plotly_chart(fig, use_container_width=True)

# --- Nettoyage mémoire ---
check_memory()
