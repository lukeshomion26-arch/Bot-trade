import os
import time
import hmac
import hashlib
import requests

BASE_URL = "https://api.crypto.com/exchange/v1"

API_KEY = os.getenv("CRYPTO_API_KEY")
API_SECRET = os.getenv("CRYPTO_API_SECRET")

METHOD = "private/user-balance"


print("=== CRYPTO.COM AUTH TEST v6 ===", flush=True)

if not API_KEY:
    raise RuntimeError("CRYPTO_API_KEY is missing")

if not API_SECRET:
    raise RuntimeError("CRYPTO_API_SECRET is missing")


# --------------------------------------------------
# Crypto.com official parameter serializer
# --------------------------------------------------

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
                if isinstance(item, dict):
                    result += params_to_str(item, level + 1)
                elif isinstance(item, list):
                    result += params_to_str(item, level + 1)
                else:
                    result += str(item)

        elif isinstance(value, dict):
            result += params_to_str(value, level + 1)

        else:
            result += str(value)

    return result


# --------------------------------------------------
# Build request
# --------------------------------------------------

# Keep ID independent from nonce.
request_id = 11

# One nonce, used in BOTH the signature and JSON body.
nonce = int(time.time() * 1000)

# Explicitly select the unified master Exchange account.
params = {
    "system_label": "ONEEX"
}

param_string = params_to_str(params)


# EXACT Crypto.com formula:
#
# method + id + api_key + parameter_string + nonce

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
    "params": params,
    "nonce": nonce,
    "sig": signature
}


print("METHOD:", METHOD, flush=True)
print("REQUEST ID:", request_id, flush=True)
print("NONCE:", nonce, flush=True)
print("SYSTEM LABEL: ONEEX", flush=True)
print("PARAM STRING:", param_string, flush=True)
print("API KEY LENGTH:", len(API_KEY), flush=True)
print("SECRET LENGTH:", len(API_SECRET), flush=True)
print("SIGNATURE LENGTH:", len(signature), flush=True)
print("SENDING...", flush=True)


# --------------------------------------------------
# Send
# --------------------------------------------------

try:
    response = requests.post(
        BASE_URL + "/" + METHOD,
        json=body,
        headers={
            "Content-Type": "application/json"
        },
        timeout=20
    )

    print("HTTP STATUS:", response.status_code, flush=True)
    print("RESPONSE:", response.text[:2000], flush=True)

    try:
        data = response.json()
    except Exception:
        data = {}

    if data.get("code") == 0:
        print("", flush=True)
        print("======================================", flush=True)
        print("AUTHENTICATION SUCCESSFUL", flush=True)
        print("CRYPTO.COM ACCOUNT ACCESS WORKS", flush=True)
        print("======================================", flush=True)
    else:
        print("", flush=True)
        print("======================================", flush=True)
        print("AUTHENTICATION FAILED", flush=True)
        print("======================================", flush=True)

except Exception as e:
    print(
        "REQUEST ERROR:",
        type(e).__name__,
        str(e),
        flush=True
    )


# Keep Render worker alive.
while True:
    time.sleep(30)
