import streamlit as st
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
 
st.set_page_config(page_title="Calculateur de Trajet", page_icon="🚗")
 
st.title("📍 Calculateur de Distance")

st.subheader("Estimez la distance entre deux adresses")
 
# Entrées utilisateur

col1, col2 = st.columns(2)
with col1:

    addr1 = st.text_input("Adresse de départ", "Tour Eiffel, Paris")
with col2:

    addr2 = st.text_input("Adresse d'arrivée", "Musée du Louvre, Paris")
 
if st.button("Calculer l'itinéraire"):

    geolocator = Nominatim(user_agent="my_travel_app")
try:

        location1 = geolocator.geocode(addr1)

        location2 = geolocator.geocode(addr2)
 
        if location1 and location2:
# Coordonnées

            coord1 = (location1.latitude, location1.longitude)

            coord2 = (location2.latitude, location2.longitude)
# Calcul de la distance (vol d'oiseau)

            dist = geodesic(coord1, coord2).kilometers
# Estimation simple du temps (vitesse moyenne 60km/h)

            temps_estime = (dist / 60) * 60# en minutes# Affichage des résultats

            st.success(f"**Distance :** {dist:.2f} km")

            st.info(f"**Temps estimé (moyenne 60km/h) :** {temps_estime:.0f} min")
# Petite carte interactive

            st.map(data=[{"lat": coord1[0], "lon": coord1[1]}, {"lat": coord2[0], "lon": coord2[1]}])
         else:

            st.error("Impossible de trouver l'une des adresses.")
except Exception as e:

        st.error(f"Erreur : {e}")
 
