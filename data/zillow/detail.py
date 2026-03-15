"""Fetch and parse a Zillow listing detail page for features, policies, and schools."""
import json
import logging
from bs4 import BeautifulSoup
from .playwright_fetch import fetch_html

logger = logging.getLogger(__name__)

DETAIL_SELECTOR = "script#__NEXT_DATA__"

# Maps our schema feature names → buildingAttributes keys that confirm them
_FEATURE_ATTR_MAP = {
    "parking":          ["parkingTypes", "parkingDescription"],
    "garage":           ["parkingTypes", "parkingDescription"],
    "pool":             ["hasSwimmingPool"],
    "basement":         [],
    "waterfront":       [],
    "pet_friendly":     ["petPolicies", "petPolicyDescription", "detailedPetPolicy", "hasPetPark"],
    "new_construction": [],
    "laundry":          ["hasSharedLaundry"],
    "ac":               ["airConditioning"],
    "near_schools":     [],
    "near_transit":     [],
    "barbecue":         ["hasBarbecue"],
    "elevator":         ["hasElevator"],
    "fireplace":        ["hasFireplace"],
    "patio_balcony":    ["hasPatioBalcony"],
    "storage":          ["hasStorage"],
    "hot_tub":          ["hasHotTub"],
    "sauna":            ["hasSauna"],
    "furnished":        ["isFurnished"],
    "smoke_free":       ["isSmokeFree"],
    "disabled_access":  ["hasDisabledAccess"],
    "ceiling_fan":      ["hasCeilingFan"],
}


def _extract_building_data(html: str) -> dict | None:
    """Pull the building/property JSON from the Next.js __NEXT_DATA__ or embedded scripts."""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.select('script[type="application/json"]'):
        try:
            d = json.loads(script.string or "")
            if not isinstance(d, dict) or "props" not in d:
                continue
            redux = (
                d.get("props", {})
                .get("pageProps", {})
                .get("componentProps", {})
                .get("initialReduxState", {})
                .get("gdp", {})
            )
            return redux.get("building") or redux.get("property") or None
        except (json.JSONDecodeError, AttributeError):
            continue
    return None


def _check_feature(feature: str, attrs: dict, schools: list, amenity: dict) -> bool | None:
    """
    Check if a feature is present.
    Returns True (confirmed), False (confirmed absent), or None (unknown).
    """
    if feature == "near_schools":
        if schools:
            return any(s.get("distance", 99) <= 1.5 for s in schools)
        return None

    if feature == "pet_friendly":
        policies = attrs.get("petPolicies", [])
        if isinstance(policies, list):
            policy_str = " ".join(str(p) for p in policies).lower()
            if any(w in policy_str for w in ("cats", "dogs", "pets allowed", "small", "large")):
                return True
            if "no pets" in policy_str:
                return False
        desc = attrs.get("petPolicyDescription") or attrs.get("detailedPetPolicy") or ""
        if isinstance(desc, str) and desc.strip():
            dl = desc.lower()
            if "no pet" in dl or "not allowed" in dl:
                return False
            return True
        pet_details = amenity.get("pets") or amenity.get("petDetails") or []
        if pet_details:
            return True
        if attrs.get("hasPetPark") is True:
            return True
        return None

    if feature in ("parking", "garage"):
        parking = attrs.get("parkingTypes", [])
        desc = (attrs.get("parkingDescription") or "").lower()
        if isinstance(parking, list):
            parking_str = " ".join(str(p) for p in parking).lower()
            if feature == "garage" and "garage" in (parking_str + " " + desc):
                return True
            if feature == "parking" and parking_str and "unknown" not in parking_str:
                return True
            if feature == "parking" and ("parking" in desc or "lot" in desc):
                return True
        return None

    if feature == "ac":
        ac = attrs.get("airConditioning", "")
        if isinstance(ac, str):
            if ac.lower() not in ("", "unknown", "none"):
                return True
            if ac.lower() == "none":
                return False
        return None

    attr_keys = _FEATURE_ATTR_MAP.get(feature, [])
    for key in attr_keys:
        val = attrs.get(key)
        if val is True:
            return True
        if val is False:
            return False
    return None


def parse_detail_features(html: str) -> dict:
    """
    Parse a Zillow detail page and return structured feature data.

    Returns:
        {
            "features_found": ["pet_friendly", "near_schools", ...],
            "features_absent": ["pool", ...],
            "features_unknown": ["garage", ...],
            "schools": [{"name": ..., "distance": ..., "rating": ...}, ...],
            "pet_policy": "...",
            "parking": "...",
            "raw_attributes": { ... },
        }
    """
    building = _extract_building_data(html)
    if not building:
        return {
            "features_found": [], "features_absent": [], "features_unknown": [],
            "schools": [], "pet_policy": None, "parking": None, "raw_attributes": {},
        }

    attrs = building.get("buildingAttributes") or {}
    schools = building.get("assignedSchools") or []
    amenity = building.get("amenityDetails") or {}

    features_found = []
    features_absent = []
    features_unknown = []

    for feature in _FEATURE_ATTR_MAP:
        result = _check_feature(feature, attrs, schools, amenity)
        if result is True:
            features_found.append(feature)
        elif result is False:
            features_absent.append(feature)
        else:
            features_unknown.append(feature)

    pet_policy = attrs.get("petPolicyDescription") or None
    if not pet_policy:
        policies = attrs.get("petPolicies", [])
        if isinstance(policies, list) and policies and policies != ["Unknown"]:
            pet_policy = ", ".join(str(p) for p in policies)

    parking = attrs.get("parkingDescription") or None
    if not parking:
        ptypes = attrs.get("parkingTypes", [])
        if isinstance(ptypes, list) and ptypes and ptypes != ["Unknown"]:
            parking = ", ".join(str(p) for p in ptypes)

    school_summary = [
        {"name": s.get("name", ""), "distance": s.get("distance"), "rating": s.get("rating")}
        for s in schools[:5]
    ]

    return {
        "features_found": features_found,
        "features_absent": features_absent,
        "features_unknown": features_unknown,
        "schools": school_summary,
        "pet_policy": pet_policy,
        "parking": parking,
        "raw_attributes": attrs,
    }


def fetch_detail_features(url: str) -> dict:
    """Fetch a listing detail page and extract features."""
    logger.info("Fetching detail page: %s", url)
    html = fetch_html(url, headless=True)
    if not html:
        logger.warning("Failed to fetch detail page: %s", url)
        return parse_detail_features("")
    return parse_detail_features(html)
