import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import psycopg2
from sqlalchemy import create_engine
import time

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    layout="wide",
    page_title="Visualisation Fibre 3D",
    page_icon="📊"
)

# --- CONFIGURATION GLOBALE ---
CHUNK_SIZE = 50
DB_CONFIG = {
    "dbname": "neondb",
    "user": "neondb_owner",
    "password": "npg_GJ6XsHumk0Yz",
    "host": "ep-lucky-base-a22m3jwu-pooler.eu-central-1.aws.neon.tech",
    "port": 5432,
    "sslmode": "require"
}

# --- PURGE TOTALE EN FORCE ---
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

# --- INTERFACE PRINCIPALE ---
st.markdown("### 📊 Visualisation 3D des Données de Fibre Optique")

# --- PANNEAU DE CONTRÔLE HORIZONTAL ---
controls_cols = st.columns([2, 8, 2]) # 3 colonnes pour la disposition

# Bouton "Charger avant" dans la première colonne
with controls_cols[0]:
    if st.button("⟸ Charger avant", use_container_width=True):
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
            st.toast("⛔ Première date atteinte", icon="⛔")

# Slider de sélection dans la colonne centrale (la plus large)
with controls_cols[1]:
    if not st.session_state.get("loaded_dates"):
        st.warning("⏳ Aucune donnée chargée.")
        st.stop()

    readable_labels = [d["date"].strftime("%d/%m/%Y %H:%M") for d in st.session_state.loaded_dates]
    current_selection_index = max(0, min(st.session_state.current_index, len(readable_labels) - 1))
    default_selection = readable_labels[current_selection_index]

    selected_label = st.select_slider(
        "📅 Sélectionnez une date",
        options=readable_labels,
        value=default_selection,
        key="date_selector",
        label_visibility="collapsed" # Cache le label pour gagner de la place
    )
    slider_index = readable_labels.index(selected_label)
    st.session_state.current_index = slider_index
    selected_data = st.session_state.loaded_dates[slider_index]

# Statut "Dernière date" dans la troisième colonne
with controls_cols[2]:
    if st.session_state.backward_index + len(st.session_state.loaded_dates) >= len(date_ids):
        st.success("✅ Dernière date")

# --- AFFICHAGE COMPACT DE LA DATE ---
st.markdown(
    f"<p style='text-align:center; font-size: 0.9em; color: grey;'>Plage chargée : {readable_labels[0]}  —  <strong style='color: #FF4B4B;'>{selected_label}</strong>  —  {readable_labels[-1]}</p>",
    unsafe_allow_html=True
)

st.divider()

# --- GRAPHIQUE 3D MIS EN AVANT ---
values = selected_data["values"]
if len(values) != n_points:
    st.error(f"❌ Incohérence des données : {n_points} points XYZ mais {len(values)} valeurs.")
    st.stop()

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
                colorbar=dict(title="Valeur", thickness=15, len=0.75)
            ),
            hovertemplate="<b>X</b>: %{x:.2f}<br><b>Y</b>: %{y:.2f}<br><b>Z</b>: %{z:.2f}<br><b>Valeur</b>: %{marker.color:.2f}<extra></extra>"
        )
    ])
    # Optimisation de l'espace : suppression des marges et ajustement de la scène
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0), # Aucune marge
        scene=dict(
            xaxis_title="X",
            yaxis_title="Y",
            zaxis_title="Z",
            aspectmode='data' # Assure que les proportions sont respectées
        )
    )

    st.plotly_chart(fig, use_container_width=True, height=650)

except Exception as e:
    st.error(f"❌ Erreur lors de la création du graphique Plotly : {e}")```