import os
import time
import hmac
import hashlib
import json
import uuid
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone

import requests


# ============================================================
# CONFIGURATION
# ============================================================

CRYPTO_BASE = "https://api.crypto.com/exchange/v1"
XAI_URL = "https://api.x.ai/v1/chat/completions"

MODEL = os.getenv("GROK_MODEL", "grok-4.6")

INSTRUMENTS = (
    "BTC_USDT",
    "ETH_USDT",
)

LOOP_SECONDS = int(
    os.getenv("LOOP_SECONDS", "900")
)

MAX_TRADE_PCT = Decimal(
    os.getenv("MAX_TRADE_PCT", "0.10")
)

MIN_CONFIDENCE = float(
    os.getenv("MIN_CONFIDENCE", "0.70")
)

DAILY_LOSS_LIMIT_PCT = Decimal(
    os.getenv("DAILY_LOSS_LIMIT_PCT", "0.05")
)

MAX_SPREAD_PCT = Decimal(
    os.getenv("MAX_SPREAD_PCT", "0.50")
)

MIN_TRADE_USDT = Decimal(
    os.getenv("MIN_TRADE_USDT", "1.00")
)

COOLDOWN_SECONDS = int(
    os.getenv("TRADE_COOLDOWN_SECONDS", "1800")
)

# IMPORTANT:
# false = no real orders
# true = real money
LIVE_TRADING = (
    os.getenv(
        "LIVE_TRADING",
        "false"
    ).lower() == "true"
)

STATE_FILE = os.getenv(
    "ACCOUNT_STATE_FILE",
    "bot_state.json"
)


# ============================================================
# API KEYS
# ============================================================

API_KEY = os.getenv(
    "CRYPTO_API_KEY"
)

API_SECRET = os.getenv(
    "CRYPTO_API_SECRET"
)

GROK_KEY = os.getenv(
    "GROK_API_KEY"
)

if not API_KEY:
    raise RuntimeError(
        "Missing CRYPTO_API_KEY"
    )

if not API_SECRET:
    raise RuntimeError(
        "Missing CRYPTO_API_SECRET"
    )

if not GROK_KEY:
    raise RuntimeError(
        "Missing GROK_API_KEY"
    )


# ============================================================
# REQUEST COUNTERS
# ============================================================

REQUEST_ID = 0
LAST_NONCE = 0


def log(message):
    print(
        f"[{datetime.now(timezone.utc).isoformat()}] "
        f"{message}",
        flush=True
    )


def next_request_id():
    global REQUEST_ID

    REQUEST_ID += 1

    return REQUEST_ID


def next_nonce():
    global LAST_NONCE

    value = int(
        time.time() * 1000
    )

    if value <= LAST_NONCE:
        value = LAST_NONCE + 1

    LAST_NONCE = value

    return value


# ============================================================
# CRYPTO.COM SIGNATURE
# ============================================================

def serialize_params(
    obj,
    level=0
):
    """
    Crypto.com recursive parameter
    serialization used for HMAC signing.
    """

    if level >= 3:
        return str(obj)

    if obj is None:
        return "null"

    if isinstance(obj, dict):

        output = ""

        for key in sorted(obj):

            output += str(key)

            value = obj[key]

            output += serialize_params(
                value,
                level + 1
            )

        return output

    if isinstance(obj, list):

        return "".join(
            serialize_params(
                item,
                level + 1
            )
            for item in obj
        )

    return str(obj)


