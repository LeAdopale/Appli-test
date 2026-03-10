import osmnx as ox
import networkx as nx
import pandas as pd
import numpy as np
import os
import streamlit as st
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import time

def geocoder_sites(df_param_sites):
    geolocator = Nominatim(user_agent="chu_nantes_logistique")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
    
    df_param_sites.columns = [str(c).strip() for c in df_param_sites.columns]
    col_nom = df_param_sites.columns[0]
    col_adresse = df_param_sites.columns[1]
    
    lats, lons = [], []
    adresses_en_echec = [] # <-- Liste pour capturer les erreurs

    for _, row in df_param_sites.iterrows():
        nom = row[col_nom]
        addr = row[col_adresse]
        full_addr = addr if "nantes" in addr.lower() else f"{addr}, Nantes, France"
        
        try:
            location = geocode(full_addr)
            if location:
                lats.append(location.latitude)
                lons.append(location.longitude)
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
    
    # On renvoie le DF complet ET la liste des erreurs
    return df_param_sites, adresses_en_echec


def initialiser_graphe_routier(ville_ou_zone="Nantes, France", buffer_km=40):
    cache_path = "./data/graph_nantes.graphml"
    
    if os.path.exists(cache_path):
        G = ox.load_graphml(cache_path)
    else:
        st.info(f"Téléchargement initial du graphe pour {ville_ou_zone}...")
        
        # Correction ici : on utilise graph_from_place sans le buffer_dist problématique
        # ou on utilise graph_from_address avec une distance explicite.
        try:
            # Approche la plus stable :
            G = ox.graph_from_place(ville_ou_zone, network_type='drive')
            
            # Si vous avez vraiment besoin d'un buffer plus large que les limites de la ville :
            # G = ox.graph_from_address(ville_ou_zone, dist=buffer_km*1000, network_type='drive')
            
        except Exception as e:
            st.error(f"Erreur lors du téléchargement OSM : {e}")
            return None

        G = ox.add_edge_speeds(G)
        G = ox.add_edge_travel_times(G)
        
        if not os.path.exists("./data"): 
            os.makedirs("./data")
        ox.save_graphml(G, cache_path)
        
    return G

def calculer_matrice_hors_ligne(G, df_param_sites):
    # 1. Géocodage
    df_gps = geocoder_sites(df_param_sites)
    
    # 2. Sécurité : On ne garde QUE les lignes où Lat/Lon ne sont pas nulles
    df_gps = df_gps.dropna(subset=['Latitude', 'Longitude'])
    
    if df_gps.empty:
        st.error("❌ Aucun site n'a pu être localisé sur la carte. Vérifiez le format des adresses.")
        return None, None

    nodes = []
    for idx, row in df_gps.iterrows():
        try:
            # Conversion explicite et vérification
            lon = float(row['Longitude'])
            lat = float(row['Latitude'])
            
            # Projection sur le graphe
            node = ox.nearest_nodes(G, X=lon, Y=lat)
            nodes.append(node)
        except Exception as e:
            st.warning(f"⚠️ Impossible de projeter le site {idx} sur la route : {e}")
            continue
            
    # 3. Calcul de la matrice entre les noeuds valides
    num_nodes = len(nodes)
    mat_dist = np.zeros((num_nodes, num_nodes))
    mat_temps = np.zeros((num_nodes, num_nodes))
    
    for i in range(num_nodes):
        for j in range(num_nodes):
            if i == j: continue
            try:
                # Calcul Dijkstra
                mat_temps[i, j] = nx.shortest_path_length(G, nodes[i], nodes[j], weight='travel_time') / 60
                mat_dist[i, j] = nx.shortest_path_length(G, nodes[i], nodes[j], weight='length') / 1000
            except nx.NetworkXNoPath:
                mat_temps[i, j] = 999
                mat_dist[i, j] = 999

    return mat_dist, mat_temps

def generer_jobs_atomises(df_flux, df_sites, matrice_dist, matrice_temps, capa_vehicule_max):
    """
    Transforme les flux en 'Jobs' individuels.
    Utilise l'ordre des colonnes pour éviter les KeyError sur les noms.
    """
    # 1. On nettoie les espaces dans les noms de colonnes de df_sites
    df_sites.columns = [str(c).strip() for c in df_sites.columns]
    
    # On suppose que la colonne 0 est le NOM du site (ex: 'Hôtel Dieu')
    nom_col_site = df_sites.columns[0]
    
    # Création du dictionnaire de correspondance : { 'Hôtel Dieu': 0, 'Laënnec': 1, ... }
    site_to_idx = {name: i for i, name in enumerate(df_sites[nom_col_site])}
    
    # Identification des colonnes dans df_flux (Aller/Retour, Départ, Arrivée, Volume)
    # On cherche les colonnes par mots-clés pour être robuste
    col_dep = next((c for c in df_flux.columns if "départ" in str(c).lower()), df_flux.columns[0])
    col_arr = next((c for c in df_flux.columns if "destination" in str(c).lower()), df_flux.columns[1])
    col_vol = next((c for c in df_flux.columns if "volume" in str(c).lower()), "Volume")

    jobs = []
    for idx, flux in df_flux.iterrows():
        # Calcul du nombre de "morceaux" de flux (split)
        volume_total = float(flux[col_vol])
        if volume_total <= 0: continue
            
        nb_splits = int(np.ceil(volume_total / capa_vehicule_max))
        
        # Récupération des indices dans la matrice
        try:
            i = site_to_idx[str(flux[col_dep]).strip()]
            j = site_to_idx[str(flux[col_arr]).strip()]
        except KeyError as e:
            st.warning(f"⚠️ Le site '{e}' présent dans les flux est inconnu dans l'onglet 'param Sites'.")
            continue
        
        for s in range(nb_splits):
            vol_unitaire = capa_vehicule_max if s < nb_splits - 1 else (volume_total % capa_vehicule_max or capa_vehicule_max)
            
            jobs.append({
                'id_job': f"J_{idx}_{s}",
                'origine': flux[col_dep],
                'destination': flux[col_arr],
                'volume': vol_unitaire,
                'dist_km': matrice_dist[i, j],
                'temps_min': matrice_temps[i, j],
                # On garde les fenêtres horaires si elles existent, sinon valeurs par défaut
                'h_dep': flux.get('Heure de mise à disposition min départ', "08:00"),
                'h_arr': flux.get('Heure de livraison à destination', "18:00")
            })
            
    return pd.DataFrame(jobs)
