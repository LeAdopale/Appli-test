import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import polyline

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="GPS Streamlit", layout="wide")

# --- FONCTIONS LOGIQUES ---

def geocode(adresse):
    """Convertit une adresse en coordonnées (lat, lon) via Nominatim"""
    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={adresse}"
        headers = {'User-Agent': 'my-streamlit-app-v1'}
        response = requests.get(url, headers=headers).json()
        if response:
            return float(response[0]['lat']), float(response[0]['lon'])
    except Exception as e:
        st.error(f"Erreur de géocodage : {e}")
    return None

def get_route(start_coords, end_coords):
    """Récupère l'itinéraire via l'API OSRM"""
    # OSRM utilise le format (longitude, latitude)
    loc = f"{start_coords[1]},{start_coords[0]};{end_coords[1]},{end_coords[0]}"
    url = f"http://router.project-osrm.org/route/v1/driving/{loc}?overview=full"
    try:
        response = requests.get(url).json()
        if response.get('code') == 'Ok':
            line = response['routes'][0]['geometry']
            points = polyline.decode(line)
            duration = response['routes'][0]['duration'] / 60  # minutes
            distance = response['routes'][0]['distance'] / 1000 # km
            return points, distance, duration
    except Exception as e:
        st.error(f"Erreur de calcul d'itinéraire : {e}")
    return None, None, None

# --- GESTION DE LA MÉMOIRE (SESSION STATE) ---
# On initialise les variables pour qu'elles persistent au rechargement de la page
if 'route_points' not in st.session_state:
    st.session_state.route_points = None
if 'distance' not in st.session_state:
    st.session_state.distance = None
if 'duration' not in st.session_state:
    st.session_state.duration = None
if 'coords' not in st.session_state:
    st.session_state.coords = None

# --- INTERFACE UTILISATEUR ---

st.title("🚗 Mon Calculateur d'Itinéraire")
st.markdown("Cette application calcule le trajet le plus rapide entre deux points.")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Paramètres")
    addr_dep = st.text_input("Départ", "Tour Eiffel, Paris")
    addr_arr = st.text_input("Arrivée", "Musée du Louvre, Paris")
    
    if st.button("Lancer le calcul", type="primary"):
        with st.spinner("Recherche d'itinéraire..."):
            c1 = geocode(addr_dep)
            c2 = geocode(addr_arr)
            
            if c1 and c2:
                points, dist, dur = get_route(c1, c2)
                if points:
                    # SAUVEGARDE dans le session_state
                    st.session_state.route_points = points
                    st.session_state.distance = dist
                    st.session_state.duration = dur
                    st.session_state.coords = (c1, c2)
                else:
                    st.error("Aucun itinéraire trouvé.")
            else:
                st.error("Une des adresses est introuvable.")

with col2:
    # On affiche la carte seulement si des données sont présentes en mémoire
    if st.session_state.route_points:
        st.success(f"📍 {st.session_state.distance:.2f} km | ⏱️ {st.session_state.duration:.0f} min")
        
        c1, c2 = st.session_state.coords
        
        # Création de la carte
        m = folium.Map(location=c1, zoom_start=13)
        
        # Ajout du tracé
        folium.PolyLine(
            st.session_state.route_points, 
            color="#31333F", 
            weight=5, 
            opacity=0.8
        ).add_to(m)
        
        # Ajout des marqueurs
        folium.Marker(c1, popup="Départ", icon=folium.Icon(color='green')).add_to(m)
        folium.Marker(c2, popup="Arrivée", icon=folium.Icon(color='red')).add_to(m)
        
        # Ajuster la vue pour voir tout le trajet
        m.fit_bounds([c1, c2])
        
        # Affichage du composant Folium
        # L'ajout d'une 'key' unique est crucial pour éviter les bugs d'affichage
        st_folium(m, width="100%", height=500, key="map_display")
    else:
        st.info("Entrez vos adresses à gauche pour générer la carte.")
