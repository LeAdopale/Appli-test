import streamlit as st
import pandas as pd
import plotly.express as px

# Configuration
st.set_page_config(page_title="Logistique CHU - Optimisation", layout="wide")

## --- FONCTIONS UTILES ---
def load_data(file):
    expected = ["param Véhicules", "param Sites", "param Contenants", "param RH", "M flux"]
    try:
        dict_dfs = pd.read_excel(file, sheet_name=expected)
        return dict_dfs, None
    except Exception as e:
        return None, str(e)

## --- ETAPE 1 : ACCUEIL ---
st.title("🚚 Optimisation des Tournées de Distribution")

uploaded_file = st.sidebar.file_uploader("Charger le fichier de paramétrage", type=["xlsx"])

if uploaded_file:
    data, error = load_data(uploaded_file)
    
    if error:
        st.error(f"Fichier non conforme : {error}")
    else:
        st.success("Données chargées !")
        
        # Attribution des DataFrames
        df_v = data["param Véhicules"]
        df_f = data["M flux"]

        ## --- ETAPE 2 : CONTROLE DE COHERENCE ---
        st.header("📊 1. Contrôle des flux hebdomadaires")
        
        # On regroupe par Fonction Support et Jour pour l'histogramme
        # On suppose les colonnes 'Fonction support', 'Jour de passage' et 'Nombre de contenants'
        if 'Fonction support' in df_f.columns:
            fig = px.histogram(df_f, x="Jour de passage", y="Nombre de contenants", 
                               color="Fonction support", barmode="group",
                               title="Volume de contenants à distribuer par jour")
            st.plotly_chart(fig, use_container_width=True)
        
        if st.button("Valider les données d'entrée"):
            st.session_state['validated'] = True

        ## --- ETAPE 3 : CONFIGURATION DE LA FLOTTE ---
        if st.session_state.get('validated'):
            st.divider()
            st.header("⚙️ 2. Configuration de la simulation")
            st.subheader("Sélectionnez les véhicules disponibles et leur taux de remplissage")

            selected_vehicles = []
            
            # Création du tableau de sélection
            cols = st.columns([1, 2, 2, 2])
            cols[0].write("**Actif**")
            cols[1].write("**Type de véhicule**")
            cols[2].write("**Taux d'occupation max (%)**")
            cols[3].write("**Capacité (Rolls)**")

            for i, row in df_v.iterrows():
                c1, c2, c3, c4 = st.columns([1, 2, 2, 2])
                is_active = c1.checkbox("", value=True, key=f"check_{i}")
                type_v = row['Type de véhicule']
                c2.text(type_v)
                
                # Input pour le taux d'occupation (par défaut 100%)
                taux = c3.number_input("", min_value=10, max_value=100, value=100, step=5, key=f"taux_{i}")
                
                # Rappel de la capacité
                capa = row['Capacité en nombre de rolls']
                c4.text(f"{capa} rolls")

                if is_active:
                    selected_vehicles.append({
                        "type": type_v,
                        "taux_max": taux / 100,
                        "capa_rolls": capa,
                        "ptac": row['PTAC (kg)']
                    })

            if st.button("Lancer la Simulation", type="primary"):
                st.session_state['run_sim'] = True
                st.session_state['final_fleet'] = selected_vehicles

        ## --- ETAPE 4 : MOTEUR DE CALCUL (A VENIR) ---
        if st.session_state.get('run_sim'):
            st.info("🚀 Calcul de l'optimisation en cours... (Prochaine étape)")
            # Ici nous intégrerons la logique de calcul complexe
