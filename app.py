import streamlit as st
import pandas as pd
import plotly.express as px

# Configuration
st.set_page_config(page_title="Logistique CHU Nantes", layout="wide")

# --- FONCTION DE TRAITEMENT DES FLUX ---
def extraire_flux_hebdo(df):
    # Nettoyage des colonnes
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

    # Identification des colonnes clés
    col_support = next((c for c in df.columns if 'Support' in c), df.columns[2])
    col_direction = next((c for c in df.columns if 'Aller / Retour' in c or 'Direction' in c), None)
    
    # Liste des colonnes à garder avant de dépivoter
    cols_id = [c for c in df.columns if c not in cols_jours]
    
    # Dépivotage
    df_long = df.melt(id_vars=cols_id, value_vars=cols_jours, var_name='Jour_Brut', value_name='Volume')
    
    # Nettoyage du nom du jour
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

# --- UI ---
st.title("🚚 Analyse Détaillée des Flux Logistiques")

uploaded_file = st.sidebar.file_uploader("Charger le fichier Excel", type=["xlsx"])

if uploaded_file:
    all_data, error = load_all_data(uploaded_file)
    
    if not error:
        # On récupère l'onglet Flux
        onglet_flux = next((s for s in all_data.keys() if "flux" in s.lower()), None)
        df_propre = extraire_flux_hebdo(all_data[onglet_flux])
        
        if not df_propre.empty:
            # Paramètres d'affichage
            ordre_jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
            col_support = next((c for c in df_propre.columns if 'Support' in c), df_propre.columns[0])
            col_direction = next((c for c in df_propre.columns if 'Aller / Retour' in c), None)

            st.header("📊 Volume par Fonction Support")

            # Boucle pour créer un graphique par Service
            services = df_propre[col_support].unique()
            
            for svc in services:
                with st.expander(f"Analyse : {svc}", expanded=True):
                    df_svc = df_propre[df_propre[col_support] == svc]
                    
                    # Calcul des cumuls Aller / Retour
                    total_aller = df_svc[df_svc[col_direction] == 'Aller']['Volume'].sum() if col_direction else 0
                    total_retour = df_svc[df_svc[col_direction] == 'Retour']['Volume'].sum() if col_direction else 0
                    
                    # Affichage des KPI
                    c1, c2 = st.columns(2)
                    c1.metric("Cumul ALLER (Hebdo)", f"{int(total_aller)} rolls")
                    c2.metric("Cumul RETOUR (Hebdo)", f"{int(total_retour)} rolls")
                    
                    # Graphique
                    fig = px.bar(
                        df_svc, 
                        x='Jour', 
                        y='Volume', 
                        color=col_direction,
                        title=f"Flux quotidiens - {svc}",
                        category_orders={"Jour": ordre_jours},
                        barmode="group",
                        color_discrete_map={'Aller': '#3498db', 'Retour': '#e67e22'}, # Bleu pour Aller, Orange pour Retour
                        text_auto=True
                    )
                    st.plotly_chart(fig, use_container_width=True)

            if st.button("Valider et passer au paramétrage de la flotte"):
                st.session_state['step'] = 2
                st.rerun()

        # Étape 2 (Configuration Flotte)
        if st.session_state.get('step') == 2:
            st.success("Flux validés. Sélectionnez maintenant vos véhicules.")
            # ... (Le code de l'étape 3 précédent peut être inséré ici)
