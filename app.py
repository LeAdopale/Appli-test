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
