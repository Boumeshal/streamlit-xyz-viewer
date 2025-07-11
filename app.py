import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import psycopg2
import time

# --- CONNEXION NEON ---
conn = psycopg2.connect(
    dbname="neondb",
    user="neondb_owner",
    password="npg_GJ6XsHumk0Yz",
    host="ep-lucky-base-a22m3jwu-pooler.eu-central-1.aws.neon.tech",
    port=5432,
    sslmode="require"
)

st.set_page_config(layout="wide")
st.title("📊 XYZ Viewer – Dynamique avec pagination ≤ 3s")

# --- COORDONNÉES XYZ ---
df_xyz = pd.read_sql("SELECT x, y, z FROM xyz_points ORDER BY id", conn)
n_points = len(df_xyz)

# --- CHARGER TOUTES LES DATES DISPONIBLES ---
df_all_dates = pd.read_sql("SELECT date FROM data_fibre ORDER BY date", conn)
all_dates = df_all_dates["date"].tolist()

# --- INITIALISER SESSION STATE ---
if "loaded_dates" not in st.session_state:
    st.session_state.loaded_dates = []
    st.session_state.values_cache = {}
    st.session_state.pagination_offset = 0

# --- CHARGER DATES DANS LA LIMITE DES 3s ---
def load_dates_within_3s():
    max_duration = 10
    start_total = time.time()
    new_loaded = []

    while st.session_state.pagination_offset < len(all_dates):
        d = all_dates[st.session_state.pagination_offset]
        q = "SELECT values FROM data_fibre WHERE date = %s"
        start = time.time()
        df = pd.read_sql(q, conn, params=[d])
        elapsed = time.time() - start

        if df.empty or len(df["values"][0]) != n_points:
            st.session_state.pagination_offset += 1
            continue

        if (time.time() - start_total) + elapsed > max_duration:
            break

        st.session_state.values_cache[d] = df["values"][0]
        new_loaded.append(d)
        st.session_state.pagination_offset += 1

    return new_loaded

# --- BOUTON POUR CHARGER PLUS ---
if st.button("⬇ Charger plus de dates (≤ 3s)"):
    new = load_dates_within_3s()
    st.session_state.loaded_dates += new
    st.experimental_rerun()

# --- SI RIEN CHARGÉ, CHARGER AU MOINS UNE FOIS ---
if not st.session_state.loaded_dates:
    load_dates_within_3s()
    if not st.session_state.loaded_dates:
        st.error("❌ Aucune date valide chargée en moins de 3s.")
        st.stop()

# --- TRI DES DATES ---
selected_dates = sorted(st.session_state.loaded_dates)
selected_index = st.slider("Sélectionnez une date", 0, len(selected_dates)-1, 0)
selected_date = selected_dates[selected_index]
st.markdown(f"### 📅 Date sélectionnée : {selected_date}")

values = st.session_state.values_cache[selected_date]

# --- AFFICHAGE PLOTLY ---
fig = go.Figure(data=[
    go.Scatter3d(
        x=df_xyz["x"], y=df_xyz["y"], z=df_xyz["z"],
        mode='markers',
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
    title=dict(text="XYZ Data – Affichage dynamique", x=0.5),
    margin=dict(l=0, r=0, t=40, b=0),
    scene=dict(xaxis_title="X", yaxis_title="Y", zaxis_title="Z"),
    updatemenus=[dict(
        type="buttons",
        showactive=False,
        buttons=[
            dict(label="▶ Play", method="animate",
                 args=[None, {"frame": {"duration": 500, "redraw": True}, "fromcurrent": True}]),
            dict(label="⏸ Pause", method="animate",
                 args=[[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}])
        ]
    )],
    sliders=[dict(
        steps=[dict(method="animate",
                    args=[[str(d)], {"mode": "immediate", "frame": {"duration": 0, "redraw": True}}],
                    label=str(d)) for d in selected_dates],
        transition={"duration": 0},
        x=0.1, xanchor="left", y=0, yanchor="top"
    )]
)

# --- FRAMES ---
frames = []
for d in selected_dates:
    frames.append(go.Frame(
        data=[
            go.Scatter3d(
                x=df_xyz["x"], y=df_xyz["y"], z=df_xyz["z"],
                mode='markers',
                marker=dict(
                    size=4,
                    color=st.session_state.values_cache[d],
                    colorscale="Turbo",
                    cmin=0,
                    cmax=10000,
                    opacity=0.85
                ),
                hovertemplate="<b>X</b>: %{x:.2f}<br><b>Y</b>: %{y:.2f}<br><b>Z</b>: %{z:.2f}<br><b>Valeur</b>: %{marker.color:.2f}<extra></extra>"
            )
        ],
        name=str(d)
    ))
fig.frames = frames

st.plotly_chart(fig, use_container_width=True)

# --- FERMER LA CONNEXION ---
conn.close()
