import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import psycopg2

# --- Connexion à Neon ---
conn = psycopg2.connect(
    dbname="neondb",
    user="neondb_owner",
    password="npg_GJ6XsHumk0Yz",
    host="ep-lucky-base-a22m3jwu-pooler.eu-central-1.aws.neon.tech",
    port=5432,
    sslmode="require"
)

# --- Charger les points XYZ ---
df_xyz = pd.read_sql("SELECT x, y, z FROM xyz_points ORDER BY id", conn)
n_points = df_xyz.shape[0]

# --- Charger uniquement les dates valides ---
df_valid_dates = pd.read_sql(f"""
    SELECT date FROM data_fibre
    WHERE array_length(values, 1) = {n_points}
    ORDER BY date
""", conn)

dates = df_valid_dates["date"].tolist()

# --- Interface Streamlit ---
st.title("XYZ Data – Colorisation dynamique par données temporelles")

# Slider pour sélectionner une date
index = st.slider("Sélectionnez une date", 0, len(dates) - 1, 0)
selected_date = dates[index]
st.markdown(f"**Date sélectionnée : {selected_date}**")

# Requête SQL pour récupérer les valeurs à cette date
query = "SELECT values FROM data_fibre WHERE date = %s"
df = pd.read_sql(query, conn, params=[selected_date])

# --- Sécurité : Vérifier le bon nombre de valeurs ---
values = df["values"].iloc[0]
if len(values) != n_points:
    st.error("Erreur : Nombre de valeurs ne correspond pas au nombre de points XYZ.")
else:
    # --- Tracer ---
    fig = go.Figure(
        data=[
            go.Scatter3d(
                x=df_xyz["x"], y=df_xyz["y"], z=df_xyz["z"],
                mode="markers",
                marker=dict(
                    size=4,
                    color=values,
                    colorscale="Viridis",
                    cmin=0,
                    cmax=10000,
                    opacity=0.85,
                    colorbar=dict(title="Valeur")
                ),
                hovertemplate=(
                    "<b>X</b>: %{x:.2f}<br><b>Y</b>: %{y:.2f}"
                    "<br><b>Z</b>: %{z:.2f}<br><b>Valeur</b>: %{marker.color:.2f}<extra></extra>"
                )
            )
        ],
        layout=go.Layout(
            scene=dict(
                xaxis=dict(title="X"),
                yaxis=dict(title="Y"),
                zaxis=dict(title="Z"),
            ),
            margin=dict(l=0, r=0, t=40, b=0),
            template="simple_white"
        )
    )
    st.plotly_chart(fig, use_container_width=True)

# --- Fermer la connexion ---
conn.close()
