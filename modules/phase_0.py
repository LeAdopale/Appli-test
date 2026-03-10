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
    """
    Transforme les adresses textuelles en coordonnées GPS.
    df_param_sites doit avoir : Col A (Nom) et Col B (Adresse)
    """
    geolocator = Nominatim(user_agent="chu_nantes_logistique")
    # RateLimiter permet de ne pas surcharger le serveur (1 requête/sec max)
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
    
    # Nettoyage des noms de colonnes
    df_param_sites.columns = [str(c).strip() for c in df_param_sites.columns]
    col_nom = df_param_sites.columns[0]
    col_adresse = df_param_sites.columns[1]
    
    st.info("Géocodage des adresses en cours (1 sec par adresse)...")
    
    lats, lons = [], []
    for addr in df_param_sites[col_adresse]:
        # On ajoute ", Nantes, France" si ce n'est pas précisé pour aider le moteur
        full_addr = addr if "nantes" in addr.lower() else f"{addr}, Nantes, France"
        location = geocode(full_addr)
        
        if location:
            lats.append(location.latitude)
            lons.append(location.longitude)
        else:
            st.warning(f"📍 Adresse non trouvée : {full_addr}")
            lats.append(None)
            lons.append(None)
            
    df_param_sites['Latitude'] = lats
    df_param_sites['Longitude'] = lons
    return df_param_sites.dropna(subset=['Latitude', 'Longitude'])


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
    Transforme les flux en 'Jobs' individuels basés sur les capacités réelles.
    """
    # Création d'un index pour retrouver les sites dans la matrice
    site_to_idx = {name: i for i, name in enumerate(df_sites['Nom_Site'])}
    
    jobs = []
    for idx, flux in df_flux.iterrows():
        # Atomisation si le volume dépasse la capacité d'un camion
        nb_splits = int(np.ceil(flux['Volume'] / capa_vehicule_max))
        
        i = site_to_idx[flux['Point de départ']]
        j = site_to_idx[flux['Point de destination']]
        
        for s in range(nb_splits):
            vol = capa_vehicule_max if s < nb_splits - 1 else (flux['Volume'] % capa_vehicule_max or capa_vehicule_max)
            
            jobs.append({
                'id_job': f"J_{idx}_{s}",
                'origine': flux['Point de départ'],
                'destination': flux['Point de destination'],
                'volume': vol,
                'poids': vol * 25, # Poids moyen arbitraire par roll (ex: 25kg)
                'dist_km': matrice_dist[i, j],
                'temps_min': matrice_temps[i, j],
                'fenetre_debut': flux['Heure de mise à disposition min départ'],
                'fenetre_fin': flux['Heure de livraison à destination']
            })
            
    return pd.DataFrame(jobs)
