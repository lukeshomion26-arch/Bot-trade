import os
import time
import hmac
import hashlib
import requests

BASE_URL = "https://api.crypto.com/exchange/v1"
METHOD = "private/user-balance"

API_KEY = os.getenv("CRYPTO_API_KEY")
API_SECRET = os.getenv("CRYPTO_API_SECRET")

print("=== CRYPTO AUTH DIAGNOSTIC v3 ===", flush=True)

if not API_KEY:
    raise RuntimeError("CRYPTO_API_KEY missing")

if not API_SECRET:
    raise RuntimeError("CRYPTO_API_SECRET missing")

print("API KEY LENGTH:", len(API_KEY), flush=True)
print("SECRET LENGTH:", len(API_SECRET), flush=True)

print(
    "API KEY HAS LEADING/TRAILING WHITESPACE:",
    API_KEY != API_KEY.strip(),
    flush=True
)

print(
    "SECRET HAS LEADING/TRAILING WHITESPACE:",
    API_SECRET != API_SECRET.strip(),
    flush=True
)

print(
    "API KEY CONTAINS INTERNAL WHITESPACE:",
    any(c.isspace() for c in API_KEY),
    flush=True
)

print(
    "SECRET CONTAINS INTERNAL WHITESPACE:",
    any(c.isspace() for c in API_SECRET),
    flush=True
)

# Do NOT print the actual credentials.

request_id = int(time.time() * 1000)
nonce = int(time.time() * 1000)

params = {}

# Crypto.com's documented parameter-string algorithm.
param_string = ""

payload = (
    METHOD
    + str(request_id)
    + API_KEY
    + param_string
    + str(nonce)
)

signature = hmac.new(
    API_SECRET.encode("utf-8"),
    payload.encode("utf-8"),
    hashlib.sha256
).hexdigest()

body = {
    "id": request_id,
    "method": METHOD,
    "api_key": API_KEY,
    "params": params,
    "nonce": nonce,
    "sig": signature,
}

print("REQUEST ID:", request_id, flush=True)
print("NONCE:", nonce, flush=True)
print("SIGNATURE LENGTH:", len(signature), flush=True)
print("SENDING...", flush=True)

try:
    response = requests.post(
        BASE_URL + "/" + METHOD,
        json=body,
        headers={"Content-Type": "application/json"},
        timeout=20,
    )

    print("HTTP:", response.status_code, flush=True)
    print("RESPONSE:", response.text[:1000], flush=True)

except Exception as e:
    print("ERROR:", type(e).__name__, str(e), flush=True)

while True:
    time.sleep(30)
