import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import psycopg2
import time

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

# --- Chargement initial des métadonnées ---
df_xyz = pd.read_sql("SELECT x, y, z FROM xyz_points ORDER BY id", conn)
n_points = len(df_xyz)
df_meta = pd.read_sql("SELECT DISTINCT date FROM data_fibre ORDER BY date", conn)
total_dates = len(df_meta)

# --- Initialisation état ---
if "loaded_dates" not in st.session_state:
    st.session_state.loaded_dates = []
    st.session_state.loaded_ids = set()
    st.session_state.start_index = total_dates - 1
    st.session_state.direction = "forward"
    st.session_state.playing = False
    st.session_state.fps = 0.0
    st.session_state.fluidity_start = time.time()

# --- Paramètres ---
MAX_DATES_IN_RAM = 50
MAX_LOAD_SECONDS = 3

# --- Chargement dynamique ---
def charger_dates(depuis_index, direction="forward"):
    result = []
    offset = 1 if direction == "forward" else -1
    index = depuis_index
    start_time = time.time()

    while (0 <= index < total_dates) and (time.time() - start_time < MAX_LOAD_SECONDS):
        row = df_meta.iloc[index]
        date_str = str(row["date"])

        if date_str in st.session_state.loaded_ids:
            index += offset
            continue

        df_val = pd.read_sql("SELECT values FROM data_fibre WHERE date = %s", conn, params=[row["date"]])
        if not df_val.empty:
            values = df_val["values"][0]
            if len(values) == n_points:
                result.append({"date": row["date"], "values": values})
                st.session_state.loaded_ids.add(date_str)

        index += offset

    return result[::-1] if direction == "backward" else result, index - offset

# --- Chargement initial si nécessaire ---
if not st.session_state.loaded_dates:
    st.info("⏳ Chargement initial...")
    initial_data, new_index = charger_dates(st.session_state.start_index, "backward")
    st.session_state.loaded_dates = initial_data
    st.session_state.start_index = new_index
    st.success(f"✅ {len(initial_data)} dates chargées.")

# --- En-tête ---
st.title("📊 Visualisation XYZ – animation dynamique")
st.caption("Navigation fluide via slider interactif et pagination intelligente")

# --- Contrôles chargement ---
col1, col2, col3 = st.columns([1, 4, 1])

with col1:
    if st.button("⬅ Charger avant"):
        data, new_index = charger_dates(st.session_state.start_index, "backward")
        if not data:
            st.warning("🔚 Aucune date plus ancienne.")
        else:
            new_ids = {str(d["date"]) for d in data}
            st.session_state.loaded_dates = data + [
                d for d in st.session_state.loaded_dates if str(d["date"]) not in new_ids
            ]
            st.session_state.start_index = new_index

with col3:
    if st.button("➡ Charger après"):
        last_loaded = st.session_state.loaded_dates[-1]["date"]
        last_index = df_meta[df_meta["date"] == last_loaded].index[0]
        data, new_index = charger_dates(last_index + 1, "forward")
        if not data:
            st.warning("🔚 Aucune date plus récente.")
        else:
            new_ids = {str(d["date"]) for d in data}
            st.session_state.loaded_dates += [
                d for d in data if str(d["date"]) not in st.session_state.loaded_ids
            ]

# --- Nettoyage mémoire ---
if len(st.session_state.loaded_dates) > MAX_DATES_IN_RAM:
    surplus = len(st.session_state.loaded_dates) - MAX_DATES_IN_RAM
    st.session_state.loaded_dates = st.session_state.loaded_dates[surplus:]
    st.session_state.loaded_ids = set(str(d["date"]) for d in st.session_state.loaded_dates)
    st.info("♻ Cache RAM réduit automatiquement.")

# --- FPS ---
elapsed = time.time() - st.session_state.fluidity_start
if elapsed > 0:
    st.session_state.fps = 1 / elapsed
st.session_state.fluidity_start = time.time()
st.metric("⚡ Fluidité estimée", f"{st.session_state.fps:.2f} FPS")

# --- PLAY/PAUSE ---
colA, _ = st.columns([1, 4])
with colA:
    if st.button("▶ Play" if not st.session_state.playing else "⏸ Pause"):
        st.session_state.playing = not st.session_state.playing

# --- Slider avec dates visibles ---
date_labels = [d["date"].strftime("%Y-%m-%d %H:%M:%S") for d in st.session_state.loaded_dates]
selected_date_str = st.select_slider("📅 Sélectionnez une date", options=date_labels, value=date_labels[0])
selected_index = date_labels.index(selected_date_str)
selected_values = st.session_state.loaded_dates[selected_index]["values"]

# --- Graphique 3D avec colorbar ---
fig = go.Figure(data=[go.Scatter3d(
    x=df_xyz["x"], y=df_xyz["y"], z=df_xyz["z"],
    mode='markers',
    marker=dict(
        size=4,
        color=selected_values,
        colorscale="Viridis",
        cmin=0,
        cmax=10000,
        colorbar=dict(title="Valeur")  # Légende des couleurs
    ),
    hovertemplate="<b>X</b>: %{x:.2f}<br><b>Y</b>: %{y:.2f}<br><b>Z</b>: %{z:.2f}<br><b>Valeur</b>: %{marker.color:.2f}<extra></extra>"
)])
fig.update_layout(
    margin=dict(l=0, r=0, t=30, b=0),
    scene=dict(xaxis_title="X", yaxis_title="Y", zaxis_title="Z"),
    title=f"Date sélectionnée : {selected_date_str}"
)
st.plotly_chart(fig, use_container_width=True)

# --- Animation automatique ---
if st.session_state.playing:
    next_index = (selected_index + 1) % len(st.session_state.loaded_dates)
    time.sleep(0.5)
    st.experimental_rerun()
