import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import psycopg2
import time

# --- PURGE TOTALE EN FORCE ---
if not st.session_state.get("cleared"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.session_state.cleared = True
    st.rerun()

# --- Connexion à la base Neon ---
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

# --- Récupération des ID et dates ---
@st.cache_data(show_spinner="🔄 Chargement des dates...")
def get_all_date_ids(_conn):  # Underscore prefix to avoid hashing
    df = pd.read_sql("SELECT id, date FROM data_fibre ORDER BY date", _conn)
    return df["id"].tolist(), df["date"].tolist()

# --- Récupération des points XYZ ---
@st.cache_data
def get_xyz(_conn):  # Underscore prefix to avoid hashing
    return pd.read_sql("SELECT x, y, z FROM xyz_points ORDER BY id", _conn)

# --- Chargement dynamique des données temporelles ---
def load_dates_dynamic(conn, date_ids, date_labels, start_idx, direction="forward", max_seconds=3.0):
    data = []
    start_time = time.time()
    step = 1 if direction == "forward" else -1
    index = start_idx
    df_xyz = get_xyz(conn)
    n_points = len(df_xyz)

    while 0 <= index < len(date_ids):
        try:
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
        except Exception as e:
            st.error(f"Erreur lors du chargement des données pour l'index {index}: {e}")
            break
            
        index += step
        if time.time() - start_time > max_seconds:
            break

    if direction == "backward":
        data.reverse()
        index = index + 1
    return data, index

# --- Configuration de la page ---
st.set_page_config(layout="wide")
st.title("📊 Visualisation 3D Dynamique des données XYZ")

# --- Initialisation sécurisée ---
try:
    conn = get_conn()
    date_ids, date_labels = get_all_date_ids(conn)
    df_xyz = get_xyz(conn)
    n_points = len(df_xyz)
    
    # Vérification que nous avons des données
    if not date_ids or not date_labels or df_xyz.empty:
        st.error("❌ Aucune donnée trouvée dans la base de données.")
        st.stop()
        
except Exception as e:
    st.error(f"❌ Erreur de connexion à la base de données: {e}")
    st.stop()

# --- Initialisation session ---
if "loaded_dates" not in st.session_state:
    try:
        initial_data, new_index = load_dates_dynamic(conn, date_ids, date_labels, len(date_ids) - 1, direction="backward")
        if not initial_data:
            st.error("❌ Impossible de charger les données initiales.")
            st.stop()
            
        st.session_state.loaded_dates = initial_data
        st.session_state.current_index = len(initial_data) - 1
        st.session_state.backward_index = new_index
        st.session_state.forward_index = date_ids.index(initial_data[-1]["id"]) + 1
    except Exception as e:
        st.error(f"❌ Erreur lors de l'initialisation: {e}")
        st.stop()

# --- Pagination ---
cols = st.columns([1, 6, 1])

with cols[0]:
    if st.button("⟸ Charger plus (avant)"):
        try:
            new_data, new_idx = load_dates_dynamic(conn, date_ids, date_labels, st.session_state.backward_index, direction="backward")
            if new_data:
                st.session_state.loaded_dates = new_data + st.session_state.loaded_dates
                st.session_state.current_index += len(new_data)
                st.session_state.backward_index = new_idx
                st.rerun()
            else:
                st.warning("⛔ Aucune date plus ancienne à charger.")
        except Exception as e:
            st.error(f"❌ Erreur lors du chargement des données antérieures: {e}")

with cols[2]:
    if st.button("Charger plus (après) ⟹"):
        try:
            new_data, new_idx = load_dates_dynamic(conn, date_ids, date_labels, st.session_state.forward_index, direction="forward")
            if new_data:
                st.session_state.loaded_dates += new_data
                st.session_state.forward_index = new_idx
                st.rerun()
            else:
                st.warning("✅ Vous avez atteint la dernière date disponible.")
        except Exception as e:
            st.error(f"❌ Erreur lors du chargement des données ultérieures: {e}")

# --- Vérification que nous avons des données chargées ---
if not st.session_state.loaded_dates:
    st.error("❌ Aucune donnée chargée.")
    st.stop()

# --- Slider avec étiquettes de dates lisibles ---
labels = []
for d in st.session_state.loaded_dates:
    try:
        if hasattr(d["date"], "strftime"):
            labels.append(d["date"].strftime("%d/%m/%Y %H:%M"))
        else:
            labels.append(str(d["date"]))
    except:
        labels.append("Date inconnue")

# Vérification des indices
max_index = len(labels) - 1
if st.session_state.current_index > max_index:
    st.session_state.current_index = max_index

slider_index = st.slider(
    "📅 Sélectionnez une date :",
    min_value=0,
    max_value=max_index,
    value=st.session_state.current_index,
    format_func=lambda i: labels[i] if 0 <= i < len(labels) else "?",
)

st.session_state.current_index = slider_index
selected = st.session_state.loaded_dates[slider_index]

# --- Affichage de la date sélectionnée (centrée) ---
if labels:
    st.markdown(
        f"<center><code>{labels[0]}</code> ⟶ <strong style='color:red;'>{labels[slider_index]}</strong> ⟶ <code>{labels[-1]}</code></center>",
        unsafe_allow_html=True
    )

# --- Vérification de cohérence ---
values = selected["values"]

if len(values) != n_points:
    st.error(f"❌ Incohérence entre les points XYZ ({n_points}) et les données ({len(values)}).")
    st.stop()

# --- Affichage Plotly 3D ---
try:
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
    
except Exception as e:
    st.error(f"❌ Erreur lors de la création du graphique: {e}")