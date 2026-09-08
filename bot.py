import os
import time
import hmac
import hashlib
import requests

BASE = "https://api.crypto.com/exchange/v1"

API_KEY = os.getenv("CRYPTO_API_KEY")
API_SECRET = os.getenv("CRYPTO_API_SECRET")

print("=== CRYPTO.COM AUTH TEST v5 ===", flush=True)

print("API KEY PRESENT:", bool(API_KEY), flush=True)
print("SECRET PRESENT:", bool(API_SECRET), flush=True)

# --------------------------------------------------
# TEST 1: PUBLIC API
# --------------------------------------------------

print("", flush=True)
print("=== TEST 1: PUBLIC API ===", flush=True)

try:
    r = requests.get(
        BASE + "/public/get-instruments",
        timeout=20
    )

    print("PUBLIC HTTP:", r.status_code, flush=True)
    print("PUBLIC RESPONSE:", r.text[:500], flush=True)

except Exception as e:
    print("PUBLIC ERROR:", type(e).__name__, str(e), flush=True)


# --------------------------------------------------
# TEST 2: AUTHENTICATED API
# --------------------------------------------------

print("", flush=True)
print("=== TEST 2: PRIVATE API ===", flush=True)

METHOD = "private/get-accounts"
PARAMS = {}

request_id = int(time.time() * 1000)
nonce = int(time.time() * 1000)

param_string = ""

signature_payload = (
    METHOD
    + str(request_id)
    + API_KEY
    + param_string
    + str(nonce)
)

signature = hmac.new(
    API_SECRET.encode("utf-8"),
    signature_payload.encode("utf-8"),
    hashlib.sha256
).hexdigest()

body = {
    "id": request_id,
    "method": METHOD,
    "api_key": API_KEY,
    "params": PARAMS,
    "nonce": nonce,
    "sig": signature
}

print("METHOD:", METHOD, flush=True)
print("REQUEST ID:", request_id, flush=True)
print("NONCE:", nonce, flush=True)
print("API KEY LENGTH:", len(API_KEY), flush=True)
print("SECRET LENGTH:", len(API_SECRET), flush=True)
print("SIGNATURE LENGTH:", len(signature), flush=True)
print("SENDING PRIVATE REQUEST...", flush=True)

try:
    r = requests.post(
        BASE + "/" + METHOD,
        json=body,
        headers={
            "Content-Type": "application/json"
        },
        timeout=20
    )

    print("PRIVATE HTTP:", r.status_code, flush=True)
    print("PRIVATE RESPONSE:", r.text[:1000], flush=True)

except Exception as e:
    print("PRIVATE ERROR:", type(e).__name__, str(e), flush=True)


while True:
    time.sleep(30)