def private_call(
    method,
    params=None
):

    params = params or {}

    rid = next_request_id()
    n = next_nonce()

    payload = (
        method
        + str(rid)
        + API_KEY
        + serialize_params(params)
        + str(n)
    )

    signature = hmac.new(
        API_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    body = {
        "id": rid,
        "method": method,
        "api_key": API_KEY,
        "params": params,
        "nonce": n,
        "sig": signature,
    }

    response = requests.post(
        f"{CRYPTO_BASE}/{method}",
        json=body,
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    if data.get("code") != 0:

        raise RuntimeError(
            f"Crypto.com {method}: {data}"
        )

    return data.get(
        "result",
        {}
    )


def public_call(
    method,
    params=None
):

    response = requests.get(
        f"{CRYPTO_BASE}/{method}",
        params=params or {},
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    if data.get("code") != 0:

        raise RuntimeError(
            f"Crypto.com {method}: {data}"
        )

    return data.get(
        "result",
        {}
    )


# ============================================================
# ACCOUNT
# ============================================================

def get_balances():

    result = private_call(
        "private/user-balance",
        {}
    )

    data = result.get(
        "data",
        []
    )

    if not data:

        raise RuntimeError(
            "No balance data returned"
        )

    return data[0]


def available(
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

            quantity = Decimal(
                str(
                    item.get(
                        "quantity",
                        "0"
                    )
                )
            )

            reserved = Decimal(
                str(
                    item.get(
                        "reserved_qty",
                        "0"
                    )
                )
            )

            return max(
                Decimal("0"),
                quantity - reserved
            )

    return Decimal("0")


# ============================================================
# MARKET DATA
# ============================================================

def get_ticker(symbol):

    result = public_call(
        "public/get-tickers",
        {
            "instrument_name": symbol
        }
    )

    data = result.get(
        "data",
        []
    )

    if not data:

        raise RuntimeError(
            f"No ticker for {symbol}"
        )

    item = data[0]

    return {
        "price": Decimal(
            str(item["a"])
        ),
        "bid": Decimal(
            str(item["b"])
        ),
        "ask": Decimal(
            str(item["k"])
        ),
        "change": Decimal(
            str(item["c"])
        ) * 100,
        "volume": Decimal(
            str(item["v"])
        ),
    }


def get_candles(symbol):

    result = public_call(
        "public/get-candlestick",
        {
            "instrument_name": symbol,
            "timeframe": "15m",
            "count": 100,
        }
    )

    data = result.get(
        "data",
        []
    )

    if len(data) < 50:

        raise RuntimeError(
            f"Not enough candles for {symbol}"
        )

    return sorted(
        data,
        key=lambda x: int(x["t"])
    )


# ============================================================
# INDICATORS
# ============================================================

def sma(
    values,
    period
):

    if len(values) < period:
        return None

    return (
        sum(values[-period:])
        / Decimal(period)
    )


def rsi(
    values,
    period=14
):

    if len(values) <= period:
        return None

    gains = []
    losses = []

    start = len(values) - period

    for i in range(
        start,
        len(values)
    ):

        change = (
            values[i]
            - values[i - 1]
        )

        gains.append(
            max(
                change,
                Decimal("0")
            )
        )

        losses.append(
            max(
                -change,
                Decimal("0")
            )
        )

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

    rs = (
        average_gain
        / average_loss
    )

    return (
        Decimal("100")
        - (
            Decimal("100")
            / (Decimal("1") + rs)
        )
    )


def market_snapshot(symbol):

    ticker = get_ticker(
        symbol
    )

    candles = get_candles(
        symbol
    )

    closes = [
        Decimal(str(c["c"]))
        for c in candles
    ]

    spread = (
        (
            ticker["ask"]
            - ticker["bid"]
        )
        / ticker["bid"]
        * 100
    )

    momentum = (
        (
            closes[-1]
            / closes[-11]
        )
        - 1
    ) * 100

    return {
        "instrument": symbol,

        "price": str(
            ticker["price"]
        ),

        "bid": str(
            ticker["bid"]
        ),

        "ask": str(
            ticker["ask"]
        ),

        "spread_pct": str(
            spread
        ),

        "change_24h_pct": str(
            ticker["change"]
        ),

        "volume_24h": str(
            ticker["volume"]
        ),

        "sma10": str(
            sma(closes, 10)
        ),

        "sma20": str(
            sma(closes, 20)
        ),

        "sma50": str(
            sma(closes, 50)
        ),

        "rsi14": str(
            rsi(closes, 14)
        ),

        "momentum10_pct": str(
            momentum
        ),
    }


# ============================================================
# PORTFOLIO
# ============================================================

def portfolio_value(
    account
):

    value = available(
        account,
        "USDT"
    )

    for coin, pair in (
        ("BTC", "BTC_USDT"),
        ("ETH", "ETH_USDT"),
    ):

        quantity = available(
            account,
            coin
        )

        if quantity:

            value += (
                quantity
                * get_ticker(pair)["bid"]
            )

    return value


# ============================================================
# STATE
# ============================================================

def load_state():

    if not os.path.exists(
        STATE_FILE
    ):

        return {}

    try:

        with open(
            STATE_FILE
        ) as file:

            return json.load(file)

    except Exception:

        return {}


def save_state(
    state
):

    temporary = (
        STATE_FILE
        + ".tmp"
    )

    with open(
        temporary,
        "w"
    ) as file:

        json.dump(
            state,
            file,
            indent=2
        )

    os.replace(
        temporary,
        STATE_FILE
    )


def daily_loss_ok(
    state,
    current_value
):

    today = (
        datetime.now(
            timezone.utc
        )
        .date()
        .isoformat()
    )

    if (
        state.get("day")
        != today
        or not state.get(
            "day_start_value"
        )
    ):

        state["day"] = today

        state["day_start_value"] = str(
            current_value
        )

        state["trades_today"] = 0

        save_state(state)

        return True

    starting_value = Decimal(
        str(
            state[
                "day_start_value"
            ]
        )
    )

    if starting_value <= 0:
        return True

    loss = (
        starting_value
        - current_value
    ) / starting_value

    if loss >= DAILY_LOSS_LIMIT_PCT:

        log(
            f"DAILY LOSS LIMIT: "
            f"{loss * 100:.2f}%"
        )

        return False

    return True


# ============================================================
# GROK
# ============================================================

def ask_grok(
    markets,
    account
):

    balances = {
        currency: str(
            available(
                account,
                currency
            )
        )
        for currency in (
            "USDT",
            "BTC",
            "ETH",
        )
    }

    prompt = (
        "You are a conservative spot "
        "cryptocurrency trading analyst. "
        "Choose buy, sell, or hold using "
        "ONLY the supplied data. "
        "No leverage. No shorts. "
        "HOLD when evidence is weak. "
        "Maximum size_pct is 0.10.\n\n"
        f"Balances:\n"
        f"{json.dumps(balances)}\n\n"
        f"Markets:\n"
        f"{json.dumps(markets)}"
    )

    schema = {
        "type": "object",

        "properties": {

            "action": {
                "type": "string",
                "enum": [
                    "buy",
                    "sell",
                    "hold",
                ],
            },

            "instrument": {
                "type": "string",
                "enum": list(
                    INSTRUMENTS
                ),
            },

            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
            },

            "size_pct": {
                "type": "number",
                "minimum": 0,
                "maximum": 0.10,
            },

            "reason": {
                "type": "string",
            },
        },

        "required": [
            "action",
            "instrument",
            "confidence",
            "size_pct",
            "reason",
        ],

        "additionalProperties": False,
    }

    body = {
        "model": MODEL,

        "messages": [
            {
                "role": "system",
                "content":
                    "Return only valid JSON "
                    "matching the schema.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],

        "temperature": 0.1,

        "response_format": {
            "type": "json_schema",

            "json_schema": {
                "name":
                    "trade_decision",

                "strict":
                    True,

                "schema":
                    schema,
            },
        },
    }

    response = requests.post(
        XAI_URL,
        headers={
            "Authorization":
                f"Bearer {GROK_KEY}",

            "Content-Type":
                "application/json",
        },
        json=body,
        timeout=60,
    )

    response.raise_for_status()

    result = response.json()

    content = (
        result["choices"][0]
        ["message"]
        ["content"]
    )

    return json.loads(
        content
    )


# ============================================================
# EXCHANGE INFORMATION
# ============================================================

def instrument_info(
    symbol
):

    result = public_call(
        "public/get-instruments"
    )

    for item in result.get(
        "data",
        []
    ):

        if item.get(
            "symbol"
        ) == symbol:

            if not item.get(
                "tradable",
                False
            ):

                raise RuntimeError(
                    f"{symbol} is not tradable"
                )

            return item

    raise RuntimeError(
        f"Instrument not found: {symbol}"
    )


def round_quantity(
    quantity,
    tick_size
):

    tick = Decimal(
        str(tick_size)
    )

    if tick <= 0:
        return quantity

    return (
        quantity / tick
    ).to_integral_value(
        rounding=ROUND_DOWN
    ) * tick


# ============================================================
# OPEN ORDERS
# ============================================================

def open_orders(
    symbol
):

    result = private_call(
        "private/get-open-orders",
        {
            "instrument_name": symbol,
            "page_size": 200,
            "page": 0,
        }
    )

    return result.get(
        "order_list",
        result.get(
            "data",
            []
        )
    )


# ============================================================
# CREATE ORDER
# ============================================================

def create_market_order(
    symbol,
    side,
    quantity
):

    client_oid = (
        "grok-"
        + uuid.uuid4().hex[:24]
    )

    params = {
        "instrument_name": symbol,

        "side": side,

        "type": "MARKET",

        "quantity": format(
            quantity,
            "f"
        ),

        "client_oid": client_oid,

        "spot_margin": "SPOT",
    }

    return private_call(
        "private/create-order",
        params
    )


# ============================================================
# EXECUTION
# ============================================================

def execute_trade(
    decision,
    account,
    portfolio,
    state,
    market
):

    action = decision["action"]

    symbol = decision["instrument"]

    confidence = float(
        decision["confidence"]
    )

    size_pct = Decimal(
        str(
            decision["size_pct"]
        )
    )

    spread = Decimal(
        str(
            market["spread_pct"]
        )
    )

    # --------------------------------------------------------
    # HOLD
    # --------------------------------------------------------

    if action == "hold":

        log(
            f"HOLD {symbol} | "
            f"confidence={confidence:.2f} | "
            f"{decision['reason']}"
        )

        return

    # --------------------------------------------------------
    # HARD RISK CHECKS
    # --------------------------------------------------------

    if confidence < MIN_CONFIDENCE:

        log(
            "RISK REJECT: "
            "confidence too low"
        )

        return

    if (
        size_pct <= 0
        or size_pct > MAX_TRADE_PCT
    ):

        log(
            "RISK REJECT: "
            "invalid trade size"
        )

        return

    if spread > MAX_SPREAD_PCT:

        log(
            f"RISK REJECT: "
            f"spread={spread}%"
        )

        return

    last_trade = state.get(
        "last_trade_time"
    )

    if last_trade:

        elapsed = (
            time.time()
            - float(last_trade)
        )

        if elapsed < COOLDOWN_SECONDS:

            log(
                "RISK REJECT: "
                "trade cooldown active"
            )

            return

    # --------------------------------------------------------
    # OPEN ORDER CHECK
    # --------------------------------------------------------

    if open_orders(symbol):

        log(
            f"RISK REJECT: "
            f"open order exists for "
            f"{symbol}"
        )

        return

    # --------------------------------------------------------
    # PRICE
    # --------------------------------------------------------

    ticker_data = get_ticker(
        symbol
    )

    if action == "buy":
        price = ticker_data["ask"]
    else:
        price = ticker_data["bid"]

    if price <= 0:

        log(
            "RISK REJECT: "
            "invalid market price"
        )

        return

    # --------------------------------------------------------
    # TRADE VALUE
    # --------------------------------------------------------

    target_value = (
        portfolio
        * size_pct
    )

    if target_value < MIN_TRADE_USDT:

        log(
            f"RISK REJECT: "
            f"trade value ${target_value:.4f} "
            f"is below ${MIN_TRADE_USDT}"
        )

        return

    # --------------------------------------------------------
    # CALCULATE QUANTITY
    # --------------------------------------------------------

    if action == "buy":

        usdt = available(
            account,
            "USDT"
        )

        spend = min(
            target_value,
            usdt
        )

        if spend < MIN_TRADE_USDT:

            log(
                "BUY REJECT: "
                "insufficient USDT"
            )

            return

        quantity = (
            spend / price
        )

    else:

        if symbol == "BTC_USDT":
            coin = "BTC"
        else:
            coin = "ETH"

        coin_avai
