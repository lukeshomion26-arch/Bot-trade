import os
import time
import hmac
import hashlib
import requests

CRYPTO_BASE = "https://api.crypto.com/exchange/v1"

API_KEY = os.getenv("CRYPTO_API_KEY")
API_SECRET = os.getenv("CRYPTO_API_SECRET")

print("BOT STARTING", flush=True)
print("API KEY:", "PRESENT" if API_KEY else "MISSING", flush=True)
print("API SECRET:", "PRESENT" if API_SECRET else "MISSING", flush=True)


def make_signature(method, request_id, params, nonce):
    params = params or {}

    param_string = "".join(
        key + str(params[key])
        for key in sorted(params)
    )

    payload = (
        method
        + str(request_id)
        + API_KEY
        + param_string
        + str(nonce)
    )

    return hmac.new(
        API_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def crypto_private(method, params=None):
    params = params or {}

    # Crypto.com requires a numeric request ID.
    request_id = int(time.time() * 1000)
    nonce = int(time.time() * 1000)

    body = {
        "id": request_id,
        "method": method,
        "api_key": API_KEY,
        "params": params,
        "nonce": nonce,
    }

    body["sig"] = make_signature(
        method,
        request_id,
        params,
        nonce,
    )

    print(f"CALLING: {method}", flush=True)

    response = requests.post(
        f"{CRYPTO_BASE}/{method}",
        json=body,
        timeout=20,
    )

    print("HTTP STATUS:", response.status_code, flush=True)

    data = response.json()

    print("API CODE:", data.get("code"), flush=True)

    if data.get("message"):
        print("API MESSAGE:", data["message"], flush=True)

    return data


try:
    result = crypto_private("private/user-balance")

    if result.get("code") == 0:
        print("========================================", flush=True)
        print("CRYPTO.COM CONNECTION SUCCESSFUL", flush=True)
        print("========================================", flush=True)
    else:
        print("CRYPTO.COM REQUEST FAILED", flush=True)

except Exception as e:
    print(
        f"CRYPTO TEST ERROR: {type(e).__name__}: {e}",
        flush=True,
    )

while True:
    print("BOT ALIVE", flush=True)
    time.sleep(30)
