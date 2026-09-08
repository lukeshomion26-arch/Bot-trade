import os
import time
import hmac
import hashlib
import requests

BASE_URL = "https://api.crypto.com/exchange/v1"
METHOD = "private/get-accounts"

API_KEY = os.getenv("CRYPTO_API_KEY")
API_SECRET = os.getenv("CRYPTO_API_SECRET")

print("=== CRYPTO.COM AUTH TEST v4 ===", flush=True)

if not API_KEY:
    raise RuntimeError("CRYPTO_API_KEY is missing")

if not API_SECRET:
    raise RuntimeError("CRYPTO_API_SECRET is missing")


def object_to_string(obj):
    if obj is None:
        return ""

    result = ""

    for key in sorted(obj):
        value = obj[key]

        result += key

        if isinstance(value, dict):
            result += object_to_string(value)

        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    result += object_to_string(item)
                elif isinstance(item, list):
                    result += str(item)
                else:
                    result += str(item)

        else:
            result += str(value)

    return result


# Crypto.com requires a numeric request ID.
request_id = int(time.time() * 1000)

# Current Unix timestamp in milliseconds.
nonce = int(time.time() * 1000)

params = {}

param_string = object_to_string(params)

# Crypto.com's documented signature payload:
#
# method + id + api_key + parameter_string + nonce
#
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
    "sig": signature,
}


print("METHOD:", METHOD, flush=True)
print("REQUEST ID:", request_id, flush=True)
print("NONCE:", nonce, flush=True)
print("PARAM STRING:", repr(param_string), flush=True)
print("API KEY LENGTH:", len(API_KEY), flush=True)
print("SECRET LENGTH:", len(API_SECRET), flush=True)
print("SIGNATURE LENGTH:", len(signature), flush=True)
print("SENDING REQUEST...", flush=True)

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

        if data.get("code") == 0:
            print("", flush=True)
            print("================================", flush=True)
            print("AUTHENTICATION SUCCESSFUL", flush=True)
            print("GET-ACCOUNTS WORKS", flush=True)
            print("================================", flush=True)
        else:
            print("", flush=True)
            print("================================", flush=True)
            print("AUTHENTICATION FAILED", flush=True)
            print("================================", flush=True)

    except Exception:
        print("Response was not valid JSON.", flush=True)

except Exception as e:
    print(
        "REQUEST ERROR:",
        type(e).__name__,
        str(e),
        flush=True
    )


while True:
    time.sleep(30)
