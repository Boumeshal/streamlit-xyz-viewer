import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import psycopg2
import time
import psutil

# --- Paramètres de connexion à Neon ---
conn = psycopg2.connect(
    dbname="neondb",
    user="neondb_owner",
    password="npg_GJ6XsHumk0Yz",
    host="ep-lucky-base-a22m3jwu-pooler.eu-central-1.aws.neon.tech",
    port=5432,
    sslmode="require"
)

# --- Surveillance RAM ---
def memory_saturation_detected(threshold_percent=90):
    mem = psutil.virtual_memory()
    used_percent = 100 * (mem.total - mem.available) / mem.total
    return used_percent > threshold_percent

if memory_saturation_detected():
    st.cache_data.clear()
    st.toast("🧹 Cache vidé automatiquement pour préserver la fluidité.")

# --- Cache le chargement de XYZ ---
@st.cache_data
def load_xyz():
    return pd.read_sql("SELECT x, y, z FROM xyz_points ORDER BY id", conn)

df_xyz = load_xyz()
n_points = len(df_xyz)

# --- Liste des dates triées ---
@st.cache_data
def get_all_dates():
    df = pd.read_sql("SELECT id, date, values FROM data_fibre ORDER BY date", conn)
    return df

df_data = get_all_dates()

# --- Préchargement intelligent ≤ 3 secondes ---
@st.cache_data
def preload_valid_dates(max_duration=3.0, start_index=0):
    valid = []
    start = time.time()
    for i in range(start_index, len(df_data)):
        row = df_data.iloc[i]
        if time.time() - start > max_duration:
            break
        if isinstance(row["values"], list) and len(row["values"]) == n_points:
            valid.append(row)
    return valid, i + 1  # nouvelle position pour pagination

# --- Initialisation session ---
if "valid_rows" not in st.session_state:
    st.session_state.valid_rows, st.session_state.next_idx = preload_valid_dates()

# --- Page ---
st.set_page_config(layout="wide")
st.title("📊 XYZ Viewer – Dynamique avec pagination ≤ 3s")

# --- Pagination dynamique ---
if st.button("⬇️ Charger plus de dates (≤ 3s)"):
    new_rows, st.session_state.next_idx = preload_valid_dates(start_index=st.session_state.next_idx)
    st.session_state.valid_rows.extend(new_rows)

# --- Vérification ---
if len(st.session_state.valid_rows) == 0:
    st.error("❌ Aucune date valide chargée en moins de 3s.")
    st.stop()

# --- Slider ---
dates = [row["date"] for row in st.session_state.valid_rows]
selected_idx = st.slider("📅 Sélectionnez une date", 0, len(dates) - 1, 0)
selected_row = st.session_state.valid_rows[selected_idx]

# --- Affichage diagnostic ---
st.caption(f"Nombre de points XYZ : {n_points}")
st.caption(f"Nombre de dates préchargées : {len(dates)}")
st.markdown(f"### 🔎 Date affichée : `{selected_row['date']}`")

# --- Visualisation Plotly ---
fig = go.Figure(data=[
    go.Scatter3d(
        x=df_xyz["x"],
        y=df_xyz["y"],
        z=df_xyz["z"],
        mode='markers',
        marker=dict(
            size=3,
            color=selected_row["values"],
            colorscale="Viridis",
            cmin=0,
            cmax=10000,
            colorbar=dict(title="Valeur")
        ),
        hovertemplate="<b>X</b>: %{x:.2f}<br><b>Y</b>: %{y:.2f}<br><b>Z</b>: %{z:.2f}<br><b>Valeur</b>: %{marker.color:.2f}<extra></extra>"
    )
])
fig.update_layout(
    margin=dict(l=0, r=0, t=40, b=0),
    scene=dict(xaxis_title="X", yaxis_title="Y", zaxis_title="Z")
)
st.plotly_chart(fig, use_container_width=True)

# --- Connexion fermée automatiquement par Streamlit Cloud ---
