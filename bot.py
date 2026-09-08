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

# 15 minutes between decisions
LOOP_SECONDS = int(
    os.getenv("LOOP_SECONDS", "900")
)

# Grok must have at least this confidence
MIN_CONFIDENCE = float(
    os.getenv("MIN_CONFIDENCE", "0.70")
)

# Maximum portion of total portfolio used by one trade
MAX_TRADE_PCT = Decimal(
    os.getenv("MAX_TRADE_PCT", "0.10")
)

# Maximum percentage loss from the beginning of the UTC day
DAILY_LOSS_LIMIT_PCT = Decimal(
    os.getenv("DAILY_LOSS_LIMIT_PCT", "0.05")
)

# Ignore markets with excessive bid/ask spread
MAX_SPREAD_PCT = Decimal(
    os.getenv("MAX_SPREAD_PCT", "0.50")
)

# Don't bother attempting microscopic trades
MIN_TRADE_USDT = Decimal(
    os.getenv("MIN_TRADE_USDT", "1.00")
)

# Prevent repeatedly trading the same market too quickly
TRADE_COOLDOWN_SECONDS = int(
    os.getenv("TRADE_COOLDOWN_SECONDS", "1800")
)

# Order status polling
ORDER_CHECK_SECONDS = 2
ORDER_TIMEOUT_SECONDS = 30

# IMPORTANT:
# false = NO REAL ORDERS
# true  = REAL MONEY
LIVE_TRADING = os.getenv(
    "LIVE_TRADING",
    "false"
).lower() == "true"

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
        f"[{datetime.now(timezone.utc).isoformat()}] {message}",
        flush=True
    )


# ============================================================
# GLOBAL REQUEST COUNTERS
# ============================================================

_request_id = 0
_last_nonce = 0


def next_request_id():
    global _request_id

    _request_id += 1

    return _request_id


def next_nonce():
    global _last_nonce

    nonce = int(time.time() * 1000)

    if nonce <= _last_nonce:
        nonce = _last_nonce + 1

    _last_nonce = nonce

    return nonce


# ============================================================
# CRYPTO.COM PARAMETER SERIALIZATION
# ============================================================

def params_to_string(obj, level=0):
    """
    Crypto.com HMAC parameter serialization.
    """

    max_level = 3

    if level >= max_level:
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

    param_string = params_to_string(params)

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
# CRYPTO.COM PUBLIC API
# ============================================================

def crypto_public(
    method,
    params=None
):

    url = f"{CRYPTO_BASE_URL}/{method}"

    response = requests.get(
        url,
        params=params or {},
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    if data.get("code") != 0:
        raise RuntimeError(
            f"Crypto.com public API error: {data}"
        )

    return data.get("result", {})


# ============================================================
# CRYPTO.COM PRIVATE API
# ============================================================

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
            f"Crypto.com private API error: {data}"
        )

    return data.get("result", {})


# ============================================================
# TICKER
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
            f"No ticker returned for {instrument}"
        )

    ticker = data[0]

    return {
        "price": Decimal(str(ticker["a"])),
        "bid": Decimal(str(ticker["b"])),
        "ask": Decimal(str(ticker["k"])),
        "high": Decimal(str(ticker["h"])),
        "low": Decimal(str(ticker["l"])),
        "volume": Decimal(str(ticker["v"])),
        "change_24h": Decimal(str(ticker["c"])) * 100
    }


# ============================================================
# CANDLE DATA
# ============================================================

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
# TECHNICAL INDICATORS
# ============================================================

def sma(values, period):

    if len(values) < period:
        return None

    return (
        sum(values[-period:])
        / Decimal(period)
    )


def rsi(values, period=14):

    if len(values) <= period:
        return None

    gains = []
    losses = []

    start = len(values) - period

    for i in range(start, len(values)):

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

    return (
        Decimal("100")
        - (
            Decimal("100")
            / (Decimal("1") + rs)
        )
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
        ((new / old) - 1)
        * 100
    )


# ============================================================
# MARKET SNAPSHOT
# ============================================================

