import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import psycopg2
from sqlalchemy import create_engine
import time

# --- CONFIGURATION ---
CHUNK_SIZE = 50

# --- AVERTISSEMENT DE SÉCURITÉ ---
# Idéalement, utilisez les secrets de Streamlit (st.secrets) pour plus de sécurité.
DB_CONFIG = {
    "dbname": "neondb",
    "user": "neondb_owner",
    "password": "npg_GJ6XsHumk0Yz",
    "host": "ep-lucky-base-a22m3jwu-pooler.eu-central-1.aws.neon.tech",
    "port": 5432,
    "sslmode": "require"
}

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(layout="wide")
st.title("📊 Visualisation 3D Dynamique des données XYZ")

# --- PURGE TOTALE EN FORCE (pour le développement) ---
if not st.session_state.get("cleared"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.session_state.cleared = True
    st.rerun()

# --- CONNEXION À LA BASE DE DONNÉES ---
@st.cache_resource
def get_engine():
    try:
        db_url = (
            f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
            f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}?sslmode={DB_CONFIG['sslmode']}"
        )
        return create_engine(db_url)
    except Exception as e:
        st.error(f"Erreur de configuration de la connexion SQLAlchemy: {e}")
        st.stop()

# --- FONCTIONS DE RÉCUPÉRATION DES DONNÉES ---
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
    try:
        query = "SELECT id, date, values FROM data_fibre WHERE id = ANY(%s) ORDER BY date"
        df = pd.read_sql(query, engine, params=(ids_to_fetch,))
    except Exception as e:
        st.error(f"Erreur lors du chargement des données par lot: {e}")
        return []
    data = [
        {"id": row["id"], "date": row["date"], "values": row["values"]}
        for _, row in df.iterrows() if len(row.get("values", [])) == n_points
    ]
    return data

# --- INITIALISATION DE L'APPLICATION ---
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

# --- PAGINATION ---
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
                st.rerun()
        else:
            st.warning("⛔ Vous avez atteint la date la plus ancienne.")

with cols[2]:
    if st.session_state.backward_index + len(st.session_state.loaded_dates) >= len(date_ids):
        st.markdown("<p style='text-align: center; color: green;'>✅<br>Dernière date</p>", unsafe_allow_html=True)
    else:
        st.button("Charger plus (après) ⟹", disabled=True)

# --- SÉLECTION DE DATE AVEC st.select_slider ---
if not st.session_state.get("loaded_dates"):
    st.warning("⏳ Aucune donnée chargée.")
    st.stop()

readable_labels = [d["date"].strftime("%d/%m/%Y %H:%M") for d in st.session_state.loaded_dates]

# Sécurisation de l'index pour la valeur par défaut
current_selection_index = max(0, min(st.session_state.current_index, len(readable_labels) - 1))
default_selection = readable_labels[current_selection_index]

# Remplacement de st.slider par st.select_slider pour une meilleure compatibilité
selected_label = st.select_slider(
    "📅 Sélectionnez une date :",
    options=readable_labels,
    value=default_selection,
    key="date_selector" # Nouvelle clé pour éviter les conflits d'état
)

# Retrouver l'index à partir de l'étiquette sélectionnée
slider_index = readable_labels.index(selected_label)
st.session_state.current_index = slider_index
selected_data = st.session_state.loaded_dates[slider_index]

# --- AFFICHAGE DE LA DATE SÉLECTIONNÉE ---
st.markdown(
    f"<center><code>{readable_labels[0]}</code> ⟶ <strong style='color:red;'>{selected_label}</strong> ⟶ <code>{readable_labels[-1]}</code></center>",
    unsafe_allow_html=True
)

# --- VÉRIFICATION DE COHÉRENCE ---
values = selected_data["values"]
if len(values) != n_points:
    st.error(f"❌ Incohérence des données : {n_points} points XYZ mais {len(values)} valeurs pour cette date.")
    st.stop()

# --- AFFICHAGE PLOTLY 3D ---
try:
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
            hovertemplate="<b>X</b>: %{x:.2f}<br><b>Y</b>: %{y:.2f}<br><b>Z</b>: %{z:.2f}<br><b>Valeur</b>: %{marker.color:.2f}<extra></extra>"
        )
    ])
    fig.update_layout(
        margin=dict(l=0, r=0, t=40, b=0),
        scene=dict(xaxis_title="X", yaxis_title="Y", zaxis_title="Z")
    )
    st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.error(f"❌ Erreur lors de la création du graphique Plotly : {e}")

# --- AFFICHAGE PLOTLY 2D scattergl (valeurs en fonction de l'ordre des points) ---
try:
    fig2d = go.Figure(data=[
        go.Scattergl(
            x=list(range(len(values))),
            y=values,
            mode="markers+lines",
            marker=dict(color="blue"),
            line=dict(shape="linear"),
            name="Values ScatterGL"
        )
    ])
    fig2d.update_layout(
        title="📈 ScatterGL plot 2D des valeurs (ordre des points)",
        xaxis_title="Index du point",
        yaxis_title="Valeur",
        yaxis=dict(range=[0, 15000]),
        margin=dict(l=40, r=40, t=40, b=40)
    )
    st.plotly_chart(fig2d, use_container_width=True)
except Exception as e:
    st.error(f"❌ Erreur lors de la création du graphique 2D scattergl : {e}")
