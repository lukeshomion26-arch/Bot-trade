import os
import time
import hmac
import hashlib
import json
import uuid
import requests

CRYPTO_BASE = "https://api.crypto.com/exchange/v1"

API_KEY = os.getenv("CRYPTO_API_KEY")
API_SECRET = os.getenv("CRYPTO_API_SECRET")

print("BOT STARTING", flush=True)
print("API KEY:", "PRESENT" if API_KEY else "MISSING", flush=True)
print("API SECRET:", "PRESENT" if API_SECRET else "MISSING", flush=True)


def make_signature(method, params, nonce, req_id):
    params = params or {}

    param_str = "".join(
        f"{key}{params[key]}"
        for key in sorted(params)
    )

    payload = (
        method
        + str(req_id)
        + API_KEY
        + param_str
        + str(nonce)
    )

    return hmac.new(
        API_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def crypto_private(method, params=None):
    req_id = str(uuid.uuid4())
    nonce = int(time.time() * 1000)

    params = params or {}

    body = {
        "id": req_id,
        "method": method,
        "api_key": API_KEY,
        "params": params,
        "nonce": nonce,
    }

    body["sig"] = make_signature(
        method,
        params,
        nonce,
        req_id
    )

    print(f"CALLING: {method}", flush=True)

    response = requests.post(
        f"{CRYPTO_BASE}/{method}",
        json=body,
        timeout=20
    )

    print("HTTP STATUS:", response.status_code, flush=True)
    print("RESPONSE RECEIVED", flush=True)

    data = response.json()

    # Don't print the entire response in case it contains
    # information we don't need in the logs.
    print("API CODE:", data.get("code"), flush=True)

    return data


try:
    result = crypto_private("private/user-balance")

    print("CRYPTO.COM CONNECTION TEST COMPLETE", flush=True)

    result_data = result.get("result")

    if result_data is not None:
        print("ACCOUNT DATA RECEIVED: YES", flush=True)
    else:
        print("ACCOUNT DATA RECEIVED: NO", flush=True)
        print("API MESSAGE:", result.get("message"), flush=True)

except Exception as e:
    print(
        f"CRYPTO TEST ERROR: {type(e).__name__}: {e}",
        flush=True
    )

while True:
    print("BOT ALIVE", flush=True)
    time.sleep(30)
