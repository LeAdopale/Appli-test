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
        
        # 1. Identification automatique de la colonne temporelle
        col_jour = None
        for candidat in ['Jour de passage', 'Jour', 'date', 'Journée']:
            if candidat in df_f.columns:
                col_jour = candidat
                break
        
        if col_jour:
            # 2. Préparation des données pour le graphique
            # On groupe par Jour et par Fonction Support pour voir la répartition
            df_grouped = df_f.groupby([col_jour, 'Fonction support'])['Nombre de contenants'].sum().reset_index()
            
            # Tri des jours pour un affichage chronologique (Lundi -> Dimanche)
            ordre_jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
            df_grouped[col_jour] = pd.Categorical(df_grouped[col_jour], categories=ordre_jours, ordered=True)
            df_grouped = df_grouped.sort_values(col_jour)
        
            # 3. Affichage du graphique immédiat
            fig = px.bar(
                df_grouped, 
                x=col_jour, 
                y="Nombre de contenants", 
                color="Fonction support",
                title="Volume total de contenants par jour et par service",
                barmode="group",
                text_auto='.2s'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            st.info("💡 Vérifiez que les volumes ci-dessus correspondent à vos attentes avant de valider.")
        else:
            st.warning("⚠️ Impossible de trouver une colonne 'Jour de passage' dans l'onglet M flux.")
            st.write("Colonnes détectées :", list(df_f.columns))
        
        # Le bouton de validation vient APRES le graphique
        if st.button("Valider ces données et configurer la flotte"):
            st.session_state['validated'] = True
            st.rerun() # Force le rafraîchissement pour afficher l'étape suivante

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
