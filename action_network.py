import os
import requests

AN_BASE_URL = "https://actionnetwork.org/api/v2"


def _headers():
    return {"OSDI-API-Token": os.getenv("ACTION_NETWORK_API_KEY")}


def check_membership(email: str) -> bool:
    """Returns True if the email belongs to an active DSA member in Action Network."""
    params = {"filter": f"email_address eq '{email}'"}
    response = requests.get(
        f"{AN_BASE_URL}/people",
        headers=_headers(),
        params=params,
        timeout=10
    )
    response.raise_for_status()

    people = response.json().get("_embedded", {}).get("osdi:people", [])
    if not people:
        return False

    custom_fields = people[0].get("custom_fields", {})
    return custom_fields.get("is_member") == "True"
