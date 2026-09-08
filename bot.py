import os
import time
import hmac
import hashlib
import requests

BASE_URL = "https://api.crypto.com/exchange/v1"
METHOD = "private/user-balance"

API_KEY = os.environ["CRYPTO_API_KEY"]
API_SECRET = os.environ["CRYPTO_API_SECRET"]

request_id = 11
nonce = int(time.time() * 1000)

params = {}

# Empty params = empty string
param_string = ""

# Crypto.com documented signature:
# method + id + api_key + parameter_string + nonce
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
    "sig": signature
}

print("=== CRYPTO.COM FINAL AUTH TEST ===", flush=True)
print("METHOD:", METHOD, flush=True)
print("ID:", request_id, flush=True)
print("NONCE:", nonce, flush=True)
print("KEY LENGTH:", len(API_KEY), flush=True)
print("SECRET LENGTH:", len(API_SECRET), flush=True)
print("SIGNATURE LENGTH:", len(signature), flush=True)
print("SENDING...", flush=True)

try:
    response = requests.post(
        BASE_URL + "/" + METHOD,
        json=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "crypto-com-exchange/1.0.1"
        },
        timeout=20
    )

    print("HTTP:", response.status_code, flush=True)
    print("RESPONSE:", response.text[:2000], flush=True)

except Exception as e:
    print("ERROR:", type(e).__name__, str(e), flush=True)

while True:
    time.sleep(30)
