import os
import time
import hmac
import hashlib
import json
import uuid
import requests
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone


# ============================================================
# CONFIGURATION
# ============================================================

CRYPTO_API_KEY = os.getenv("CRYPTO_API_KEY")
CRYPTO_API_SECRET = os.getenv("CRYPTO_API_SECRET")
GROK_API_KEY = os.getenv("GROK_API_KEY")

CRYPTO_BASE_URL = "https://api.crypto.com/exchange/v1"
GROK_URL = "https://api.x.ai/v1/chat/completions"

GROK_MODEL = os.getenv("GROK_MODEL", "grok-4.6")

ALLOWED_INSTRUMENTS = [
    "BTC_USDT",
    "ETH_USDT"
]

LOOP_SECONDS = int(
    os.getenv("LOOP_SECONDS", "900")
)

MAX_POSITION_PCT = Decimal(
    os.getenv("MAX_POSITION_PCT", "0.30")
)

MIN_CONFIDENCE = float(
    os.getenv("MIN_CONFIDENCE", "0.70")
)

DAILY_LOSS_LIMIT_PCT = Decimal(
    os.getenv("DAILY_LOSS_LIMIT_PCT", "0.15")
)

# Maximum percentage of portfolio value that ONE trade
# may represent.
MAX_TRADE_PCT = Decimal(
    os.getenv("MAX_TRADE_PCT", "0.30")
)

# Prevent extremely small trades.
MIN_TRADE_USDT = Decimal(
    os.getenv("MIN_TRADE_USDT", "1.00")
)

# Maximum acceptable spread.
MAX_SPREAD_PCT = Decimal(
    os.getenv("MAX_SPREAD_PCT", "0.50")
)

# Emergency switch.
#
# IMPORTANT:
# Set LIVE_TRADING=true only when you actually want
# real orders.
LIVE_TRADING = os.getenv(
    "LIVE_TRADING",
    "false"
).lower() == "true"

# After sending an order, wait for the exchange to report
# its state.
ORDER_CHECK_SECONDS = 2

# Never allow the bot to have an existing open order when
# it is about to submit another one.
REJECT_IF_OPEN_ORDERS = True

ACCOUNT_STATE_FILE = os.getenv(
    "ACCOUNT_STATE_FILE",
    "bot_state.json"
)


# ============================================================
# VALIDATION
# ============================================================

if not CRYPTO_API_KEY:
    raise ValueError("Missing CRYPTO_API_KEY")

if not CRYPTO_API_SECRET:
    raise ValueError("Missing CRYPTO_API_SECRET")

if not GROK_API_KEY:
    raise ValueError("Missing GROK_API_KEY")


# ============================================================
# LOGGING
# ============================================================

def log(message):
    print(
        f"[{datetime.now(timezone.utc).isoformat()}] "
        f"{message}",
        flush=True
    )


# ============================================================
# CRYPTO.COM SIGNATURE
# ============================================================

_request_id = 0
_last_nonce = 0


def next_request_id():
    global _request_id

    _request_id += 1

    return _request_id


def next_nonce():
    """
    Crypto.com requires a current millisecond nonce.

    Also guarantees that two requests made in the same
    millisecond don't reuse the same nonce.
    """
    global _last_nonce

    nonce = int(time.time() * 1000)

    if nonce <= _last_nonce:
        nonce = _last_nonce + 1

    _last_nonce = nonce

    return nonce


def params_to_string(obj, level=0):
    """
    Crypto.com HMAC parameter serialization.

    Matches the API documentation's recursive
    alphabetical-key serialization.
    """

    MAX_LEVEL = 3

    if level >= MAX_LEVEL:
        return str(obj)

    if obj is None:
        return "null"

    if isinstance(obj, dict):

        output = ""

        for key in sorted(obj.keys()):

            output += str(key)

            value = obj[key]

            if value is None:
                output += "null"

            elif isinstance(value, (dict, list)):
                output += params_to_string(
                    value,
                    level + 1
                )

            else:
                output += str(value)

        return output

    if isinstance(obj, list):

        return "".join(
            params_to_string(
                item,
                level + 1
            )
            for item in obj
        )

    return str(obj)


