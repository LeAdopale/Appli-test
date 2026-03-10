import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import polyline

# Configuration de la page
st.set_page_config(page_title="Calculateur d'Itinéraire", layout="wide")

st.title("🚗 Calculateur d'Itinéraire Rapide")
st.markdown("Entrez deux adresses pour afficher le trajet le plus rapide sur la carte.")

# --- FONCTIONS UTILES ---

def geocode(adresse):
    """Convertit une adresse en coordonnées (lat, lon) via l'API Nominatim (OpenStreetMap)"""
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={adresse}"
    headers = {'User-Agent': 'my-streamlit-app'}
    response = requests.get(url, headers=headers).json()
    if response:
        return float(response[0]['lat']), float(response[0]['lon'])
    return None

def get_route(start_coords, end_coords):
    """Récupère l'itinéraire via l'API OSRM"""
    loc = f"{start_coords[1]},{start_coords[0]};{end_coords[1]},{end_coords[0]}"
    url = f"http://router.project-osrm.org/route/v1/driving/{loc}?overview=full"
    response = requests.get(url).json()
    if response['code'] == 'Ok':
        # Décodage de la géométrie de la route
        line = response['routes'][0]['geometry']
        points = polyline.decode(line)
        duration = response['routes'][0]['duration'] / 60  # en minutes
        distance = response['routes'][0]['distance'] / 1000 # en km
        return points, distance, duration
    return None, None, None

# --- INTERFACE UTILISATEUR ---

col1, col2 = st.columns([1, 3])

with col1:
    addr1 = st.text_input("Adresse de départ", "Tour Eiffel, Paris")
    addr2 = st.text_input("Adresse d'arrivée", "Musée du Louvre, Paris")
    btn = st.button("Calculer l'itinéraire")

with col2:
    if btn:
        with st.spinner("Calcul en cours..."):
            coords1 = geocode(addr1)
            coords2 = geocode(addr2)

            if coords1 and coords2:
                route_points, dist, dur = get_route(coords1, coords2)

                if route_points:
                    st.success(f"Distance : {dist:.2f} km | Temps estimé : {dur:.0f} min")
                    
                    # Création de la carte Folium
                    m = folium.Map(location=coords1, zoom_start=13)
                    
                    # Ajout des marqueurs
                    folium.Marker(coords1, tooltip="Départ", icon=folium.Icon(color='green')).add_to(m)
                    folium.Marker(coords2, tooltip="Arrivée", icon=folium.Icon(color='red')).add_to(m)
                    
                    # Ajout de la ligne du trajet
                    folium.PolyLine(route_points, color="blue", weight=5, opacity=0.7).add_to(m)
                    
                    # Ajustement automatique du zoom
                    m.fit_bounds([coords1, coords2])
                    
                    # Affichage dans Streamlit
                    st_folium(m, width=1000, height=500)
                else:
                    st.error("Impossible de calculer l'itinéraire.")
            else:
                st.error("Une des adresses n'a pas pu être trouvée.")
    else:
        st.info("Entrez vos adresses et cliquez sur le bouton pour voir la carte.")
