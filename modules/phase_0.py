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

def calculer_matrice_hors_ligne(G, df_sites):
    """
    Calcule la matrice de distances et temps entre tous les sites 
    en utilisant l'algorithme de Dijkstra sur le graphe local.
    """

    # Étape de géocodage
    df_gps = geocoder_sites(df_param_sites)
    
    nodes = []
    for _, row in df_gps.iterrows():
        node = ox.nearest_nodes(G, X=row['Longitude'], Y=row['Latitude'])
        nodes.append(node)
        
    # 1. On projette chaque site (lat, lon) sur le noeud du graphe le plus proche
    for _, row in df_sites.iterrows():
        node = ox.nearest_nodes(G, X=row['Longitude'], Y=row['Latitude'])
        nodes.append(node)
    
    num_sites = len(nodes)
    matrice_dist = np.zeros((num_sites, num_sites))
    matrice_temps = np.zeros((num_sites, num_sites))
    
    # 2. Calcul des plus courts chemins (All-pairs shortest path simplifié)
    for i in range(num_sites):
        for j in range(num_sites):
            if i == j: continue
            
            # Calcul du chemin le plus court en temps
            try:
                # nx.shortest_path_length utilise l'attribut 'travel_time' ajouté par OSMnx
                temps_sec = nx.shortest_path_length(G, nodes[i], nodes[j], weight='travel_time')
                dist_metres = nx.shortest_path_length(G, nodes[i], nodes[j], weight='length')
                
                matrice_temps[i, j] = temps_sec / 60  # Conversion minutes
                matrice_dist[i, j] = dist_metres / 1000 # Conversion km
            except nx.NetworkXNoPath:
                matrice_temps[i, j] = 9999 # Chemin impossible
                matrice_dist[i, j] = 9999
                
    return matrice_dist, matrice_temps

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
