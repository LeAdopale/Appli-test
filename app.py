import streamlit as st
import pandas as pd
import plotly.express as px
import datetime

    
# Configuration de la page
st.set_page_config(page_title="Logistique CHU Nantes", layout="wide")

# --- FONCTION DE TRAITEMENT DES FLUX ---
def extraire_flux_hebdo(df):
    df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]
    jours_cibles = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    
    cols_jours = []
    for j in jours_cibles:
        for c in df.columns:
            if j.lower() in str(c).lower():
                cols_jours.append(c)
                break
    
    if not cols_jours:
        return pd.DataFrame()

    col_support = next((c for c in df.columns if 'Support' in c), df.columns[2])
    col_direction = next((c for c in df.columns if 'Aller / Retour' in c or 'Direction' in c), 'Aller / Retour')
    
    cols_id = [c for c in df.columns if c not in cols_jours]
    df_long = df.melt(id_vars=cols_id, value_vars=cols_jours, var_name='Jour_Brut', value_name='Volume')
    
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
        onglet_flux = next((s for s in all_data.keys() if "flux" in s.lower()), None)
        df_propre = extraire_flux_hebdo(all_data[onglet_flux])
        
        if not df_propre.empty:
            ordre_jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
            col_support = next((c for c in df_propre.columns if 'Support' in c), df_propre.columns[0])
            col_direction = next((c for c in df_propre.columns if 'Aller / Retour' in c), 'Aller / Retour')

            # --- 1. NOUVEAU GRAPHE : VUE GLOBALE EMPILEE ---
            st.header("🌍 Vue Globale : Charge Totale Cumulée")
            
            # Agrégation par Jour, Direction ET Fonction Support
            df_global = df_propre.groupby(['Jour', col_direction, col_support])['Volume'].sum().reset_index()
            
            fig_global = px.bar(
                df_global,
                x='Jour',
                y='Volume',
                color=col_support, # Code couleur par fonction
                facet_col=col_direction, # Sépare Aller et Retour en deux colonnes de graphe
                title="Besoin total en transport (Aller vs Retour) par Service",
                category_orders={"Jour": ordre_jours, col_direction: ["Aller", "Retour"]},
                barmode="stack", # Empilé
                text_auto='.0f'
            )
            
            fig_global.update_layout(yaxis_title="Total Contenants (Rolls)", height=500)
            st.plotly_chart(fig_global, use_container_width=True)
            
            st.divider()

            # --- 2. DÉTAIL PAR FONCTION SUPPORT ---
            st.header("📊 Détail par Fonction Support")
            services = sorted(df_propre[col_support].unique())
            
            for svc in services:
                with st.expander(f"Analyse des volumes : {svc}", expanded=False):
                    df_svc = df_propre[df_propre[col_support] == svc]
                    df_cumul = df_svc.groupby(['Jour', col_direction])['Volume'].sum().reset_index()
                    
                    fig = px.bar(
                        df_cumul, 
                        x='Jour', 
                        y='Volume', 
                        color=col_direction,
                        title=f"Total quotidien - {svc}",
                        category_orders={"Jour": ordre_jours},
                        barmode="group",
                        color_discrete_map={'Aller': '#3498db', 'Retour': '#e67e22'},
                        text_auto='.0f'
                    )
                    st.plotly_chart(fig, use_container_width=True)

            if st.button("Valider et passer à la configuration de la flotte"):
                st.session_state['step'] = 2
                st.rerun()

        # Étape suivante
        if st.session_state.get('step') == 2:
            st.success("Volumes validés. Paramétrez votre flotte.")

        # --- ÉTAPE 3 : CONFIGURATION DE LA SIMULATION ---
        if st.session_state.get('step') == 2:
            st.divider()
            st.header("⚙️ Paramétrage de la Simulation")
            
            # 1. Sélection de la Flotte
            st.subheader("1. Flotte de véhicules et capacité de charge")
            onglet_v = next((s for s in all_data.keys() if "Véhicule" in s), None)
            df_v = all_data[onglet_v].copy()
            
            # Nettoyage du nom de la colonne Poids
            col_poids = next((c for c in df_v.columns if "Poids max" in c or "PTAC" in c), None)
            
            selected_vehicles = []
            
            # Interface de sélection
            cols_h = st.columns([0.5, 2, 1.5, 1.5, 2])
            cols_h[0].write("**Actif**")
            cols_h[1].write("**Type de véhicule**")
            cols_h[2].write("**Charge Max (kg)**")
            cols_h[3].write("**Marge sécu (%)**")
            cols_h[4].write("**Impact Carbone**")

            for i, row in df_v.iterrows():
                c1, c2, c3, c4, c5 = st.columns([0.5, 2, 1.5, 1.5, 2])
                
                v_name = row['Types']
                is_active = c1.checkbox("", value=True, key=f"v_active_{i}")
                
                # Extraction du poids (on enlève "T" ou "kg" pour avoir un nombre)
                poids_str = str(row[col_poids]).lower().replace('t', '').replace('kg', '').replace(',', '.').strip()
                try:
                    poids_val = float(poids_str)
                    if "t" in str(row[col_poids]).lower(): poids_val *= 1000 # Conversion tonnes -> kg
                except:
                    poids_val = 0

                c2.write(f"**{v_name}**")
                c3.write(f"{int(poids_val)} kg")
                
                # Taux de remplissage / Marge
                taux = c4.number_input("Remplissage", 50, 100, 100, key=f"v_taux_{i}", label_visibility="collapsed")
                
                # Info Carbone
                c5.write(f"🍃 {row.get('Cout carbone (kg/km)', 0)} kg/km")

                if is_active:
                    selected_vehicles.append({
                        "id": v_name,
                        "poids_max": poids_val * (taux / 100),
                        "vitesse": 30, # Vitesse moyenne par défaut
                        "data_origine": row.to_dict()
                    })

            st.divider()

            # 3. Bouton final
            if st.button("🚀 LANCER LE CALCUL DES TOURNÉES", type="primary", use_container_width=True):
                if not selected_vehicles:
                    st.error("Veuillez sélectionner au moins un véhicule.")
                else:
                    st.session_state['selected_fleet'] = selected_vehicles
                    st.session_state['step'] = 3
                    st.rerun()
