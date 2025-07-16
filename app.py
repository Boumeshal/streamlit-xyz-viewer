import streamlit as st
import plotly.graph_objects as go
from datetime import datetime
import random

# Simulation de données chargées
if "loaded_dates" not in st.session_state:
    st.session_state.loaded_dates = [
        {
            "date": datetime(2025, 7, 10),
            "x": list(range(10)),
            "y": list(range(10)),
            "z": list(range(10)),
            "values": [random.randint(0, 100) for _ in range(10)]
        },
        {
            "date": datetime(2025, 7, 11),
            "x": list(range(10)),
            "y": list(range(10)),
            "z": list(range(10)),
            "values": [random.randint(0, 100) for _ in range(10)]
        },
        {
            "date": datetime(2025, 7, 12),
            "x": list(range(10)),
            "y": list(range(10)),
            "z": list(range(10)),
            "values": [random.randint(0, 100) for _ in range(10)]
        },
    ]

# --- Slider pour choisir une date ---
available_dates = [entry["date"] for entry in st.session_state.loaded_dates]
selected_date = st.select_slider(
    "Sélectionnez une date",
    options=available_dates,
    value=available_dates[-1],
    format_func=lambda d: d.strftime("%Y-%m-%d")
)

# Récupération des données associées à la date sélectionnée
selected_data = next((entry for entry in st.session_state.loaded_dates if entry["date"] == selected_date), None)

if selected_data:
    # --- Graphique 3D ---
    fig = go.Figure(data=[go.Scatter3d(
        x=selected_data["x"],
        y=selected_data["y"],
        z=selected_data["z"],
        mode='markers',
        marker=dict(
            size=5,
            color=selected_data["values"],
            colorscale='Viridis',
            opacity=0.8,
            colorbar=dict(title="Valeur")
        )
    )])
    fig.update_layout(
        title=f"Visualisation 3D - {selected_date.strftime('%Y-%m-%d')}",
        scene=dict(
            xaxis_title='X',
            yaxis_title='Y',
            zaxis_title='Z'
        ),
        margin=dict(l=0, r=0, t=50, b=0)
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- Graphique 2D SCATTER des valeurs ---
    scatter_fig = go.Figure(data=go.Scatter(
        x=list(range(len(selected_data["values"]))),
        y=selected_data["values"],
        mode='lines+markers',
        marker=dict(color='orange'),
        line=dict(color='orange'),
        name="Valeurs"
    ))

    scatter_fig.update_layout(
        title="📊 Valeurs brutes pour la date sélectionnée",
        xaxis_title="Index",
        yaxis_title="Valeur",
        height=400,
        margin=dict(l=40, r=40, t=60, b=40)
    )

    st.plotly_chart(scatter_fig, use_container_width=True)
else:
    st.warning("Aucune donnée disponible pour la date sélectionnée.")
