import re
from math import radians, sin, cos, sqrt, atan2


MUNICH_COORDS = (48.137154, 11.576124)

CITY_COORDS = {
    "munich": (48.137154, 11.576124),
    "münchen": (48.137154, 11.576124),

    "garching": (48.248872, 11.653247),
    "ismaning": (48.226292, 11.674108),
    "unterföhring": (48.192092, 11.642337),
    "unterschleißheim": (48.280371, 11.576840),
    "oberschleißheim": (48.250751, 11.559788),

    "dachau": (48.260269, 11.434021),
    "fürstenfeldbruck": (48.179041, 11.254698),
    "germering": (48.133921, 11.376692),

    "starnberg": (48.001932, 11.344262),
    "gilching": (48.107122, 11.293969),

    "freising": (48.402880, 11.748486),
    "erding": (48.306679, 11.906859),

    "ottobrunn": (48.064903, 11.663191),
    "unterhaching": (48.065922, 11.615955),
    "taufkirchen": (48.048039, 11.617206),
    "kirchheim": (48.176700, 11.755300),
    "neubiberg": (48.076282, 11.658467),

    "rosenheim": (47.856370, 12.128100),
    "wasserburg": (48.061376, 12.232143),

    "augsburg": (48.370545, 10.897790),
    "gersthofen": (48.424815, 10.877856),
    "ingolstadt": (48.766535, 11.425755),

    "landshut": (48.544191, 12.146854),
    "mühldorf": (48.246072, 12.521868),

    "weilheim": (47.840748, 11.141448),
    "wolfratshausen": (47.912624, 11.421382),

    "bad tölz": (47.760846, 11.558038),
    "holzkirchen": (47.876435, 11.701924)
}


def haversine_km(lat1, lon1, lat2, lon2):
    earth_radius_km = 6371.0

    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat1)
        * cos(lat2)
        * sin(delta_lon / 2) ** 2
    )

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a)
    )

    return earth_radius_km * c


def is_remote_germany(location, description=""):
    location_text = (location or "").lower().strip()
    description_text = (description or "").lower()

    remote_terms = [
        "remote",
        "home office",
        "homeoffice",
        "work from home",
        "fully remote"
    ]

    germany_terms = [
        "germany",
        "deutschland",
        "german-wide",
        "germany-wide"
    ]

    # Explicit Germany-wide remote wording in description
    has_remote_in_description = any(
        term in description_text
        for term in remote_terms
    )

    has_germany_scope_in_description = any(
        term in description_text
        for term in germany_terms
    )

    if (
        has_remote_in_description
        and has_germany_scope_in_description
    ):
        return True

    # Generic country-level location such as "Germany"
    generic_germany_location = location_text in {
        "germany",
        "deutschland",
        "remote germany",
        "remote - germany",
        "germany remote",
        "remote, germany"
    }

    if generic_germany_location and (
        has_remote_in_description
        or "remote" in location_text
    ):
        return True

    return False


def extract_known_city(location):
    location_lower = (location or "").lower()

    for city in CITY_COORDS:
        pattern = r"(?<!\w)" + re.escape(city) + r"(?!\w)"

        if re.search(pattern, location_lower):
            return city

    return None


def distance_from_munich(location):
    city = extract_known_city(location)

    if city is None:
        return None

    lat, lon = CITY_COORDS[city]
    munich_lat, munich_lon = MUNICH_COORDS

    return haversine_km(
        munich_lat,
        munich_lon,
        lat,
        lon
    )


def location_allowed(
    location,
    description="",
    max_distance_km=100
):
    # Remote anywhere in Germany
    if is_remote_germany(
        location,
        description
    ):
        return True

    distance = distance_from_munich(location)

    # Unknown city:
    # don't automatically accept it
    if distance is None:
        return False

    return distance <= max_distance_km
