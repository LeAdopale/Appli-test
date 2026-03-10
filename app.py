import math
import time
from typing import Dict, Optional, Tuple

import requests
import streamlit as st

# --------------------------------------------------
# Configuration générale
# --------------------------------------------------
st.set_page_config(
    page_title="Calcul de trajet",
    page_icon="🚗",
    layout="centered",
)

st.title("🚗 Calculateur de trajet")
st.write(
    "Entrez deux adresses pour calculer automatiquement la distance "
    "et la durée estimée du trajet routier le plus court disponible."
)

# Services publics utilisés
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving"

# User-Agent explicite recommandé pour Nominatim
HEADERS = {
    "User-Agent": "premiere-app-streamlit-trajet/1.0"
}


# --------------------------------------------------
# Fonctions utilitaires
# --------------------------------------------------
def geocode_address(address: str) -> Optional[Dict]:
    """
    Convertit une adresse texte en coordonnées via Nominatim.
    Retourne un dict avec display_name, lat, lon ou None si rien trouvé.
    """
    params = {
        "q": address,
        "format": "jsonv2",
        "limit": 1,
    }

    response = requests.get(
        NOMINATIM_URL,
        params=params,
        headers=HEADERS,
        timeout=20,
    )
    response.raise_for_status()

    results = response.json()
    if not results:
        return None

    first = results[0]
    return {
        "display_name": first.get("display_name", address),
        "lat": float(first["lat"]),
        "lon": float(first["lon"]),
    }


def get_route_osrm(
    start: Tuple[float, float],
    end: Tuple[float, float],
) -> Optional[Dict]:
    """
    Calcule un itinéraire routier via le serveur public OSRM.
    start/end = (lon, lat)
    Retourne distance_m, duration_s, geometry ou None.
    """
    start_lon, start_lat = start
    end_lon, end_lat = end

    url = (
        f"{OSRM_ROUTE_URL}/"
        f"{start_lon},{start_lat};{end_lon},{end_lat}"
    )

    params = {
        "overview": "false",
        "alternatives": "false",
        "steps": "false",
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()

    routes = data.get("routes", [])
    if not routes:
        return None

    route = routes[0]
    return {
        "distance_m": route.get("distance"),
        "duration_s": route.get("duration"),
    }


def format_distance(distance_m: float) -> str:
    if distance_m is None:
        return "-"
    if distance_m < 1000:
        return f"{round(distance_m)} m"
    return f"{distance_m / 1000:.1f} km"


def format_duration(duration_s: float) -> str:
    if duration_s is None:
        return "-"
    total_minutes = round(duration_s / 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours == 0:
        return f"{minutes} min"
    return f"{hours} h {minutes:02d} min"


def haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Distance à vol d'oiseau en km.
    Sert de secours si le routage échoue.
    """
    r = 6371.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


# --------------------------------------------------
# Formulaire
# --------------------------------------------------
with st.form("trajet_form"):
    adresse_depart = st.text_input(
        "Adresse de départ",
        placeholder="Ex. : 10 rue de Rivoli, Paris",
    )
    adresse_arrivee = st.text_input(
        "Adresse d'arrivée",
        placeholder="Ex. : 5 place Bellecour, Lyon",
    )

    submitted = st.form_submit_button("Calculer le trajet")

# --------------------------------------------------
# Traitement
# --------------------------------------------------
if submitted:
    if not adresse_depart.strip() or not adresse_arrivee.strip():
        st.warning("Merci de renseigner les deux adresses.")
        st.stop()

    if adresse_depart.strip().lower() == adresse_arrivee.strip().lower():
        st.warning("Les deux adresses doivent être distinctes.")
        st.stop()

    try:
        with st.spinner("Recherche des adresses..."):
            depart = geocode_address(adresse_depart.strip())
            time.sleep(1)  # évite d'enchaîner trop vite les appels publics
            arrivee = geocode_address(adresse_arrivee.strip())

        if not depart:
            st.error("Impossible de localiser l'adresse de départ.")
            st.stop()

        if not arrivee:
            st.error("Impossible de localiser l'adresse d'arrivée.")
            st.stop()

        with st.expander("Adresses interprétées"):
            st.write(f"**Départ** : {depart['display_name']}")
            st.write(f"**Arrivée** : {arrivee['display_name']}")

        with st.spinner("Calcul du trajet..."):
            route = get_route_osrm(
                (depart["lon"], depart["lat"]),
                (arrivee["lon"], arrivee["lat"]),
            )

        if route:
            col1, col2 = st.columns(2)
            col1.metric("Distance routière", format_distance(route["distance_m"]))
            col2.metric("Durée estimée", format_duration(route["duration_s"]))

            st.success("Trajet calculé avec succès.")
        else:
            st.warning(
                "Le calcul routier n'a pas abouti. "
                "Je te donne au moins la distance à vol d'oiseau."
            )
            distance_km = haversine_km(
                depart["lat"],
                depart["lon"],
                arrivee["lat"],
                arrivee["lon"],
            )
            st.metric("Distance à vol d'oiseau", f"{distance_km:.1f} km")

    except requests.HTTPError as e:
        st.error(f"Erreur HTTP lors de l'appel à un service externe : {e}")
    except requests.RequestException as e:
        st.error(f"Erreur réseau : {e}")
    except Exception as e:
        st.error(f"Une erreur inattendue est survenue : {e}")