def market_snapshot(instrument):

    ticker = get_ticker(instrument)

    candles = get_candles(instrument)

    closes = [
        Decimal(str(c["c"]))
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

        "24h_high": str(
            ticker["high"]
        ),

        "24h_low": str(
            ticker["low"]
        ),

        "24h_volume": str(
            ticker["volume"]
        ),

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
# ACCOUNT BALANCES
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


def position_balances(account):

    return account.get(
        "position_balances",
        []
    )


def balance_for(
    account,
    currency
):

    for item in position_balances(account):

        instrument = item.get(
            "instrument_name"
        )

        if instrument == currency:

            return Decimal(
                str(
                    item.get(
                        "quantity",
                        "0"
                    )
                )
            )

    return Decimal("0")


def available_balance(
    account,
    currency
):

    for item in position_balances(account):

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
# INSTRUMENT INFORMATION
# ============================================================

def get_instrument_info(instrument):

    result = crypto_public(
        "public/get-instruments"
    )

    for item in result.get(
        "data",
        []
    ):

        symbol = item.get("symbol")

        if symbol == instrument:

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

    if tick <= 0:
        return quantity

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
        result.get(
            "data",
            []
        )
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
# CREATE MARKET ORDER
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
        f"ORDER REQUEST: "
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
            f"No order_id returned: {result}"
        )

    return {
        "order_id": str(order_id),
        "client_oid": client_oid
    }


# ============================================================
# WAIT FOR ORDER
# ============================================================

def wait_for_order(
    order_id
):

    deadline = (
        time.time()
        + ORDER_TIMEOUT_SECONDS
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

                log(
                    f"ORDER STATUS: "
                    f"{status}"
                )

                if status in (
                    "FILLED",
                    "REJECTED",
                    "CANCELED",
                    "EXPIRED"
                ):

                    return last

        except Exception as e:

            log(
                f"Order status error: {e}"
            )

        time.sleep(
            ORDER_CHECK_SECONDS
        )

    return last


# ============================================================
# PORTFOLIO VALUE
# ============================================================

def portfolio_value_usdt(account):

    usdt = available_balance(
        account,
        "USDT"
    )

    btc = available_balance(
        account,
        "BTC"
    )

    eth = available_balance(
        account,
        "ETH"
    )

    btc_value = Decimal("0")
    eth_value = Decimal("0")

    if btc > 0:

        btc_ticker = get_ticker(
            "BTC_USDT"
        )

        btc_value = (
            btc
            * btc_ticker["bid"]
        )

    if eth > 0:

        eth_ticker = get_ticker(
            "ETH_USDT"
        )

        eth_value = (
            eth
            * eth_ticker["bid"]
        )

    total = (
        usdt
        + btc_value
        + eth_value
    )

    return total


# ============================================================
# STATE
# ============================================================

def default_state():

    return {
        "day":
            datetime.now(
                timezone.utc
            ).date().isoformat(),

        "day_start_value":
            None,

        "last_trade_time":
            None,

        "last_trade_instrument":
            None,

        "trades_today":
            0
    }


def load_state():

    if not os.path.exists(
        ACCOUNT_STATE_FILE
    ):

        return default_state()

    try:

        with open(
            ACCOUNT_STATE_FILE,
            "r"
        ) as f:

            state = json.load(f)

        defaults = default_state()

        for key, value in defaults.items():

            if key not in state:
                state[key] = value

        return state

    except Exception as e:

        log(
            f"Could not load state: {e}"
        )

        return default_state()


def save_state(state):

    temporary = (
        ACCOUNT_STATE_FILE
        + ".tmp"
    )

    with open(
        temporary,
        "w"
    ) as f:

        json.dump(
            state,
            f,
            indent=2
        )

    os.replace(
        temporary,
        ACCOUNT_STATE_FILE
    )


# ============================================================
# DAILY LOSS PROTECTION
# ============================================================

def check_daily_loss(
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

    if state.get("day") != today:

        state["day"] = today

        state["day_start_value"] = str(
            current_value
        )

        state["trades_today"] = 0

        state["last_trade_time"] = None

        state["last_trade_instrument"] = None

        save_state(state)

        log(
            f"New UTC trading day. "
            f"Starting value: "
            f"${current_value:.4f}"
        )

        return True

    if state.get(
        "day_start_value"
    ) is None:

        state["day_start_value"] = str(
            current_value
        )

        save_state(state)

        log(
            f"Daily starting value set: "
            f"${current_value:.4f}"
        )

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

    loss_pct = (
        (starting_value - current_value)
        / starting_value
        * 100
    )

    log(
        f"Daily P/L: "
        f"{loss_pct:.2f}%"
    )

    max_loss_pct = (
        DAILY_LOSS_LIMIT_PCT
        * 100
    )

    if loss_pct >= max_loss_pct:

        log(
            "DAILY LOSS LIMIT REACHED. "
            "NO NEW TRADES."
        )

        return False

    return True


# ============================================================
# GROK DECISION
# ============================================================

def ask_grok(
    market_data,
    account
):

    portfolio = {
        "USDT": str(
            available_balanc
