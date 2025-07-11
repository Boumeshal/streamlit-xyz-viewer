import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import psycopg2
import json
from datetime import datetime

# --- Connexion à Neon ---
conn = psycopg2.connect(
    dbname="neondb",
    user="neondb_owner",
    password="npg_GJ6XsHumk0Yz",
    host="ep-lucky-base-a22m3jwu-pooler.eu-central-1.aws.neon.tech",
    port=5432,
    sslmode="require"
)

# --- Débogage des dates valides ---
def get_valid_dates(conn):
    df_dates = pd.read_sql("SELECT DISTINCT date FROM data_fibre ORDER BY date", conn)
    df_xyz = pd.read_sql("SELECT x, y, z FROM xyz_points ORDER BY id", conn)
    n_points = len(df_xyz)

    valid_dates = []

    st.subheader("🔍 Débogage des dates valides")
    st.write(f"Nombre de points XYZ : {n_points}")
    st.write(f"Nombre total de dates brutes : {len(df_dates)}")

    for i, date in enumerate(df_dates["date"]):
        # Supprimer les millisecondes pour comparaison propre
        date_clean = date.replace(microsecond=0)

        query = "SELECT values FROM data_fibre WHERE date = %s"
        df_values_raw = pd.read_sql(query, conn, params=[date_clean])

        if df_values_raw.empty:
            st.warning(f"⚠️ Date {date_clean} → Aucune donnée trouvée.")
            continue

        raw = df_values_raw["values"][0]

        # Conversion JSON si nécessaire
        try:
            if isinstance(raw, str):
                values = json.loads(raw)
            else:
                values = raw
        except Exception as e:
            st.error(f"❌ Date {date_clean} → Erreur de parsing JSON : {e}")
            continue

        # Comparaison des tailles
        if len(values) == n_points:
            valid_dates.append(date_clean)
        else:
            st.error(f"🚨 Date {date_clean} → Taille mismatch : {len(values)} valeurs ≠ {n_points} XYZ")

    return valid_dates

# --- PAGE ---
st.set_page_config(layout="wide")
st.title("📊 XYZ Data – Colorisation dynamique par données temporelles")

# --- Bouton pour recharger ---
if st.button("🔄 Recharger les dates disponibles"):
    st.rerun()

# --- Chargement des dates valides ---
dates = get_valid_dates(conn)
st.success(f"✅ {len(dates)} dates valides chargées.")

if not dates:
    st.error("❌ Aucune date disponible dans la base de données.")
    st.stop()

# --- Sélection de la date ---
index = st.slider("Sélectionnez une date", 0, len(dates)-1, 0)
selected_date = dates[index]
st.markdown(f"### 📅 Date sélectionnée : {selected_date}")

# --- Données values ---
query = "SELECT values FROM data_fibre WHERE date = %s"
df_values_raw = pd.read_sql(query, conn, params=[selected_date])
raw = df_values_raw["values"][0]

# --- JSON parsing ---
try:
    if isinstance(raw, str):
        values = json.loads(raw)
    else:
        values = raw
except Exception as e:
    st.error(f"❌ Erreur de parsing JSON : {e}")
    st.stop()

# --- Points XYZ ---
df_xyz = pd.read_sql("SELECT x, y, z FROM xyz_points ORDER BY id", conn)

# --- Affichage des longueurs ---
st.subheader("🧪 Vérifications de cohérence")
st.write(f"🟢 Longueur des valeurs : {len(values)}")
st.write(f"🟢 Nombre de points XYZ : {len(df_xyz)}")

# --- Comparaison stricte ---
if len(values) != len(df_xyz):
    st.error("❌ Erreur : Nombre de valeurs ne correspond pas au nombre de points XYZ.")
    st.stop()

# --- Affichage Plotly ---
fig = go.Figure(data=[
    go.Scatter3d(
        x=df_xyz["x"], y=df_xyz["y"], z=df_xyz["z"],
        mode='markers',
        marker=dict(
            size=4,
            color=values,
            colorscale="Viridis",
            cmin=0,
            cmax=10000,
            opacity=0.85,
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

# --- Fermer la connexion ---
conn.close()
