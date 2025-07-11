import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import psycopg2
import time

# --- Connexion PostgreSQL Neon ---
conn = psycopg2.connect(
    dbname="neondb",
    user="neondb_owner",
    password="npg_GJ6XsHumk0Yz",
    host="ep-lucky-base-a22m3jwu-pooler.eu-central-1.aws.neon.tech",
    port=5432,
    sslmode="require"
)

# --- Paramètres globaux ---
COLOR_MIN = 0
COLOR_MAX = 10000
MARKER_SIZE = 4
FONT_SIZE = 14
LOAD_TIME_LIMIT = 3.0  # secondes

# --- Cache initial pour les XYZ ---
@st.cache_data
def load_xyz():
    return pd.read_sql("SELECT id, x, y, z FROM xyz_points ORDER BY id", conn)

df_xyz = load_xyz()
xyz_count = len(df_xyz)

# --- Récupération des dates disponibles ---
@st.cache_data
def get_all_date_ids():
    df = pd.read_sql("SELECT id, date FROM data_fibre ORDER BY date DESC", conn)
    return df

df_date_ids = get_all_date_ids()
all_ids = df_date_ids["id"].tolist()
all_dates = df_date_ids["date"].tolist()

# --- Chargement dynamique de données selon limite de temps ---
def load_dates_dynamic(start_index):
    valid_data = {}
    t0 = time.time()
    i = start_index
    while i < len(all_ids):
        id_ = all_ids[i]
        date_str = str(all_dates[i])

        query = f"SELECT values FROM data_fibre WHERE id = {int(id_)}"
        df = pd.read_sql(query, conn)
        values = df["values"].iloc[0]

        if len(values) != xyz_count:
            i += 1
            continue

        valid_data[date_str] = values
        i += 1
        if time.time() - t0 >= LOAD_TIME_LIMIT:
            break
    return valid_data, i

# --- UI Streamlit ---
st.set_page_config(layout="wide")
st.title("📊 XYZ Viewer – Dynamique avec pagination ≤ 3s")
st.markdown("")

# --- Session ---
if "data_cache" not in st.session_state:
    st.session_state.data_cache = {}
    st.session_state.last_loaded_index = 0

# --- Préchargement initial ---
if len(st.session_state.data_cache) == 0:
    with st.spinner("Préchargement des données initiales..."):
        initial_data, new_index = load_dates_dynamic(0)
        st.session_state.data_cache.update(initial_data)
        st.session_state.last_loaded_index = new_index

# --- Bouton pagination ---
if st.button("⬇ Charger plus de dates (≤ 3s)"):
    with st.spinner("Chargement dynamique..."):
        new_data, new_index = load_dates_dynamic(st.session_state.last_loaded_index)
        if len(new_data) == 0:
            st.error("❌ Aucune date valide chargée en moins de 3s.")
        else:
            st.session_state.data_cache.update(new_data)
            st.session_state.last_loaded_index = new_index

# --- Données à afficher ---
valid_dates = list(st.session_state.data_cache.keys())

if len(valid_dates) == 0:
    st.error("⚠️ Aucune donnée disponible pour affichage.")
    st.stop()

# --- Création des frames ---
frames = []
for date in valid_dates:
    z_vals = st.session_state.data_cache[date]
    frames.append(go.Frame(
        data=[go.Scatter3d(
            x=df_xyz["x"], y=df_xyz["y"], z=df_xyz["z"],
            mode="markers",
            marker=dict(
                size=MARKER_SIZE,
                color=z_vals,
                colorscale="Viridis",
                cmin=COLOR_MIN,
                cmax=COLOR_MAX,
                opacity=0.85,
                colorbar=dict(title=dict(text="Valeur", font=dict(size=FONT_SIZE)))
            ),
            hovertemplate="<b>X</b>: %{x:.2f}<br><b>Y</b>: %{y:.2f}<br><b>Z</b>: %{z:.2f}<br><b>Valeur</b>: %{marker.color:.2f}<extra></extra>",
        )],
        name=date
    ))

# --- Affichage initial ---
initial_z = st.session_state.data_cache[valid_dates[0]]
scatter = go.Scatter3d(
    x=df_xyz["x"], y=df_xyz["y"], z=df_xyz["z"],
    mode="markers",
    marker=dict(
        size=MARKER_SIZE,
        color=initial_z,
        colorscale="Viridis",
        cmin=COLOR_MIN,
        cmax=COLOR_MAX,
        opacity=0.85,
        colorbar=dict(title=dict(text="Valeur", font=dict(size=FONT_SIZE)))
    ),
    hovertemplate="<b>X</b>: %{x:.2f}<br><b>Y</b>: %{y:.2f}<br><b>Z</b>: %{z:.2f}<br><b>Valeur</b>: %{marker.color:.2f}<extra></extra>",
)

# --- Création de la figure Plotly ---
fig = go.Figure(
    data=[scatter],
    layout=go.Layout(
        title=dict(
            text="XYZ Data – Colorisation temporelle dynamique",
            x=0.5, font=dict(size=FONT_SIZE + 2)
        ),
        template="simple_white",
        scene=dict(
            xaxis=dict(title="X"),
            yaxis=dict(title="Y"),
            zaxis=dict(title="Z"),
        ),
        updatemenus=[
            dict(type="buttons", showactive=False, buttons=[
                dict(label="▶ Play", method="animate", args=[None, {
                    "frame": {"duration": 500, "redraw": True}, "fromcurrent": True
                }]),
                dict(label="⏸ Pause", method="animate", args=[[None], {
                    "mode": "immediate", "frame": {"duration": 0, "redraw": False}
                }])
            ])
        ],
        sliders=[dict(
            steps=[
                dict(method="animate", args=[[d], {"mode": "immediate", "frame": {"duration": 0, "redraw": True}}], label=d)
                for d in valid_dates
            ],
            transition={"duration": 0},
            x=0.1, xanchor="left", y=0, yanchor="top"
        )],
        margin=dict(l=0, r=0, t=40, b=0),
    ),
    frames=frames
)

# --- Affichage final ---
st.plotly_chart(fig, use_container_width=True)
