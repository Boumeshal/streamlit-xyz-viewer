import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import create_engine
from streamlit_plotly_events import plotly_events  # import de la lib externe

# --- CONFIGURATION ---
CHUNK_SIZE = 50

DB_CONFIG = {
    "dbname": "neondb",
    "user": "neondb_owner",
    "password": "npg_GJ6XsHumk0Yz",
    "host": "ep-lucky-base-a22m3jwu-pooler.eu-central-1.aws.neon.tech",
    "port": 5432,
    "sslmode": "require"
}

st.set_page_config(layout="wide")
st.title("📊 Visualisation 3D Dynamique des données XYZ")

if not st.session_state.get("cleared"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.session_state.cleared = True
    st.experimental_rerun()

@st.cache_resource
def get_engine():
    db_url = (
        f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
        f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}?sslmode={DB_CONFIG['sslmode']}"
    )
    return create_engine(db_url)

@st.cache_data(show_spinner="🔄 Chargement des métadonnées...")
def get_all_date_ids():
    engine = get_engine()
    df = pd.read_sql("SELECT id, date FROM data_fibre ORDER BY date", engine)
    return df["id"].tolist(), df["date"].tolist()

@st.cache_data
def get_xyz():
    engine = get_engine()
    return pd.read_sql("SELECT x, y, z FROM xyz_points ORDER BY id", engine)

def load_dates_in_batch(ids_to_fetch):
    if not ids_to_fetch:
        return []
    engine = get_engine()
    n_points = len(get_xyz())
    query = "SELECT id, date, values FROM data_fibre WHERE id = ANY(%s) ORDER BY date"
    df = pd.read_sql(query, engine, params=(ids_to_fetch,))
    data = [
        {"id": row["id"], "date": row["date"], "values": row["values"]}
        for _, row in df.iterrows() if len(row.get("values", [])) == n_points
    ]
    return data

try:
    date_ids, date_labels = get_all_date_ids()
    df_xyz = get_xyz()
    n_points = len(df_xyz)
    if not date_ids or df_xyz.empty:
        st.error("❌ Aucune donnée de base trouvée.")
        st.stop()
except Exception as e:
    st.error(f"❌ Erreur critique lors de la connexion initiale: {e}")
    st.stop()

if "loaded_dates" not in st.session_state:
    start_index = max(0, len(date_ids) - CHUNK_SIZE)
    initial_ids_to_fetch = date_ids[start_index:]
    initial_data = load_dates_in_batch(initial_ids_to_fetch)
    if not initial_data:
        st.error("❌ Impossible de charger les données initiales.")
        st.stop()
    st.session_state.loaded_dates = initial_data
    st.session_state.current_index = len(initial_data) - 1
    st.session_state.backward_index = start_index

if "selected_point_index" not in st.session_state:
    st.session_state.selected_point_index = 0  # Index sélectionné dans le timeseries

# Pagination boutons, unchanged
cols = st.columns([1, 6, 1])
with cols[0]:
    if st.button("⟸ Charger plus (avant)"):
        end = st.session_state.backward_index
        start = max(0, end - CHUNK_SIZE)
        ids_to_fetch = date_ids[start:end]
        if ids_to_fetch:
            new_data = load_dates_in_batch(ids_to_fetch)
            if new_data:
                st.session_state.loaded_dates = new_data + st.session_state.loaded_dates
                st.session_state.current_index += len(new_data)
                st.session_state.backward_index = start
                st.experimental_rerun()
        else:
            st.warning("⛔ Vous avez atteint la date la plus ancienne.")

with cols[2]:
    if st.session_state.backward_index + len(st.session_state.loaded_dates) >= len(date_ids):
        st.markdown("<p style='text-align: center; color: green;'>✅<br>Dernière date</p>", unsafe_allow_html=True)
    else:
        st.button("Charger plus (après) ⟹", disabled=True)

