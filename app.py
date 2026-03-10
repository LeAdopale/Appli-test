import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import polyline

# 1. Initialisation des variables dans le session_state si elles n'existent pas
if 'route_data' not in st.session_state:
    st.session_state.route_data = None
if 'coords' not in st.session_state:
    st.session_state.coords = None

st.title("🚗 Calculateur d'Itinéraire Persistant")

col1, col2 = st.columns([1, 3])

with col1:
    addr1 = st.text_input("Départ", "Tour Eiffel, Paris")
    addr2 = st.text_input("Arrivée", "Musée du Louvre, Paris")
    
    if st.button("Calculer l'itinéraire"):
        with st.spinner("Recherche..."):
            # Fonctions de géocodage et route (les mêmes qu'avant)
            c1 = geocode(addr1)
            c2 = geocode(addr2)
            
            if c1 and c2:
                points, dist, dur = get_route(c1, c2)
                # On stocke TOUT dans le session_state
                st.session_state.route_data = {"points": points, "dist": dist, "dur": dur}
                st.session_state.coords = (c1, c2)
            else:
                st.error("Adresses introuvables.")

with col2:
    # 2. On affiche la carte SI des données existent dans le session_state
    if st.session_state.route_data:
        data = st.session_state.route_data
        c1, c2 = st.session_state.coords
        
        st.success(f"Distance : {data['dist']:.2f} km | {data['dur']:.0f} min")
        
        m = folium.Map(location=c1, zoom_start=13)
        folium.Marker(c1, icon=folium.Icon(color='green')).add_to(m)
        folium.Marker(c2, icon=folium.Icon(color='red')).add_to(m)
        folium.PolyLine(data['points'], color="blue", weight=5).add_to(m)
        m.fit_bounds([c1, c2])
        
        # L'affichage reste stable car il lit dans st.session_state
        st_folium(m, width=700, height=500, key="main_map") 
    else:
        st.info("La carte s'affichera ici après le calcul.")
