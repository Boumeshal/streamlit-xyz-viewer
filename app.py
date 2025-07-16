# --- COURBE TEMPORAIRE DES VALEURS (TIME SERIES) ---
try:
    # Extraction de toutes les dates chargées
    time_series_dates = [d["date"] for d in st.session_state.loaded_dates]
    
    # Moyenne ou somme des valeurs à chaque date (selon ton usage)
    time_series_values = [sum(d["values"]) / len(d["values"]) for d in st.session_state.loaded_dates]

    # Création du graphique time series
    fig_ts = go.Figure()

    fig_ts.add_trace(go.Scatter(
        x=time_series_dates,
        y=time_series_values,
        mode="lines+markers",
        name="Valeurs moyennes",
        line=dict(color="blue"),
        marker=dict(size=6)
    ))

    # Ajout d'une ligne verticale pour la date sélectionnée
    fig_ts.add_vline(
        x=selected_data["date"],
        line=dict(color="red", width=2, dash="dash"),
        annotation_text="Sélection",
        annotation_position="top right"
    )

    fig_ts.update_layout(
        title="📈 Évolution des valeurs dans le temps (moyenne)",
        xaxis_title="Date",
        yaxis_title="Valeur moyenne",
        margin=dict(l=40, r=40, t=60, b=40),
        height=400
    )

    st.plotly_chart(fig_ts, use_container_width=True)

except Exception as e:
    st.error(f"❌ Erreur lors de la création du graphique temporel : {e}")
