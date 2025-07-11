import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import psycopg2
import time
import tracemalloc

# --- DÉMARRER LE MONITORING DE LA MÉMOIRE ---
tracemalloc.start()

# --- CONNEXION À LA BASE NEON ---
@st.cache_resource
def init_connection():
    return psycopg2.connect(
        dbname="neondb",
        user="neondb_owner",
        password="npg_GJ6XsHumk0Yz",
        host="ep-lucky-base-a22m3jwu-pooler.eu-central-1.aws.neon.tech",
        port=5432,
        sslmode="require"
    )

conn = init_connection()

# --- PARAMÈTRES GÉNÉRAUX ---
CHARGEMENT_MAX_SECONDES = 3
LIMIT_PAR_CHARGEMENT = 5
MEMORY_MAX_MB = 200  # Limite mémoire pour vider automatiquement le cache

st.set_page_config(layout="wide")
st.title("📊 XYZ Viewer – Données temporelles")

# --- INITIALISATION DE SESSION ---
if "all_dates" not in st.session_state:
    st.session_state.all_dates = []
if "loaded_ids" not in st.session_state:
    st.session_state.loaded_ids = set()
if "start_index" not in st.session_state:
    st.session_state.start_index = 0
if "play" not in st.session_state:
    st.session_state.play = False
if "slider_index" not in st.session_state:
    st.session_state.slider_index = 0

# --- CHARGER LES POINTS XYZ ---
@st.cache_data
def get_xyz():
    return pd.read_sql("SELECT id, x, y, z FROM xyz_points ORDER BY id", conn)

df_xyz = get_xyz()
n_points = len(df_xyz)

# --- RÉCUPÉRER LES MÉTADONNÉES DE DATE ---
@st.cache_data
def get_all_metadata():
    df = pd.read_sql("SELECT id, date FROM data_fibre ORDER BY date", conn)
    return df

df_meta = get_all_metadata()
total_dates = len(df_meta)

# --- FONCTION POUR CHARGER DES DONNÉES AVEC LIMIT ---
def charger_dates(depuis_index, direction="forward"):
    dates = []
    ids = []
    start_time = time.time()
    offset = 1 if direction == "forward" else -1
    index = depuis_index
    count = 0
    while (0 <= index < total_dates) and (time.time() - start_time < CHARGEMENT_MAX_SECONDES) and count < LIMIT_PAR_CHARGEMENT:
        row = df_meta.iloc[index]
        if row["id"] in st.session_state.loaded_ids:
            index += offset
            continue
        df_val = pd.read_sql("SELECT values FROM data_fibre WHERE id = %s", conn, params=[row["id"]])
        if not df_val.empty:
            vals = df_val["values"][0]
            if len(vals) == n_points:
                dates.append({"id": row["id"], "date": row["date"], "values": vals})
                st.session_state.loaded_ids.add(row["id"])
                count += 1
        index += offset
    return dates, index - offset

# --- PREMIER CHARGEMENT ---
if not st.session_state.all_dates:
    loaded, new_index = charger_dates(st.session_state.start_index, direction="forward")
    st.session_state.all_dates.extend(loaded)
    st.session_state.start_index = new_index

# --- AFFICHAGE SLIDER & CONTROLES ---
slider_labels = [entry["date"] for entry in st.session_state.all_dates]
st.session_state.slider_index = st.slider("📅 Sélectionnez une date", 0, len(slider_labels) - 1, st.session_state.slider_index, format="%s")
selected_entry = st.session_state.all_dates[st.session_state.slider_index]
st.markdown(f"### Date sélectionnée : {selected_entry['date']}")

col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    if st.button("⬅ Charger plus tôt"):
        loaded, new_index = charger_dates(st.session_state.start_index, direction="backward")
        if loaded:
            st.session_state.all_dates = loaded + st.session_state.all_dates
            st.session_state.start_index = new_index
        else:
            st.warning("🚫 Aucune date plus ancienne.")
with col2:
    if st.button("▶ Play" if not st.session_state.play else "⏸ Pause"):
        st.session_state.play = not st.session_state.play
with col3:
    if st.button("Charger plus tard ➡"):
        loaded, new_index = charger_dates(st.session_state.start_index, direction="forward")
        if loaded:
            st.session_state.all_dates += loaded
            st.session_state.start_index = new_index
        else:
            st.warning("🚫 Aucune date plus récente.")

# --- AFFICHAGE DU GRAPHIQUE ---
fig = go.Figure(data=[
    go.Scatter3d(
        x=df_xyz["x"],
        y=df_xyz["y"],
        z=df_xyz["z"],
        mode='markers',
        marker=dict(
            size=4,
            color=selected_entry["values"],
            colorscale="Turbo",
            cmin=0,
            cmax=10000,
            colorbar=dict(title="Valeur")
        ),
        hovertemplate="<b>X</b>: %{x:.2f}<br><b>Y</b>: %{y:.2f}<br><b>Z</b>: %{z:.2f}<br><b>Valeur</b>: %{marker.color:.2f}<extra></extra>"
    )
])
fig.update_layout(
    margin=dict(l=0, r=0, t=40, b=0),
    scene=dict(xaxis_title="X", yaxis_title="Y", zaxis_title="Z"),
)
st.plotly_chart(fig, use_container_width=True)

# --- ANIMATION SI PLAY ---
if st.session_state.play:
    time.sleep(1)
    if st.session_state.slider_index < len(st.session_state.all_dates) - 1:
        st.session_state.slider_index += 1
        st.rerun()
    else:
        st.session_state.play = False

# --- MONITORING MÉMOIRE & FLUIDITÉ ---
current, peak = tracemalloc.get_traced_memory()
st.markdown(f"#### 🧠 Mémoire utilisée : {current / 1024 / 1024:.2f} Mo (pic : {peak / 1024 / 1024:.2f} Mo)")
if current / 1024 / 1024 > MEMORY_MAX_MB:
    st.warning("⚠️ Cache saturé : vidage automatique.")
    st.cache_data.clear()
    st.rerun()

# --- DÉLAI DE CHARGEMENT INDICATIF ---
st.markdown(f"#### ⚡ Chargement limité à : {CHARGEMENT_MAX_SECONDES} secondes maximum")
