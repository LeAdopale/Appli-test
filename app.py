import streamlit as st
import pandas as pd
import plotly.express as px

# Configuration de la page
st.set_page_config(page_title="Logistique CHU Nantes", layout="wide")

# --- FONCTIONS DE TRAITEMENT ---

def extraire_flux_hebdo(df):
    """
    Détecte les colonnes Lundi-Dimanche et transforme le tableau 
    pour avoir une ligne par flux/jour.
    """
    # Nettoyage des noms de colonnes (espaces, sauts de ligne)
    df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]
    
    jours_cibles = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    
    # Trouver les colonnes qui contiennent un jour de la semaine
    cols_jours = []
    for j in jours_cibles:
        for c in df.columns:
            if j.lower() in c.lower():
                cols_jours.append(c)
                break
    
    if not cols_jours:
        return pd.DataFrame()

    # Identifier la colonne Service/Fonction (généralement la 3ème ou celle nommée 'Fonction')
    col_service = next((c for c in df.columns if 'Fonction' in c or 'Support' in c), df.columns[0])
    
    # Garder les colonnes descriptives + les jours
    cols_fixes = [c for c in df.columns if c not in cols_jours]
    
    # Dépivotage (Wide to Long)
    df_long = df.melt(
        id_vars=cols_fixes, 
        value_vars=cols_jours,
        var_name='Jour_Brut', 
        value_name='Volume'
    )

    # Nettoyage du nom du jour (pour enlever les "Quantité " devant)
    def clean_day(x):
        for j in jours_cibles:
            if j.lower() in x.lower(): return j
        return x

    df_long['Jour'] = df_long['Jour_Brut'].apply(clean_day)
    df_long['Volume'] = pd.to_numeric(df_long['Volume'], errors='coerce').fillna(0)
    
    # On ne garde que les flux avec un volume > 0
    return df_long[df_long['Volume'] > 0]

@st.cache_data
def load_all_data(file):
    """Charge tous les onglets nécessaires"""
    try:
        xl = pd.ExcelFile(file)
        data = {sheet: xl.parse(sheet) for sheet in xl.sheet_names}
        return data, None
    except Exception as e:
        return None, str(e)

# --- INTERFACE UTILISATEUR ---

st.title("🚚 Optimisateur Logistique CHU")

uploaded_file = st.sidebar.file_uploader("Charger le fichier Excel de paramétrage", type=["xlsx"])

if uploaded_file:
    all_data, error = load_all_data(uploaded_file)
    
    if error:
        st.error(f"Erreur de lecture : {error}")
    else:
        # Vérification de l'onglet M flux
        onglet_flux = next((s for s in all_data.keys() if "flux" in s.lower()), None)
        
        if onglet_flux:
            df_flux_raw = all_data[onglet_flux]
            df_propre = extraire_flux_hebdo(df_flux_raw)
            
            if not df_propre.empty:
                st.header("📊 Analyse des volumes par jour")
                
                # Graphique de contrôle
                ordre_jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
                col_couleur = 'Fonction Support associée' if 'Fonction Support associée' in df_propre.columns else df_propre.columns[0]
                
                fig = px.bar(
                    df_propre, 
                    x='Jour', 
                    y='Volume', 
                    color=col_couleur,
                    title="Cumul des contenants à transporter",
                    category_orders={"Jour": ordre_jours},
                    barmode="group",
                    text_auto=True
                )
                st.plotly_chart(fig, use_container_width=True)
                
                st.session_state['df_flux_final'] = df_propre
                
                # --- ÉTAPE SUIVANTE : FLOTTE ---
                if st.button("Valider les volumes et configurer la flotte"):
                    st.session_state['step'] = 2
            else:
                st.error("Impossible de détecter les colonnes de jours (Lundi, Mardi...) dans l'onglet Flux.")
        
        # Affichage de la configuration de la flotte si validé
        if st.session_state.get('step') == 2:
            st.divider()
            st.header("⚙️ Configuration de la Flotte")
            onglet_v = next((s for s in all_data.keys() if "Véhicule" in s), None)
            
            if onglet_v:
                df_v = all_data[onglet_v]
                selected_v = []
                
                st.write("Sélectionnez les véhicules actifs pour la simulation :")
                for i, row in df_v.iterrows():
                    c1, c2, c3 = st.columns([1, 3, 2])
                    actif = c1.checkbox("", value=True, key=f"v_{i}")
                    c2.write(f"**{row.iloc[0]}**")
                    taux = c3.slider("Taux de remplissage max (%)", 50, 100, 100, key=f"t_{i}")
                    
                    if actif:
                        selected_v.append({"type": row.iloc[0], "taux": taux})
                
                if st.button("Lancer la simulation des tournées", type="primary"):
                    st.success("Moteur de calcul prêt à être lancé (Étape 4) !")
else:
    st.info("👋 Veuillez charger votre fichier Excel dans la barre latérale pour commencer.")
