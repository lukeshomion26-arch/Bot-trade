import os
import json
import time
import hmac
import hashlib
import websocket

API_KEY = os.environ["CRYPTO_API_KEY"].strip()
API_SECRET = os.environ["CRYPTO_API_SECRET"].strip()

request_id = 1
nonce = int(time.time() * 1000)
method = "public/auth"
params = {}

# Crypto.com signature
payload = method + str(request_id) + API_KEY + "" + str(nonce)
sig = hmac.new(
    API_SECRET.encode("utf-8"),
    payload.encode("utf-8"),
    hashlib.sha256
).hexdigest()

message = {
    "id": request_id,
    "method": method,
    "api_key": API_KEY,
    "sig": sig,
    "nonce": nonce,
    "params": params
}

print("=== CRYPTO.COM WEBSOCKET AUTH TEST ===", flush=True)
print("KEY LENGTH:", len(API_KEY), flush=True)
print("SECRET LENGTH:", len(API_SECRET), flush=True)
print("SIGNATURE LENGTH:", len(sig), flush=True)
print("CONNECTING...", flush=True)

try:
    ws = websocket.create_connection(
        "wss://stream.crypto.com/exchange/v1/user",
        timeout=15
    )

    print("CONNECTED", flush=True)

    time.sleep(1)

    print("SENDING AUTH...", flush=True)
    ws.send(json.dumps(message))

    response = ws.recv()

    print("AUTH RESPONSE:", response, flush=True)

    ws.close()

except Exception as e:
    print("ERROR:", repr(e), flush=True)

print("=== TEST COMPLETE ===", flush=True)

while True:
    time.sleep(60)
