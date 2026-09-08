import os
import hashlib

key = os.environ["CRYPTO_API_KEY"]
secret = os.environ["CRYPTO_API_SECRET"]

print("=== CREDENTIAL PAIR CHECK ===", flush=True)

print("KEY LENGTH:", len(key), flush=True)
print("SECRET LENGTH:", len(secret), flush=True)

print(
    "KEY SHA256:",
    hashlib.sha256(key.encode()).hexdigest()[:12],
    flush=True
)

print(
    "SECRET SHA256:",
    hashlib.sha256(secret.encode()).hexdigest()[:12],
    flush=True
)

print(
    "KEY FIRST 4:",
    key[:4],
    flush=True
)

print(
    "KEY LAST 4:",
    key[-4:],
    flush=True
)

print(
    "SECRET FIRST 4:",
    secret[:4],
    flush=True
)

print(
    "SECRET LAST 4:",
    secret[-4:],
    flush=True
)

print("=== END ===", flush=True)

import time
while True:
    time.sleep(30)
