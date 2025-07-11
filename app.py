import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import psycopg2

# --- PARAMÈTRES DE CONNEXION NEON ---
conn = psycopg2.connect(
    dbname="neondb",
    user="neondb_owner",
    password="npg_GJ6XsHumk0Yz",
    host="ep-lucky-base-a22m3jwu-pooler.eu-central-1.aws.neon.tech",
    port=5432,
    sslmode="require"
)


def get_valid_dates(conn):
    df_dates = pd.read_sql("SELECT DISTINCT date FROM data_fibre ORDER BY date", conn)
    valid_dates = []

    # Récupérer une seule fois les points XYZ
    df_xyz = pd.read_sql("SELECT x, y, z FROM xyz_points ORDER BY id", conn)
    n_points = len(df_xyz)

    for date in df_dates["date"]:
        query = "SELECT values FROM data_fibre WHERE date = %s"
        df_values_raw = pd.read_sql(query, conn, params=[date])
        if len(df_values_raw) == 0:
            continue
        values = df_values_raw["values"][0]
        if len(values) == n_points:
            valid_dates.append(date)

    return valid_dates

st.set_page_config(layout="wide")

# --- TITRE ---
st.title("📊 XYZ Data – Colorisation dynamique par données temporelles")

# --- RECHARGER LES DATES ---
if st.button("🔄 Recharger les dates disponibles"):
    st.rerun()

# --- RÉCUPÉRER LES DATES DISPONIBLES ---
df_valid_dates = pd.read_sql("SELECT DISTINCT date FROM data_fibre ORDER BY date", conn)


dates = get_valid_dates(conn)
st.success(f"✅ {len(dates)} dates valides chargées.")


if len(dates) == 0:
    st.error("❌ Aucune date disponible dans la base de données.")
    st.stop()

# --- SLIDER ---
index = st.slider("Sélectionnez une date", 0, len(dates)-1, 0)
selected_date = dates[index]
st.markdown(f"### 📅 Date sélectionnée : {selected_date}")

# --- RÉCUPÉRER LES DONNÉES ---
query = "SELECT values FROM data_fibre WHERE date = %s"
df_values_raw = pd.read_sql(query, conn, params=[selected_date])
values = df_values_raw["values"][0]
st.write("✅ Longueur de la liste 'values' :", len(values))
st.write("📊 Aperçu des valeurs :", values[:10])  # Montre les 10 premières valeurs


# --- RÉCUPÉRER XYZ ---
df_xyz = pd.read_sql("SELECT x, y, z FROM xyz_points ORDER BY id", conn)
st.write("✅ Nombre de points XYZ :", df_xyz.shape[0])


if len(values) != len(df_xyz):
    st.error("❌ Erreur : Nombre de valeurs ne correspond pas au nombre de points XYZ.")
    st.stop()

# --- AFFICHAGE PLOTLY ---
fig = go.Figure(data=[
    go.Scatter3d(
        x=df_xyz["x"],
        y=df_xyz["y"],
        z=df_xyz["z"],
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
    margin=dict(l=0, r=0, t=40, b=0),
    scene=dict(
        xaxis_title="X",
        yaxis_title="Y",
        zaxis_title="Z"
    )
)
st.plotly_chart(fig, use_container_width=True)

# --- FERMER LA CONNEXION ---
conn.close()
