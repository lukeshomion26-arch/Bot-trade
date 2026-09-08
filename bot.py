import os
import time
import hmac
import hashlib
import requests

BASE = "https://api.crypto.com/exchange/v1"

API_KEY = os.getenv("CRYPTO_API_KEY")
API_SECRET = os.getenv("CRYPTO_API_SECRET")

print("=== CRYPTO AUTH TEST ===", flush=True)

if not API_KEY:
    raise RuntimeError("CRYPTO_API_KEY is missing")

if not API_SECRET:
    raise RuntimeError("CRYPTO_API_SECRET is missing")

# Use a numeric request ID.
request_id = int(time.time() * 1000)

# Nonce must be current Unix time in milliseconds.
nonce = int(time.time() * 1000)

method = "private/user-balance"

params = {}

# Empty because user-balance has no parameters.
param_string = ""

payload = (
    method
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

print("METHOD:", method, flush=True)
print("REQUEST ID:", request_id, flush=True)
print("NONCE:", nonce, flush=True)
print("API KEY LENGTH:", len(API_KEY), flush=True)
print("SECRET LENGTH:", len(API_SECRET), flush=True)
print("SIGNATURE LENGTH:", len(signature), flush=True)

body = {
    "id": request_id,
    "method": method,
    "api_key": API_KEY,
    "params": {},
    "nonce": nonce,
    "sig": signature,
}

print("SENDING REQUEST...", flush=True)

try:
    response = requests.post(
        BASE + "/" + method,
        json=body,
        headers={
            "Content-Type": "application/json"
        },
        timeout=20,
    )

    print("HTTP:", response.status_code, flush=True)

    data = response.json()

    print("CODE:", data.get("code"), flush=True)
    print("MESSAGE:", data.get("message"), flush=True)

    if data.get("code") == 0:
        print("================================", flush=True)
        print("AUTHENTICATION SUCCESSFUL", flush=True)
        print("================================", flush=True)
    else:
        print("AUTHENTICATION FAILED", flush=True)

except Exception as e:
    print(
        "ERROR:",
        type(e).__name__,
        str(e),
        flush=True
    )

while True:
    time.sleep(30)
