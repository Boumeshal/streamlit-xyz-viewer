import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go
import time
import psutil

# Connexion Neon
conn = psycopg2.connect(
    dbname=st.secrets["db_name"],
    user=st.secrets["db_user"],
    password=st.secrets["db_password"],
    host=st.secrets["db_host"],
    port=st.secrets["db_port"]
)

# Initialisation
if "dates" not in st.session_state:
    st.session_state.dates = []
if "values_cache" not in st.session_state:
    st.session_state.values_cache = {}
if "selected_index" not in st.session_state:
    st.session_state.selected_index = 0
if "start_index" not in st.session_state:
    st.session_state.start_index = 0
if "playing" not in st.session_state:
    st.session_state.playing = False

RAM_LIMIT_MB = 400


def check_ram():
    """Vide le cache si la RAM dépasse la limite autorisée"""
    process = psutil.Process()
    mem = process.memory_info().rss / 1024 / 1024
    if mem > RAM_LIMIT_MB:
        st.session_state.values_cache.clear()
        st.warning("⚠️ Cache vidé automatiquement (RAM > 400 MB)")


def charger_dates(start, direction="forward"):
    """Charge dynamiquement des dates en respectant une limite de 3s"""
    t0 = time.time()
    limit = 3.0
    query = """
        SELECT id, date FROM data_fibre
        WHERE id > %s ORDER BY id ASC
    """ if direction == "forward" else """
        SELECT id, date FROM data_fibre
        WHERE id < %s ORDER BY id DESC
    """
    cursor = conn.cursor()
    cursor.execute(query, (start,))
    rows = cursor.fetchall()

    chargées = []
    for row in rows:
        id_, date = row
        if id_ in st.session_state.values_cache:
            continue
        val_query = "SELECT values FROM data_fibre WHERE id = %s"
        df = pd.read_sql(val_query, conn, params=[id_])
        if df.empty:
            continue
        values = df["values"][0]
        df_xyz = pd.read_sql("SELECT x, y, z FROM xyz_points ORDER BY id", conn)
        if len(values) != len(df_xyz):
            continue
        st.session_state.values_cache[id_] = (date, values)
        chargées.append((id_, date))
        if time.time() - t0 > limit:
            break

    if direction == "backward":
        chargées = list(reversed(chargées))

    for id_, date in chargées:
        if date not in st.session_state.dates:
            st.session_state.dates.append(date)

    st.session_state.dates.sort()
    return len(chargées)


def plot_xyz(values, title):
    df_xyz = pd.read_sql("SELECT x, y, z FROM xyz_points ORDER BY id", conn)
    x, y, z = df_xyz["x"], df_xyz["y"], values
    fig = go.Figure(data=go.Scatter3d(
        x=x, y=y, z=z,
        mode='markers',
        marker=dict(
            size=2,
            color=z,
            colorscale='Viridis',
            colorbar=dict(title="Amplitude"),
            showscale=True
        )
    ))
    fig.update_layout(margin=dict(l=0, r=0, b=0, t=30), title=title)
    st.plotly_chart(fig, use_container_width=True)


# Titre
st.title("📊 Visualisation dynamique")
st.caption("Navigation fluide via slider interactif et pagination intelligente")

col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if st.button("⬅️ Charger avant"):
        if st.session_state.start_index > 0:
            st.session_state.start_index -= 1
            nb = charger_dates(st.session_state.start_index, direction="backward")
            if nb == 0:
                st.warning("🚫 Aucune date plus ancienne")
        else:
            st.warning("🚫 Début des données atteint")

with col3:
    if st.button("➡️ Charger après"):
        st.session_state.start_index += 1
        nb = charger_dates(st.session_state.start_index, direction="forward")
        if nb == 0:
            st.warning("🚫 Aucune nouvelle date trouvée")

# Indicateur de fluidité
fps = 0
st.markdown("⚡ **Fluidité estimée**")
placeholder_fps = st.empty()

# Play/Pause
if st.button("▶ Play" if not st.session_state.playing else "⏸ Pause"):
    st.session_state.playing = not st.session_state.playing

# Slider
if st.session_state.dates:
    date_labels = [d.strftime("%Y-%m-%d %H:%M:%S") for d in st.session_state.dates]
    index = st.slider("📅 Sélectionnez une date", 0, len(st.session_state.dates) - 1,
                      value=st.session_state.selected_index,
                      format=None,
                      label_visibility="visible",
                      key="date_slider")
    st.session_state.selected_index = index
    date = st.session_state.dates[index]
    # Trouver l'id correspondant
    id_ = None
    for k, (d, _) in st.session_state.values_cache.items():
        if d == date:
            id_ = k
            break
    if id_ is not None:
        values = st.session_state.values_cache[id_][1]
        t0 = time.time()
        plot_xyz(values, f"Date : {date.strftime('%Y-%m-%d %H:%M:%S')}")
        fps = 1 / max(0.001, time.time() - t0)
        placeholder_fps.markdown(f"### {fps:.2f} FPS")
        check_ram()
else:
    st.warning("Aucune donnée chargée.")

# Animation si Play
if st.session_state.playing:
    for i in range(st.session_state.selected_index + 1, len(st.session_state.dates)):
        st.session_state.selected_index = i
        st.rerun()
