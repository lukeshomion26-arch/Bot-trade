import os
import time
import hmac
import hashlib
import requests

API_KEY = os.getenv("CRYPTO_API_KEY")
API_SECRET = os.getenv("CRYPTO_API_SECRET")

BASE_URL = "https://api.crypto.com/exchange/v1"
METHOD = "private/user-balance"

print("=== CRYPTO.COM AUTH TEST v2 ===", flush=True)

if not API_KEY:
    raise RuntimeError("CRYPTO_API_KEY is missing")

if not API_SECRET:
    raise RuntimeError("CRYPTO_API_SECRET is missing")


# This follows Crypto.com's documented parameter-string algorithm.
MAX_LEVEL = 3


def params_to_str(obj, level=0):
    if level >= MAX_LEVEL:
        return str(obj)

    result = ""

    for key in sorted(obj):
        result += key

        value = obj[key]

        if value is None:
            result += "null"

        elif isinstance(value, list):
            for item in value:
                result += params_to_str(item, level + 1)

        elif isinstance(value, dict):
            result += params_to_str(value, level + 1)

        else:
            result += str(value)

    return result


# Numeric request ID.
request_id = int(time.time() * 1000)

# Current Unix timestamp in milliseconds.
nonce = int(time.time() * 1000)

params = {}

# Empty params means an empty parameter string.
param_string = params_to_str(params, 0)

# EXACT documented payload:
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


print("METHOD:", METHOD, flush=True)
print("REQUEST ID:", request_id, flush=True)
print("NONCE:", nonce, flush=True)
print("PARAM STRING LENGTH:", len(param_string), flush=True)
print("API KEY LENGTH:", len(API_KEY), flush=True)
print("SECRET LENGTH:", len(API_SECRET), flush=True)
print("SIGNATURE LENGTH:", len(signature), flush=True)

body = {
    "id": request_id,
    "method": METHOD,
    "api_key": API_KEY,
    "params": params,
    "nonce": nonce,
    "sig": signature,
}

print("SENDING REQUEST...", flush=True)

try:
    response = requests.post(
        BASE_URL + "/" + METHOD,
        json=body,
        headers={
            "Content-Type": "application/json"
        },
        timeout=20,
    )

    print("HTTP STATUS:", response.status_code, flush=True)

    try:
        data = response.json()
    except Exception:
        print("RAW RESPONSE:", response.text[:500], flush=True)
        raise

    print("API CODE:", data.get("code"), flush=True)

    if data.get("message"):
        print("API MESSAGE:", data.get("message"), flush=True)

    if data.get("code") == 0:
        print("", flush=True)
        print("==============================", flush=True)
        print("AUTHENTICATION SUCCESSFUL", flush=True)
        print("==============================", flush=True)
        print("ACCOUNT BALANCE REQUEST WORKS", flush=True)
    else:
        print("", flush=True)
        print("==============================", flush=True)
        print("AUTHENTICATION FAILED", flush=True)
        print("==============================", flush=True)

except Exception as e:
    print(
        f"REQUEST ERROR: {type(e).__name__}: {e}",
        flush=True
    )


while True:
    time.sleep(30)
