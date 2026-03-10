import streamlit as st
import pandas as pd
import plotly.express as px

# Configuration de la page
st.set_page_config(page_title="Logistique CHU Nantes", layout="wide")

# --- FONCTION DE TRAITEMENT DES FLUX ---
def extraire_flux_hebdo(df):
    # Nettoyage des colonnes (suppression des espaces et retours à la ligne)
    df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]
    
    jours_cibles = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    
    # Identification des colonnes jours
    cols_jours = []
    for j in jours_cibles:
        for c in df.columns:
            if j.lower() in str(c).lower():
                cols_jours.append(c)
                break
    
    if not cols_jours:
        return pd.DataFrame()

    # Identification des colonnes clés (Support et Direction)
    col_support = next((c for c in df.columns if 'Support' in c), df.columns[2])
    col_direction = next((c for c in df.columns if 'Aller / Retour' in c or 'Direction' in c), None)
    
    # Liste des colonnes à conserver avant le dépivotage
    cols_id = [c for c in df.columns if c not in cols_jours]
    
    # Transformation du tableau large en tableau long
    df_long = df.melt(id_vars=cols_id, value_vars=cols_jours, var_name='Jour_Brut', value_name='Volume')
    
    # Nettoyage du nom du jour pour l'uniformiser
    def clean_day(x):
        for j in jours_cibles:
            if j.lower() in str(x).lower(): return j
        return x

    df_long['Jour'] = df_long['Jour_Brut'].apply(clean_day)
    df_long['Volume'] = pd.to_numeric(df_long['Volume'], errors='coerce').fillna(0)
    
    return df_long[df_long['Volume'] > 0]

@st.cache_data
def load_all_data(file):
    xl = pd.ExcelFile(file)
    return {sheet: xl.parse(sheet) for sheet in xl.sheet_names}, None

# --- INTERFACE UTILISATEUR ---
st.title("🚚 Pilotage des Flux Logistiques")

uploaded_file = st.sidebar.file_uploader("Charger le fichier Excel de paramétrage", type=["xlsx"])

if uploaded_file:
    all_data, error = load_all_data(uploaded_file)
    
    if not error:
        # Récupération de l'onglet Flux
        onglet_flux = next((s for s in all_data.keys() if "flux" in s.lower()), None)
        df_propre = extraire_flux_hebdo(all_data[onglet_flux])
        
        if not df_propre.empty:
            st.header("📊 Cumul Quotidien par Fonction Support")

            # Paramètres de tri et de couleur
            ordre_jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
            col_support = next((c for c in df_propre.columns if 'Support' in c), df_propre.columns[0])
            col_direction = next((c for c in df_propre.columns if 'Aller / Retour' in c), 'Aller / Retour')

            # Boucle de génération des graphiques par Service
            services = sorted(df_propre[col_support].unique())
            
            for svc in services:
                with st.expander(f"Analyse des volumes : {svc}", expanded=True):
                    df_svc = df_propre[df_propre[col_support] == svc]
                    
                    # GROUPBY pour obtenir le cumul quotidien par direction
                    df_cumul = df_svc.groupby(['Jour', col_direction])['Volume'].sum().reset_index()
                    
                    # Graphique à barres groupées (Cumul par Jour)
                    fig = px.bar(
                        df_cumul, 
                        x='Jour', 
                        y='Volume', 
                        color=col_direction,
                        title=f"Total quotidien des flux - {svc}",
                        category_orders={"Jour": ordre_jours},
                        barmode="group",
                        color_discrete_map={'Aller': '#3498db', 'Retour': '#e67e22'},
                        text_auto='.0f' # Affiche le cumul arrondi sur la barre
                    )
                    
                    fig.update_layout(yaxis_title="Nombre total de contenants", xaxis_title="")
                    st.plotly_chart(fig, use_container_width=True)

            if st.button("Valider et passer à la configuration de la flotte"):
                st.session_state['step'] = 2
                st.rerun()

        # Étape 2 : Configuration de la flotte
        if st.session_state.get('step') == 2:
            st.success("Volumes validés. Paramétrez votre flotte de véhicules.")
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
