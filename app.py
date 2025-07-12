import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import psycopg2
import time

# --- Connexion Neon ---
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

# --- Récupérer toutes les dates disponibles avec leurs IDs ---
@st.cache_data(show_spinner="🔄 Chargement des dates...")
def get_all_date_ids():
    df = pd.read_sql("SELECT id, date FROM data_fibre ORDER BY date", conn)
    return df["id"].tolist(), df["date"].tolist()

date_ids, date_labels = get_all_date_ids()

# --- Récupérer les points XYZ (chargés une seule fois) ---
@st.cache_data
def get_xyz():
    return pd.read_sql("SELECT x, y, z FROM xyz_points ORDER BY id", conn)

df_xyz = get_xyz()
n_points = len(df_xyz)

# --- Chargement dynamique par ID avec temps maximum ---
@st.cache_data(ttl=60, max_entries=50)
def load_dates_dynamic(start_idx, direction="forward", max_seconds=3.0):
    data = []
    start_time = time.time()
    step = 1 if direction == "forward" else -1
    index = start_idx

    while 0 <= index < len(date_ids):
        query = "SELECT values FROM data_fibre WHERE id = %s"
        df = pd.read_sql(query, conn, params=[date_ids[index]])
        if not df.empty:
            values = df["values"].iloc[0]
            if len(values) == n_points:
                data.append({
                    "id": date_ids[index],
                    "date": date_labels[index],
                    "values": values
                })
        index += step
        if time.time() - start_time > max_seconds:
            break

    if direction == "backward":
        data.reverse()
        index = index + 1
    return data, index

# --- Initialisation ---
if "loaded_dates" not in st.session_state:
    initial_data, new_index = load_dates_dynamic(len(date_ids) - 1, direction="backward")
    st.session_state.loaded_dates = initial_data
    st.session_state.current_index = len(initial_data) - 1
    st.session_state.backward_index = new_index
    st.session_state.forward_index = date_ids.index(initial_data[-1]["id"]) + 1

st.set_page_config(layout="wide")
st.title("📊 Visualisation 3D Dynamique des données XYZ")

# --- Boutons de pagination ---
cols = st.columns([1, 6, 1])

with cols[0]:
    if st.button("⟸ Charger plus (avant)"):
        new_data, new_idx = load_dates_dynamic(st.session_state.backward_index, direction="backward")
        if new_data:
            st.session_state.loaded_dates = new_data + st.session_state.loaded_dates
            st.session_state.current_index += len(new_data)
            st.session_state.backward_index = new_idx
        else:
            st.warning("⛔ Aucune date plus ancienne à charger.")

with cols[2]:
    if st.button("Charger plus (après) ⟹"):
        new_data, new_idx = load_dates_dynamic(st.session_state.forward_index, direction="forward")
        if new_data:
            st.session_state.loaded_dates += new_data
            st.session_state.forward_index = new_idx
        else:
            st.warning("✅ Vous avez atteint la dernière date disponible.")

# --- Slider --- (amélioré avec affichage de la date sélectionnée)
labels = [d["date"].strftime("%d/%m/%Y %H:%M") if hasattr(d["date"], "strftime") else str(d["date"]) for d in st.session_state.loaded_dates]

slider_index = st.slider(
    "📅 Sélectionnez une date :",
    min_value=0,
    max_value=len(labels) - 1,
    value=st.session_state.current_index,
    format_func=lambda i: labels[i] if 0 <= i < len(labels) else "?",
)

st.session_state.current_index = slider_index
selected = st.session_state.loaded_dates[slider_index]

# --- Affichage de la date sélectionnée (optionnel mais clair)
st.markdown(
    f"<center><code>{labels[0]}</code> ⟶ <strong style='color:red;'>{labels[slider_index]}</strong> ⟶ <code>{labels[-1]}</code></center>",
    unsafe_allow_html=True
)


# --- Données sélectionnées ---
values = selected["values"]

if len(values) != n_points:
    st.error("❌ Incohérence entre les points XYZ et les données.")
    st.stop()

# --- Affichage Plotly ---
fig = go.Figure(data=[
    go.Scatter3d(
        x=df_xyz["x"],
        y=df_xyz["y"],
        z=df_xyz["z"],
        mode="markers",
        marker=dict(
            size=4,
            color=values,
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
    scene=dict(
        xaxis_title="X",
        yaxis_title="Y",
        zaxis_title="Z"
    )
)

st.plotly_chart(fig, use_container_width=True)