def sign_request(
    method,
    request_id,
    params,
    nonce
):

    param_string = params_to_string(
        params
    )

    payload = (
        method
        + str(request_id)
        + CRYPTO_API_KEY
        + param_string
        + str(nonce)
    )

    return hmac.new(
        CRYPTO_API_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


# ============================================================
# CRYPTO.COM REST
# ============================================================

def crypto_public(
    method,
    params=None
):

    url = f"{CRYPTO_BASE_URL}/{method}"

    response = requests.get(
        url,
        params=params or {},
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    if data.get("code") != 0:
        raise RuntimeError(
            f"Crypto.com public API error: {data}"
        )

    return data["result"]


def crypto_private(
    method,
    params=None
):

    params = params or {}

    request_id = next_request_id()
    nonce = next_nonce()

    body = {
        "id": request_id,
        "method": method,
        "api_key": CRYPTO_API_KEY,
        "params": params,
        "nonce": nonce
    }

    body["sig"] = sign_request(
        method,
        request_id,
        params,
        nonce
    )

    response = requests.post(
        f"{CRYPTO_BASE_URL}/{method}",
        headers={
            "Content-Type": "application/json"
        },
        json=body,
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    if data.get("code") != 0:

        raise RuntimeError(
            f"Crypto.com private API error: "
            f"{data}"
        )

    return data["result"]


# ============================================================
# MARKET DATA
# ============================================================

def get_ticker(instrument):

    result = crypto_public(
        "public/get-tickers",
        {
            "instrument_name": instrument
        }
    )

    data = result.get("data", [])

    if not data:
        raise RuntimeError(
            f"No ticker for {instrument}"
        )

    ticker = data[0]

    return {
        "price": Decimal(ticker["a"]),
        "bid": Decimal(ticker["b"]),
        "ask": Decimal(ticker["k"]),
        "high": Decimal(ticker["h"]),
        "low": Decimal(ticker["l"]),
        "volume": Decimal(ticker["v"]),
        "change_24h": Decimal(ticker["c"]) * 100
    }


def get_candles(
    instrument,
    timeframe="15m",
    count=100
):

    result = crypto_public(
        "public/get-candlestick",
        {
            "instrument_name": instrument,
            "timeframe": timeframe,
            "count": count
        }
    )

    candles = result.get("data", [])

    if len(candles) < 50:
        raise RuntimeError(
            f"Not enough candles for {instrument}"
        )

    candles.sort(
        key=lambda x: int(x["t"])
    )

    return candles


# ============================================================
# INDICATORS
# ============================================================

def sma(values, period):

    if len(values) < period:
        return None

    return sum(
        values[-period:]
    ) / Decimal(period)


def rsi(values, period=14):

    if len(values) <= period:
        return None

    gains = []
    losses = []

    for i in range(
        len(values) - period,
        len(values)
    ):

        change = (
            values[i]
            - values[i - 1]
        )

        if change > 0:
            gains.append(change)
            losses.append(Decimal("0"))

        else:
            gains.append(Decimal("0"))
            losses.append(abs(change))

    average_gain = (
        sum(gains)
        / Decimal(period)
    )

    average_loss = (
        sum(losses)
        / Decimal(period)
    )

    if average_loss == 0:
        return Decimal("100")

    rs = average_gain / average_loss

    return Decimal("100") - (
        Decimal("100")
        / (Decimal("1") + rs)
    )


def momentum(
    values,
    period=10
):

    if len(values) <= period:
        return None

    old = values[-period - 1]
    new = values[-1]

    return (
        (new / old) - 1
    ) * 100


def market_snapshot(instrument):

    ticker = get_ticker(
        instrument
    )

    candles = get_candles(
        instrument
    )

    closes = [
        Decimal(c["c"])
        for c in candles
    ]

    spread_pct = (
        (ticker["ask"] - ticker["bid"])
        / ticker["bid"]
    ) * 100

    return {
        "instrument": instrument,
        "price": str(ticker["price"]),
        "bid": str(ticker["bid"]),
        "ask": str(ticker["ask"]),
        "spread_pct": str(
            spread_pct.quantize(
                Decimal("0.0001")
            )
        ),
        "24h_change_pct": str(
            ticker["change_24h"]
        ),
        "24h_high": str(ticker["high"]),
        "24h_low": str(ticker["low"]),
        "24h_volume": str(ticker["volume"]),
        "sma_10": str(
            sma(closes, 10)
        ),
        "sma_20": str(
            sma(closes, 20)
        ),
        "sma_50": str(
            sma(closes, 50)
        ),
        "rsi_14": str(
            rsi(closes, 14)
        ),
        "momentum_10_candle_pct": str(
            momentum(closes, 10)
        )
    }


# ============================================================
# ACCOUNT
# ============================================================

def get_balances():

    result = crypto_private(
        "private/user-balance",
        {}
    )

    data = result.get("data", [])

    if not data:
        raise RuntimeError(
            "No account balance returned"
        )

    return data[0]


def balance_for(
    account,
    currency
):

    for item in account.get(
        "position_balances",
        []
    ):

        if item.get(
            "instrument_name"
        ) == currency:

            return Decimal(
                item.get(
                    "quantity",
                    "0"
                )
            )

    return Decimal("0")


def available_balance(
    account,
    currency
):

    quantity = balance_for(
        account,
        currency
    )

    for item in account.get(
        "position_balances",
        []
    ):

        if item.get(
            "instrument_name"
        ) == currency:

            reserved = Decimal(
                item.get(
                    "reserved_qty",
                    "0"
                )
            )

            return max(
                Decimal("0"),
                quantity - reserved
            )

    return Decimal("0")


# ============================================================
# INSTRUMENT INFORMATION
# ============================================================

def get_instrument_info(
    instrument
):

    result = crypto_public(
        "public/get-instruments"
    )

    for item in result.get(
        "data",
        []
    ):

        if item.get(
            "symbol"
        ) == instrument:

            if not item.get(
                "tradable",
                False
            ):

                raise RuntimeError(
                    f"{instrument} is not tradable"
                )

            return item

    raise RuntimeError(
        f"Instrument not found: {instrument}"
    )


def round_quantity(
    quantity,
    tick_size
):

    tick = Decimal(
        str(tick_size)
    )

    return (
        quantity / tick
    ).to_integral_value(
        rounding=ROUND_DOWN
    ) * tick


def decimal_string(value):

    return format(
        value,
        "f"
    )


# ============================================================
# OPEN ORDERS
# ============================================================

def get_open_orders(
    instrument=None
):

    params = {
        "page_size": 200,
        "page": 0
    }

    if instrument:
        params[
            "instrument_name"
        ] = instrument

    result = crypto_private(
        "private/get-open-orders",
        params
    )

    return result.get(
        "order_list",
        result.get("data", [])
    )


# ============================================================
# ORDER DETAIL
# ============================================================

def get_order_detail(
    order_id=None,
    client_oid=None
):

    params = {}

    if order_id is not None:
        params["order_id"] = str(
            order_id
        )

    elif client_oid:
        params["client_oid"] = client_oid

    else:
        raise ValueError(
            "order_id or client_oid required"
        )

    result = crypto_private(
        "private/get-order-detail",
        params
    )

    data = result.get(
        "data",
        []
    )

    if isinstance(data, list):

        if not data:
            return None

        return data[0]

    return data


# ============================================================
# ORDER EXECUTION
# ============================================================

def create_market_order(
    instrument,
    side,
    quantity
):

    client_oid = (
        "grok-"
        + uuid.uuid4().hex[:30]
    )

    params = {
        "instrument_name": instrument,
        "side": side,
        "type": "MARKET",
        "quantity": decimal_string(
            quantity
        ),
        "client_oid": client_oid,
        "spot_margin": "SPOT"
    }

    log(
        f"LIVE ORDER -> "
        f"{side} {quantity} {instrument}"
    )

    result = crypto_private(
        "private/create-order",
        params
    )

    order_id = result.get(
        "order_id"
    )

    if not order_id:
        raise RuntimeError(
            f"Order created without order_id: "
            f"{result}"
        )

    return {
        "order_id": str(order_id),
        "client_oid": client_oid
    }


def wait_for_order(
    order_id,
    client_oid
):

    deadline = (
        time.time()
        + 30
    )

    last = None

    while time.time() < deadline:

        try:

            last = get_order_detail(
                order_id=order_id
            )

            if last:

                status = str(
                    last.get(
                        "status",
                        ""
                    )
                ).upper()

                if status in [
                    "FILLED",
                    "REJECTED",
                    "CANCELED",
                    "EXPIRED"
                ]:

                    return last

        except Exception as e:

            log(
                f"Order status check error: {e}"
            )

        time.sleep(
            ORDER_CHECK_SECONDS
        )

    return last


# ============================================================
# GROK
# ============================================================

def ask_grok(
    market,
    account_summary
):

    portfolio = {
        "USDT": str(
            available_balance(
                account_summary,
                "USDT"
            )
        ),
        "BTC": str(
            available_balance(
                account_summary,
                "BTC"
            )
        ),
        "ETH": str(
            available_balance(
                account_summary,
                "ETH"
            )
        )
    }

    prompt = f"""
You are the decision-making component of a
VERY SMALL SPOT cryptocurrency trading bot.

LIVE TRADING IS ENABLED.

The Python risk engine, NOT you, controls the
hard limits.

Account balances:
{json.dumps(portfolio, indent=2)}

Market data:
{json.dumps(market, indent=2)}

Allowed instruments:
BTC_USDT
ETH_USDT

Trading rules:

1. Spot only.
2. No leverage.
3. No short selling.
4. HOLD is preferred when evidence is weak.
5. Never invent market data.
6. Consider SMA trend, RSI, momentum,
   24-hour movement and spread.
7. Do not recommend a trade merely because
   the model must make a trade.
8. A trade must have a clear reason.
9. size_pct means the percentage of the
   total portfolio that should be traded.
10. Maximum size_pct is 0.30.

Return ONLY this JSON:

{{
  "action": "buy" | "sell" | "hold",
  "instrument": "BTC_USDT" | "ETH_USDT",
  "confidence": 0.0,
  "size_pct": 0.0,
  "reason": "short explanation"
}}
"""

    headers = {
        "Authorization":
            f"Bearer {GROK_API_KEY}",
        "Content-Type":
            "application/json"
    }

    payload = {
        "model": GROK_MODEL,

        "messages": [
            {
                "role": "system",
                "content":
                    "You are a conservative "
                    "crypto trading analyst. "
                    "Return valid JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],

        "temperature": 0.1,

        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name":
                    "trading_decision",

                "strict": True,

                "schema": {
                    "type": "object",

                    "properties": {

                        "action": {
                            "type": "string",
                            "enum": [
                                "buy",
                                "sell",
                                "hold"
                            ]
                        },

                        "instrument": {
                            "type": "string",
                            "enum": [
                                "BTC_USDT",
                                "ETH_USDT"
                            ]
                        },

                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1
                        },

                        "size_pct": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 0.30
                        },

                        "reason": {
                            "type": "string"
                        }
                    },

                    "required": [
                        "action",
                        "instrument",
                        "confidence",
                        "size_pct",
                        "reason"
                    ],

                    "additionalProperties":
                        False
                }
            }
        }
    }

    response = requests.post(
        GROK_URL,
        headers=headers,
        json=payload,
        timeout=45
    )

    response.raise_for_status()

    result = response.json()

    content = (
        result["choices"][0]
        ["message"]
        ["content"]
    )

    return json.loads(content)


# ============================================================
# STATE
# ============================================================

def load_state():

    if not os.path.exists(
        ACCOUNT_STATE_FILE
    ):

        return {
            "day":
                datetime.now(
                    timezone.utc
                ).date().isoformat(),

            "day_start_value":
                None,

            "last_trade_time":
                None,

            "trades_today":
                0
        }

    with open(
        ACCOUNT_STATE_FILE,
        "r"
    ) as f:

        return json.load(f)


def save_state(state):

    tmp = (
        ACCOUNT_STATE_FILE
        + ".tmp"
    )

    with open(
        tmp,
        "w"
    ) as f:

        json.dump(
            state,
            f,
            indent=2
        )

    os.replace(
        tmp,
        ACCOUNT_STATE_FILE
    )


# ============================================================
# PORTFOLIO VALUE
# ==========================================
