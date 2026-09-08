import os
import time

print("1. BOT STARTING", flush=True)

try:
    import hmac
    print("2. hmac OK", flush=True)

    import hashlib
    print("3. hashlib OK", flush=True)

    import json
    print("4. json OK", flush=True)

    import uuid
    print("5. uuid OK", flush=True)

    from decimal import Decimal, ROUND_DOWN
    print("6. decimal OK", flush=True)

    from datetime import datetime, timezone
    print("7. datetime OK", flush=True)

    import requests
    print("8. requests OK", flush=True)

except Exception as e:
    print(f"IMPORT ERROR: {type(e).__name__}: {e}", flush=True)
    raise

print("9. CHECKING ENVIRONMENT", flush=True)

for name in [
    "CRYPTO_API_KEY",
    "CRYPTO_API_SECRET",
    "GROK_API_KEY",
]:
    value = os.getenv(name)

    if value:
        print(f"{name}: PRESENT", flush=True)
    else:
        print(f"{name}: MISSING", flush=True)

print("10. ENVIRONMENT CHECK COMPLETE", flush=True)

print("11. BOT TEST COMPLETE", flush=True)

while True:
    print("12. BOT ALIVE", flush=True)
    time.sleep(30)