# Date slider
readable_labels = [d["date"].strftime("%d/%m/%Y %H:%M") for d in st.session_state.loaded_dates]
current_selection_index = max(0, min(st.session_state.current_index, len(readable_labels) - 1))
default_selection = readable_labels[current_selection_index]

selected_label = st.select_slider(
    "📅 Sélectionnez une date :",
    options=readable_labels,
    value=default_selection,
    key="date_selector"
)

slider_index = readable_labels.index(selected_label)
st.session_state.current_index = slider_index
selected_data = st.session_state.loaded_dates[slider_index]

values = selected_data["values"]
if len(values) != n_points:
    st.error(f"❌ Incohérence des données : {n_points} points XYZ mais {len(values)} valeurs pour cette date.")
    st.stop()

# --- GRAPH 3D AVEC SÉLECTION CLIQUABLE ---
fig = go.Figure(data=[
    go.Scatter3d(
        x=df_xyz["x"], y=df_xyz["y"], z=df_xyz["z"],
        mode="markers",
        marker=dict(
            size=4,
            color=values,
            colorscale="Turbo",
            cmin=0,
            cmax=10000,
            colorbar=dict(title="Valeur")
        ),
        hovertemplate="<b>X</b>: %{x:.2f}<br><b>Y</b>: %{y:.2f}<br><b>Z</b>: %{z:.2f}<br><b>Valeur</b>: %{marker.color:.2f}<extra></extra>",
        customdata=list(range(len(values)))  # index des points
    )
])
fig.update_layout(
    margin=dict(l=0, r=0, t=40, b=0),
    scene=dict(xaxis_title="X", yaxis_title="Y", zaxis_title="Z")
)

selected_points = plotly_events(fig, click_event=True, key="3d_scatter")

if selected_points:
    clicked_index = selected_points[0]["customdata"]
    st.session_state.selected_point_index = clicked_index

# Graph 2D scattergl
fig2d = go.Figure(data=[
    go.Scattergl(
        x=list(range(len(values))),
        y=values,
        mode="markers",
        marker=dict(
            size=6,
            color=values,
            colorscale="Turbo",
            cmin=0,
            cmax=10000,
            colorbar=dict(title="Valeur"),
            line=dict(width=0)
        ),
        hovertemplate=(
            f"<b>Date</b>: {selected_label}<br>"
            "<b>Point</b>: %{x}<br>"
            "<b>Valeur</b>: %{y:.2f}<extra></extra>"
        ),
        name="Values ScatterGL",
        customdata=list(range(len(values))),
    )
])
fig2d.update_layout(
    title=f"📈 ScatterGL plot 2D ({selected_label})",
    xaxis_title="Index du point",
    yaxis_title="Valeur",
    yaxis=dict(range=[0, 10000]),
    margin=dict(l=40, r=40, t=40, b=40)
)
st.plotly_chart(fig2d, use_container_width=True)

# --- SLIDER POINT INDEX SYNCHRONISÉ ---
point_index = st.slider(
    "🔍 Sélectionnez l’index du point à suivre dans le temps :",
    0, n_points - 1,
    st.session_state.selected_point_index,
    key="point_slider"
)
st.session_state.selected_point_index = point_index

# --- EXTRACTION VALEURS POUR CE POINT ---
times = [entry["date"] for entry in st.session_state.loaded_dates]
point_values = [entry["values"][point_index] for entry in st.session_state.loaded_dates]

# --- GRAPHIQUE TIME SERIES ---
timeseries_fig = go.Figure()
timeseries_fig.add_trace(go.Scatter(
    x=times,
    y=point_values,
    mode="lines+markers",
    line=dict(color="royalblue"),
    marker=dict(size=6),
    name=f"Valeurs du point {point_index}"
))
timeseries_fig.update_layout(
    title=f"📊 Évolution temporelle du point {point_index}",
    xaxis_title="Temps",
    yaxis_title="Valeur",
    yaxis=dict(autorange=True),
    margin=dict(l=40, r=40, t=40, b=40)
)
st.plotly_chart(timeseries_fig, use_container_width=True)
