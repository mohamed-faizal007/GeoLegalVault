"""Manual/local smoke test for server-side geofence enforcement on upload —
not a permanent deliverable, safe to delete once you've confirmed it works.
Exists mainly as a workaround for Chrome DevTools' location override always
reporting ~150m accuracy, which trips LOCATION_LOW_CONFIDENCE before the
actual geofence check ever runs. This script sends X-Geo-* headers directly,
so accuracy and timestamp are fully controlled (Guardrail #5: the server is
the only place inside/outside is decided — this script just gives it clean
input to decide from).

Talks to a running backend over plain HTTP (default http://localhost:8000);
does not import any backend internals, so it works the same way a real
client request would.

Usage (run from repo root, backend already running e.g. via docker-compose):
    python scripts/test_geofence_upload.py

Env overrides:
    API_BASE_URL   default http://localhost:8000/api/v1
    DEMO_EMAIL     default legal_officer@geolegalvault.demo
    DEMO_PASSWORD  default Demo@Pass123! (scripts/seed.py --demo's password)

Runs two uploads against the demo HQ geofence (scripts/seed.py --demo):
  1. Inside the fence (11.67, 78.15), accuracy 15m -> expect 201.
  2. Outside the fence (11.00, 77.00), same good accuracy -> expect 403
     GEOFENCE_DENIED (proving the accuracy/freshness checks and the
     inside/outside check are independent — a good-accuracy reading can
     still be denied on location alone).
"""

import os
import sys
import time

import httpx

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
DEMO_EMAIL = os.environ.get("DEMO_EMAIL", "legal_officer@geolegalvault.demo")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "Demo@Pass123!")

# Same HQ campus box scripts/seed.py --demo creates, and its known
# inside/outside test points (Plan Part 10's worked example).
INSIDE_POINT = {"lat": 11.67, "lng": 78.15}
OUTSIDE_POINT = {"lat": 11.00, "lng": 77.00}
GOOD_ACCURACY_M = 15

TEST_FILE_BYTES = b"GeoLegalVault local geofence smoke test upload.\n" * 20


def login(client: httpx.Client) -> str:
    resp = client.post(
        "/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
    )
    if resp.status_code != 200:
        print(f"Login failed ({resp.status_code}): {resp.text}")
        print(
            "Has scripts/seed.py --demo been run against this backend's Mongo? "
            "(python scripts/seed.py --demo)"
        )
        sys.exit(1)
    return resp.json()["access_token"]


def upload(client: httpx.Client, token: str, *, lat: float, lng: float, accuracy_m: float) -> httpx.Response:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Geo-Lat": str(lat),
        "X-Geo-Lng": str(lng),
        "X-Geo-Accuracy": str(accuracy_m),
        # Unix epoch seconds, UTC — see LocationInput.timestamp /
        # backend/app/services/geofence.py. NOT milliseconds, NOT ISO 8601.
        "X-Geo-Timestamp": str(time.time()),
    }
    data = {
        "title": "Geofence smoke test upload",
        "doc_type": "CONTRACT",
        "classification": "RESTRICTED",
        "tags": "smoke-test",
    }
    files = {"file": ("smoke-test.txt", TEST_FILE_BYTES, "text/plain")}
    return client.post("/documents", headers=headers, data=data, files=files)


def main() -> None:
    with httpx.Client(base_url=API_BASE_URL, timeout=10) as client:
        token = login(client)
        print(f"Logged in as {DEMO_EMAIL}.")

        print(
            f"\n[1/2] Uploading from inside the HQ geofence "
            f"({INSIDE_POINT['lat']}, {INSIDE_POINT['lng']}), accuracy {GOOD_ACCURACY_M}m..."
        )
        inside_resp = upload(client, token, accuracy_m=GOOD_ACCURACY_M, **INSIDE_POINT)
        print(f"  -> {inside_resp.status_code} {inside_resp.text}")
        if inside_resp.status_code == 201:
            print("  OK: upload from inside the fence succeeded (201).")
        else:
            print("  UNEXPECTED: expected 201.")

        print(
            f"\n[2/2] Uploading from outside the HQ geofence "
            f"({OUTSIDE_POINT['lat']}, {OUTSIDE_POINT['lng']}), same accuracy {GOOD_ACCURACY_M}m..."
        )
        outside_resp = upload(client, token, accuracy_m=GOOD_ACCURACY_M, **OUTSIDE_POINT)
        print(f"  -> {outside_resp.status_code} {outside_resp.text}")
        outside_code = None
        try:
            outside_code = outside_resp.json().get("error", {}).get("code")
        except ValueError:
            pass
        if outside_resp.status_code == 403 and outside_code == "GEOFENCE_DENIED":
            print(
                "  OK: rejected with 403 GEOFENCE_DENIED, not LOCATION_LOW_CONFIDENCE — "
                "confirms accuracy/freshness and inside/outside are checked independently."
            )
        else:
            print(f"  UNEXPECTED: expected 403 GEOFENCE_DENIED, got {outside_resp.status_code} {outside_code!r}.")


if __name__ == "__main__":
    main()
