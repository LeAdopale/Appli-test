import time
import requests
import streamlit as st

# -----------------------------
# Configuration de la page
# -----------------------------
st.set_page_config(
    page_title="Calculateur de trajet",
    page_icon="🚗",
    layout="centered"
)

st.title("🚗 Calculateur de trajet")
st.write("Saisissez deux adresses pour calculer automatiquement la distance et la durée du trajet le plus court.")

# -----------------------------
# Paramètres / constantes
# -----------------------------
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
ORS_DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/driving-car"

# IMPORTANT :
# ajoutez votre clé API OpenRouteService dans .streamlit/secrets.toml :
# ORS_API_KEY = "votre_cle_api"

ORS_API_KEY = st.secrets.get("ORS_API_KEY", None)

if not ORS_API_KEY:
    st.error(
        "Clé API manquante. Ajoutez `ORS_API_KEY` dans votre fichier `.streamlit/secrets.toml`."
    )
    st.stop()


# -----------------------------
# Fonctions utilitaires
# -----------------------------
def geocode_address(address: str):
    """
    Convertit une adresse texte en coordonnées (lat, lon) via Nominatim.
    """
    headers = {
        # Nominatim demande un User-Agent explicite
        "User-Agent": "streamlit-calcul-trajet/1.0 (contact: example@example.com)"
    }
    params = {
        "q": address,
        "format": "jsonv2",
        "limit": 1
    }

    response = requests.get(
        NOMINATIM_URL,
        params=params,
        headers=headers,
        timeout=20
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


def get_shortest_route(start_lon, start_lat, end_lon, end_lat):
    """
    Calcule l'itinéraire via OpenRouteService
    avec préférence = shortest.
    """
    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "coordinates": [
            [start_lon, start_lat],
            [end_lon, end_lat]
        ],
        "preference": "shortest",
        "instructions": False
    }

    response = requests.post(
        ORS_DIRECTIONS_URL,
        json=payload,
        headers=headers,
        timeout=30
    )
    response.raise_for_status()

    data = response.json()

    routes = data.get("routes", [])
    if not routes:
        return None

    summary = routes[0].get("summary", {})
    distance_m = summary.get("distance")
    duration_s = summary.get("duration")

    return {
        "distance_m": distance_m,
        "duration_s": duration_s
    }


def format_distance(distance_m: float) -> str:
    if distance_m is None:
        return "-"
    if distance_m < 1000:
        return f"{distance_m:.0f} m"
    return f"{distance_m / 1000:.2f} km"


def format_duration(duration_s: float) -> str:
    if duration_s is None:
        return "-"
    total_minutes = round(duration_s / 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours == 0:
        return f"{minutes} min"
    return f"{hours} h {minutes:02d} min"


# -----------------------------
# Interface utilisateur
# -----------------------------
with st.form("trajet_form"):
    adresse_depart = st.text_input(
        "Adresse de départ",
        placeholder="Ex. : 10 rue de Rivoli, Paris"
    )
    adresse_arrivee = st.text_input(
        "Adresse d'arrivée",
        placeholder="Ex. : 5 place Bellecour, Lyon"
    )

    submitted = st.form_submit_button("Calculer le trajet")

# -----------------------------
# Traitement
# -----------------------------
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
            # petite pause par précaution vis-à-vis de Nominatim
            time.sleep(1)
            arrivee = geocode_address(adresse_arrivee.strip())

        if not depart:
            st.error("Impossible de localiser l'adresse de départ.")
            st.stop()

        if not arrivee:
            st.error("Impossible de localiser l'adresse d'arrivée.")
            st.stop()

        st.success("Adresses trouvées.")

        with st.expander("Voir les adresses interprétées", expanded=False):
            st.write(f"**Départ :** {depart['display_name']}")
            st.write(f"**Arrivée :** {arrivee['display_name']}")

        with st.spinner("Calcul du trajet le plus court..."):
            route = get_shortest_route(
                depart["lon"], depart["lat"],
                arrivee["lon"], arrivee["lat"]
            )

        if not route:
            st.error("Aucun trajet routier n'a pu être calculé entre ces deux adresses.")
            st.stop()

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Distance", format_distance(route["distance_m"]))
        with col2:
            st.metric("Durée estimée", format_duration(route["duration_s"]))

    except requests.HTTPError as e:
        st.error(f"Erreur HTTP lors de l'appel à un service externe : {e}")
    except requests.RequestException as e:
        st.error(f"Erreur réseau : {e}")
    except Exception as e:
        st.error(f"Une erreur inattendue est survenue : {e}")
