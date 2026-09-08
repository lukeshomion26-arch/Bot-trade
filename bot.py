import os
import time
import hmac
import hashlib
import requests

BASE = "https://api.crypto.com/exchange/v1"
METHOD = "private/user-balance"

API_KEY = os.environ["CRYPTO_API_KEY"]
API_SECRET = os.environ["CRYPTO_API_SECRET"]

# Crypto.com request ID
request_id = int(time.time())

# Crypto.com nonce in milliseconds
nonce = int(time.time() * 1000)

params = {}

# Empty params => empty parameter string
param_string = ""

# Exact documented signing payload
sign_payload = (
    METHOD
    + str(request_id)
    + API_KEY
    + param_string
    + str(nonce)
)

signature = hmac.new(
    API_SECRET.encode("utf-8"),
    sign_payload.encode("utf-8"),
    hashlib.sha256
).hexdigest()

body = {
    "id": request_id,
    "method": METHOD,
    "api_key": API_KEY,
    "params": {},
    "nonce": nonce,
    "sig": signature
}

print("=== CRYPTO.COM AUTH TEST V7 ===", flush=True)
print("METHOD:", METHOD, flush=True)
print("ID:", request_id, flush=True)
print("NONCE:", nonce, flush=True)
print("KEY LENGTH:", len(API_KEY), flush=True)
print("SECRET LENGTH:", len(API_SECRET), flush=True)
print("SIGNATURE LENGTH:", len(signature), flush=True)
print("SENDING...", flush=True)

try:
    r = requests.post(
        BASE + "/" + METHOD,
        json=body,
        headers={"Content-Type": "application/json"},
        timeout=20
    )

    print("HTTP:", r.status_code, flush=True)
    print("RESPONSE:", r.text[:2000], flush=True)

except Exception as e:
    print("ERROR:", repr(e), flush=True)

while True:
    time.sleep(30)
