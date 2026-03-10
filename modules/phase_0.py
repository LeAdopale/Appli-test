import osmnx as ox
import networkx as nx
import pandas as pd
import numpy as np
import os
import streamlit as st
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

def geocoder_sites(df_param_sites):
    geolocator = Nominatim(user_agent="chu_nantes_logistique")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
    
    # Nettoyage des colonnes
    df_param_sites.columns = [str(c).strip() for c in df_param_sites.columns]
    col_nom = df_param_sites.columns[0]
    col_adresse = df_param_sites.columns[1]
    
    lats, lons = [], []
    adresses_en_echec = []

    for _, row in df_param_sites.iterrows():
        nom = row[col_nom]
        addr = str(row[col_adresse]).strip()
        
        # On ajoute juste "France" si ce n'est pas déjà présent pour la précision
        # On ne force plus "Nantes" car vos adresses sont complètes
        full_addr = addr if "france" in addr.lower() else f"{addr}, France"
        
        try:
            # On tente de trouver l'adresse
            location = geocode(full_addr)
            if location:
                lats.append(location.latitude)
                lons.append(location.longitude)
            else:
                # Si échec, on tente sans le "France" au cas où
                location_bis = geocode(addr)
                if location_bis:
                    lats.append(location_bis.latitude)
                    lons.append(location_bis.longitude)
                else:
                    lats.append(None)
                    lons.append(None)
                    adresses_en_echec.append({"Site": nom, "Adresse": addr, "Erreur": "Non trouvé"})
        except Exception as e:
            lats.append(None)
            lons.append(None)
            adresses_en_echec.append({"Site": nom, "Adresse": addr, "Erreur": str(e)})
            
    df_param_sites['Latitude'] = lats
    df_param_sites['Longitude'] = lons
    return df_param_sites, adresses_en_echec

def initialiser_graphe_routier(ville_ou_zone="Nantes, France"):
    cache_path = "./data/graph_nantes_large.graphml" # On change le nom du cache
    if os.path.exists(cache_path):
        return ox.load_graphml(cache_path)
    
    try:
        # On télécharge avec un buffer de 25km autour du centre de Nantes
        st.info("Téléchargement de la carte (zone étendue 40km)...")
        G = ox.graph_from_address(ville_ou_zone, dist=40000, network_type='drive')
        G = ox.add_edge_speeds(G)
        G = ox.add_edge_travel_times(G)
        if not os.path.exists("./data"): os.makedirs("./data")
        ox.save_graphml(G, cache_path)
        return G
    except Exception as e:
        st.error(f"Erreur OSM : {e}")
        return None

def calculer_matrice_hors_ligne(G, df_param_sites):
    # 1. Géocodage
    df_gps, erreurs = geocoder_sites(df_param_sites)
    if erreurs:
        st.session_state['geocoding_errors'] = erreurs
    
    # 2. Filtrage des sites valides (ceux qui ont des coordonnées)
    df_valides = df_gps.dropna(subset=['Latitude', 'Longitude']).copy()
    
    if df_valides.empty:
        st.error("❌ Aucun site n'a pu être localisé.")
        return None, None, None

    # 3. Projection sur le graphe et création d'un mapping ID_SITE -> INDEX_MATRICE
    nodes = []
    mapping_site_index = {} # Pour faire le lien propre avec les flux
    nom_col_site = df_valides.columns[0]

    for idx, (idx_df, row) in enumerate(df_valides.iterrows()):
        try:
            node = ox.nearest_nodes(G, X=float(row['Longitude']), Y=float(row['Latitude']))
            nodes.append(node)
            # On lie le nom du site (ex: 'Hôtel Dieu') à sa position dans la future matrice (ex: 0)
            mapping_site_index[str(row[nom_col_site]).strip()] = idx
        except:
            continue

    # 4. Calcul de la matrice
    num_n = len(nodes)
    mat_dist = np.zeros((num_n, num_n))
    mat_temps = np.zeros((num_n, num_n))
    
    for i in range(num_n):
        for j in range(num_n):
            if i == j: continue
            try:
                mat_temps[i, j] = nx.shortest_path_length(G, nodes[i], nodes[j], weight='travel_time') / 60
                mat_dist[i, j] = nx.shortest_path_length(G, nodes[i], nodes[j], weight='length') / 1000
            except:
                mat_temps[i, j], mat_dist[i, j] = 999, 999

    # On renvoie le mapping pour que generer_jobs puisse s'y retrouver
    return mat_dist, mat_temps, mapping_site_index

def generer_jobs_atomises(df_flux, mapping_site_index, matrice_dist, matrice_temps, capa_max):
    col_dep = next((c for c in df_flux.columns if "départ" in str(c).lower()), df_flux.columns[0])
    col_arr = next((c for c in df_flux.columns if "destination" in str(c).lower()), df_flux.columns[1])
    col_vol = next((c for c in df_flux.columns if "vol" in str(c).lower()), None)
    if col_vol is None:
        st.error(f"Impossible de trouver une colonne 'Volume' dans l'onglet flux. Colonnes dispos : {list(df_flux.columns)}")
        return pd.DataFrame()

    jobs = []
    for idx, flux in df_flux.iterrows():
        try:
            orig_name = str(flux[col_dep]).strip()
            dest_name = str(flux[col_arr]).strip()
            
            # On utilise le mapping issu de calculer_matrice_hors_ligne
            i = mapping_site_index[orig_name]
            j = mapping_site_index[dest_name]
            
            vol_tot = float(flux[col_vol])
            if vol_tot <= 0: continue
            
            nb_splits = int(np.ceil(vol_tot / capa_max))
            for s in range(nb_splits):
                v_unit = capa_max if s < nb_splits - 1 else (vol_tot % capa_max or capa_max)
                jobs.append({
                    'id_job': f"J_{idx}_{s}",
                    'origine': orig_name,
                    'destination': dest_name,
                    'volume': v_unit,
                    'dist_km': matrice_dist[i, j],
                    'temps_min': matrice_temps[i, j],
                    'h_dep': flux.get('Heure de mise à disposition min départ', "08:00"),
                    'h_arr': flux.get('Heure de livraison à destination', "18:00")
                })
        except KeyError:
            # Le site n'est pas dans le mapping (soit absent de l'Excel, soit échec géocodage)
            continue
            
    return pd.DataFrame(jobs)
