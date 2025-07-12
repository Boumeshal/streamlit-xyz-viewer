import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import psycopg2
import time
import sys

# --- Connexion Neon ---
@st.cache_resource
def get_connection():
    return psycopg2.connect(
        dbname="neondb",
        user="neondb_owner",
        password="npg_GJ6XsHumk0Yz",
        host="ep-lucky-base-a22m3jwu-pooler.eu-central-1.aws.neon.tech",
        port=5432,
        sslmode="require"
    )

conn = get_connection()

# --- Préchargement metadata ---
df_xyz = pd.read_sql("SELECT x, y, z FROM xyz_points ORDER BY id", conn)
n_points = len(df_xyz)

df_meta = pd.read_sql("SELECT DISTINCT date FROM data_fibre ORDER BY date", conn)
total_dates = len(df_meta)

# --- PARAMS ---
CHARGEMENT_MAX_SECONDES = 3
LIMIT_PAR_CHARGEMENT = 10

# --- Initialisation ---
if "loaded_dates" not in st.session_state:
    st.session_state.loaded_dates = []
    st.session_state.loaded_ids = set()
    st.session_state.start_index = total_dates - 1
    st.session_state.direction = "forward"
    st.session_state.playing = False
    st.session_state.fps = 0.0

# --- Charger données par morceaux ---
def charger_dates(depuis_index, direction="forward"):
    dates = []
    start_time = time.time()
    offset = 1 if direction == "forward" else -1
    index = depuis_index
    count = 0
    while (0 <= index < total_dates) and (time.time() - start_time < CHARGEMENT_MAX_SECONDES) and count < LIMIT_PAR_CHARGEMENT:
        row = df_meta.iloc[index]
        if row["date"] in st.session_state.loaded_ids:
            index += offset
            continue
        df_val = pd.read_sql("SELECT values FROM data_fibre WHERE date = %s", conn, params=[row["date"]])
        if not df_val.empty:
            vals = df_val["values"][0]
            if len(vals) == n_points:
                dates.append({"date": row["date"], "values": vals})
                st.session_state.loaded_ids.add(row["date"])
                count += 1
        index += offset
    return dates, index - offset

# --- Charger initialement ---
if not st.session_state.loaded_dates:
    st.info("⏳ Chargement initial en cours...")
    initial_data, new_index = charger_dates(st.session_state.start_index, direction="backward")
    st.session_state.loaded_dates = initial_data[::-1]
    st.session_state.start_index = new_index
    st.success(f"✅ {len(initial_data)} dates chargées.")

# --- TITRE ---
st.title("📊 Visualisation XYZ dynamique (Neon + Streamlit)")
st.caption("Défilement fluide, chargement intelligent, slider interactif, éviction automatique RAM")

# --- BOUTONS CHARGEMENT ---
col1, col2, col3 = st.columns([1, 4, 1])

with col1:
    if st.button("⬅ Charger avant"):
        new_data, new_index = charger_dates(st.session_state.start_index, direction="backward")
        if not new_data:
            st.warning("🚫 Aucune date précédente.")
        else:
            st.session_state.loaded_dates = new_data[::-1] + st.session_state.loaded_dates
            st.session_state.start_index = new_index

with col3:
    if st.button("➡ Charger après"):
        last_index = df_meta[df_meta["date"] == st.session_state.loaded_dates[-1]["date"]].index[0]
        new_data, new_index = charger_dates(last_index + 1, direction="forward")
        if not new_data:
            st.warning("🚫 Aucune nouvelle date après.")
        else:
            st.session_state.loaded_dates += new_data

# --- SLIDER ---
date_labels = [str(d["date"]) for d in st.session_state.loaded_dates]
slider_index = st.slider("📅 Sélectionner une date", 0, len(date_labels) - 1, 0, format="%d")
selected_date = date_labels[slider_index]
z_vals = st.session_state.loaded_dates[slider_index]["values"]

# --- AFFICHAGE PLOTLY ---
fig = go.Figure(data=[go.Scatter3d(
    x=df_xyz["x"], y=df_xyz["y"], z=df_xyz["z"],
    mode='markers',
    marker=dict(size=4, color=z_vals, colorscale="Viridis", cmin=0, cmax=10000, opacity=0.85),
    hovertemplate="<b>X</b>: %{x:.2f}<br><b>Y</b>: %{y:.2f}<br><b>Z</b>: %{z:.2f}<br><b>Valeur</b>: %{marker.color:.2f}<extra></extra>"
)])
fig.update_layout(
    margin=dict(l=0, r=0, t=40, b=0),
    scene=dict(xaxis_title="X", yaxis_title="Y", zaxis_title="Z"),
    title=f"🗓 {selected_date}"
)
st.plotly_chart(fig, use_container_width=True)

# --- FLUIDITÉ ---
if "fluidity_start" not in st.session_state:
    st.session_state.fluidity_start = time.time()

elapsed = time.time() - st.session_state.fluidity_start
if elapsed > 0:
    st.session_state.fps = 1 / elapsed
st.session_state.fluidity_start = time.time()

st.metric("⚡ Fluidité estimée (FPS)", f"{st.session_state.fps:.2f}")

# --- AUTO-VIDAGE DU CACHE ---
MAX_CACHE = 200
if len(st.session_state.loaded_dates) > MAX_CACHE:
    st.warning("♻ Mémoire saturée : nettoyage automatique")
    surplus = len(st.session_state.loaded_dates) - MAX_CACHE
    st.session_state.loaded_dates = st.session_state.loaded_dates[surplus:]
    st.session_state.loaded_ids = set([d["date"] for d in st.session_state.loaded_dates])

# --- PLAY/PAUSE ---
play_col, _ = st.columns([1, 4])
with play_col:
    if st.button("▶ Play" if not st.session_state.playing else "⏸ Pause"):
        st.session_state.playing = not st.session_state.playing

# --- ANIMATION ---
if st.session_state.playing:
    next_index = (slider_index + 1) % len(st.session_state.loaded_dates)
    time.sleep(0.5)
    st.experimental_rerun()
