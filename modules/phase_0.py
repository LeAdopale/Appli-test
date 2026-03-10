import osmnx as ox
import networkx as nx
import pandas as pd
import numpy as np
import os

def initialiser_graphe_routier(ville_ou_zone="Nantes, France", buffer_km=20):
    """
    Télécharge et prépare le graphe routier localement.
    Utilise un cache pour éviter de retélécharger à chaque fois.
    """
    cache_path = "./data/graph_nantes.graphml"
    
    if os.path.exists(cache_path):
        # Chargement du graphe sauvegardé
        G = ox.load_graphml(cache_path)
    else:
        # Téléchargement initial (profil 'drive' pour les camions/voitures)
        st.info(f"Téléchargement du graphe pour {ville_ou_zone}...")
        G = ox.graph_from_place(ville_ou_zone, network_type='drive', buffer_dist=buffer_km*1000)
        # On ajoute les vitesses et temps de trajet par défaut sur les arcs
        G = ox.add_edge_speeds(G)
        G = ox.add_edge_travel_times(G)
        # Sauvegarde locale
        if not os.path.exists("./data"): os.makedirs("./data")
        ox.save_graphml(G, cache_path)
        
    return G

def calculer_matrice_hors_ligne(G, df_sites):
    """
    Calcule la matrice de distances et temps entre tous les sites 
    en utilisant l'algorithme de Dijkstra sur le graphe local.
    """
    nodes = []
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
