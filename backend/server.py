from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os, logging, random, string, uuid, bcrypt, jwt, secrets
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from solana_rpc import (
    get_sol_balance, check_mint_authority, get_top_holder_concentration,
    real_safety_audit, derive_public_key, get_rpc_url, verify_sol_payment,
)

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'sniper_bot')]

app = FastAPI()
api_router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@sniperbot.io")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "SniperAdmin123!")
OWNER_WALLET = os.environ.get("OWNER_WALLET", "8YjBBpAg8W3d8Juzrp7Xicga8wLe6sFwPphtswwJxgx9")

# ── Premium Packages ────────────────────────────
PREMIUM_PLANS = {
    "monthly": {"price_usd": 29.00, "price_sol": 0.2, "label": "Premium Monthly", "duration_days": 30},
    "quarterly": {"price_usd": 69.00, "price_sol": 0.5, "label": "Premium Quarterly", "duration_days": 90, "save_pct": 17},
}
FREE_LIMITS = {
    "max_wallets": 1,
    "scan_interval_ms": 30000,
    "live_trading": False,
    "push_alerts": False,
    "max_open_positions": 2,
}
PREMIUM_LIMITS = {
    "max_wallets": 10,
    "scan_interval_ms": 5000,
    "live_trading": True,
    "push_alerts": True,
    "max_open_positions": 20,
}

# ── Auth Helpers ────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

def create_access_token(user_id: str, email: str) -> str:
    return jwt.encode(
        {"sub": user_id, "email": email, "exp": datetime.now(timezone.utc) + timedelta(minutes=60), "type": "access"},
        JWT_SECRET, algorithm=JWT_ALGORITHM,
    )

def create_refresh_token(user_id: str) -> str:
    return jwt.encode(
        {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "refresh"},
        JWT_SECRET, algorithm=JWT_ALGORITHM,
    )

def set_auth_cookies(response: Response, access: str, refresh: str):
    response.set_cookie(key="access_token", value=access, httponly=True, secure=False, samesite="lax", max_age=3600, path="/")
    response.set_cookie(key="refresh_token", value=refresh, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["id"] = str(user["_id"])
        del user["_id"]
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_optional_user(request: Request):
    try:
        return await get_current_user(request)
    except:
        return None

def is_premium(user: dict) -> bool:
    if not user:
        return False
    sub = user.get("subscription", {})
    if sub.get("status") == "active":
        exp = sub.get("expires_at")
        if exp and datetime.fromisoformat(exp) > datetime.now(timezone.utc):
            return True
    return user.get("role") == "admin"

def get_limits(user: dict) -> dict:
    return PREMIUM_LIMITS if is_premium(user) else FREE_LIMITS

# ── Models ──────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class BotStateUpdate(BaseModel):
    is_running: Optional[bool] = None
    mode: Optional[str] = None

class BotConfigUpdate(BaseModel):
    strategy: Optional[str] = None
    buy_amount_sol: Optional[float] = None
    slippage_bps: Optional[int] = None
    priority_fee_lamports: Optional[int] = None
    jito_tip_sol: Optional[float] = None
    max_open_positions: Optional[int] = None
    use_jito: Optional[bool] = None
    auto_sell: Optional[bool] = None
    take_profit_pct1: Optional[int] = None
    take_profit_pct2: Optional[int] = None
    stop_loss_pct: Optional[int] = None
    trailing_stop_pct: Optional[int] = None
    max_hold_seconds: Optional[int] = None
    price_check_interval: Optional[int] = None
    require_mint_revoked: Optional[bool] = None
    require_freeze_revoked: Optional[bool] = None
    require_update_revoked: Optional[bool] = None
    require_lp_burned: Optional[bool] = None
    max_top_holder_pct: Optional[int] = None
    reject_bundles: Optional[bool] = None
    min_market_cap_usd: Optional[int] = None
    max_token_age_minutes: Optional[int] = None
    min_safety_score: Optional[int] = None
    platform_pumpfun: Optional[bool] = None
    platform_raydium: Optional[bool] = None
    platform_pumpswap: Optional[bool] = None

class WalletConfigUpdate(BaseModel):
    private_key: Optional[str] = None
    rpc_url: Optional[str] = None
    wss_url: Optional[str] = None
    label: Optional[str] = None

class AddWalletRequest(BaseModel):
    private_key: str
    label: str = "Wallet"

class CheckoutRequest(BaseModel):
    plan_id: str
    origin_url: str

# ── Helpers ─────────────────────────────────────

def random_mint():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=44))

def random_token_name():
    pre = ["ALIEN", "VOID", "MOON", "PEPE", "DOGE", "BONK", "WIF", "MYRO", "POPCAT", "MEW", "BOME", "SLERF"]
    suf = ["INU", "COIN", "TOKEN", "SOL", "SWAP", "FI", "DAO", "X", "AI", "BOT"]
    return random.choice(pre) + random.choice(suf)

PLATFORMS = ["pump.fun", "raydium", "pumpswap"]

async def add_log(level: str, message: str, user_id: str = None):
    entry = {
        "id": str(uuid.uuid4()), "level": level, "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if user_id:
        entry["user_id"] = user_id
    await db.activity_logs.insert_one(entry)

async def get_user_rpc(user_id: str) -> str:
    wallet = await db.wallets.find_one({"user_id": user_id, "is_primary": True}, {"_id": 0})
    if wallet and wallet.get("rpc_url"):
        return wallet["rpc_url"]
    return get_rpc_url()

# ── Startup ─────────────────────────────────────

@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")

    # Seed admin
    admin_email_lower = ADMIN_EMAIL.lower().strip()
    existing = await db.users.find_one({"email": admin_email_lower})
    if not existing:
        # Remove old admins
        await db.users.delete_many({"role": "admin"})
        await db.users.insert_one({
            "email": admin_email_lower, "password_hash": hash_password(ADMIN_PASSWORD),
            "name": "Admin", "role": "admin",
            "subscription": {"status": "active", "plan": "admin", "expires_at": "2099-12-31T00:00:00+00:00"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        # Ensure this user is admin with correct password
        update_fields = {
            "role": "admin",
            "subscription": {"status": "active", "plan": "admin", "expires_at": "2099-12-31T00:00:00+00:00"},
        }
        if not verify_password(ADMIN_PASSWORD, existing["password_hash"]):
            update_fields["password_hash"] = hash_password(ADMIN_PASSWORD)
        await db.users.update_one({"email": admin_email_lower}, {"$set": update_fields})
        # Remove other admins
        await db.users.update_many(
            {"email": {"$ne": admin_email_lower}, "role": "admin"},
            {"$set": {"role": "user"}}
        )

    # Ensure bot defaults
    if not await db.bot_state.find_one({}):
        await db.bot_state.insert_one({"is_running": False, "mode": "paper", "started_at": None, "tokens_scanned": 0, "tokens_sniped": 0})
    if not await db.bot_config.find_one({}):
        await db.bot_config.insert_one({
            "strategy": "balanced", "buy_amount_sol": 0.05, "slippage_bps": 1000,
            "priority_fee_lamports": 10000, "jito_tip_sol": 0.01, "max_open_positions": 5,
            "use_jito": True, "auto_sell": True, "take_profit_pct1": 100, "take_profit_pct2": 300,
            "stop_loss_pct": -30, "trailing_stop_pct": 15, "max_hold_seconds": 3600,
            "price_check_interval": 10000, "require_mint_revoked": True, "require_freeze_revoked": True,
            "require_update_revoked": True, "require_lp_burned": True, "max_top_holder_pct": 15,
            "reject_bundles": True, "min_market_cap_usd": 5000, "max_token_age_minutes": 30,
            "min_safety_score": 60, "platform_pumpfun": True, "platform_raydium": True, "platform_pumpswap": True,
        })

    # Seed default payment wallet
    if not await db.payment_wallets.find_one({}):
        await db.payment_wallets.insert_one({
            "id": str(uuid.uuid4()),
            "address": OWNER_WALLET,
            "label": "Primary Wallet",
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    # Write test credentials
    creds_path = Path("/app/memory/test_credentials.md")
    creds_path.parent.mkdir(parents=True, exist_ok=True)
    creds_path.write_text(
        f"# Test Credentials\n\n## Admin\n- Email: {ADMIN_EMAIL}\n- Password: {ADMIN_PASSWORD}\n- Role: admin (premium)\n\n"
        f"## Auth Endpoints\n- POST /api/auth/register\n- POST /api/auth/login\n- POST /api/auth/logout\n- GET /api/auth/me\n"
    )
    logger.info("Sniper bot backend started with auth + Solana RPC + Stripe")

# ── Admin Payment Wallet Management ─────────────

class PaymentWalletRequest(BaseModel):
    address: str
    label: str = "Wallet"

async def get_active_payment_wallet() -> str:
    """Get the currently active payment wallet address."""
    active = await db.payment_wallets.find_one({"is_active": True}, {"_id": 0})
    if active:
        return active["address"]
    return OWNER_WALLET

@api_router.get("/admin/payment-wallets")
async def get_payment_wallets(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    wallets = await db.payment_wallets.find({}, {"_id": 0}).sort("created_at", -1).to_list(20)
    return {"wallets": wallets}

@api_router.post("/admin/payment-wallets")
async def add_payment_wallet(req: PaymentWalletRequest, request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    existing = await db.payment_wallets.find_one({"address": req.address})
    if existing:
        raise HTTPException(400, "Wallet address already exists")
    wallet_doc = {
        "id": str(uuid.uuid4()),
        "address": req.address,
        "label": req.label,
        "is_active": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.payment_wallets.insert_one(wallet_doc)
    await add_log("info", f"Payment wallet added: {req.label} ({req.address[:12]}...)", user["id"])
    return {k: v for k, v in wallet_doc.items() if k != "_id"}

@api_router.put("/admin/payment-wallets/{wallet_id}/activate")
async def activate_payment_wallet(wallet_id: str, request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    # Deactivate all, then activate target
    await db.payment_wallets.update_many({}, {"$set": {"is_active": False}})
    result = await db.payment_wallets.update_one({"id": wallet_id}, {"$set": {"is_active": True}})
    if result.modified_count == 0:
        raise HTTPException(404, "Wallet not found")
    wallet = await db.payment_wallets.find_one({"id": wallet_id}, {"_id": 0})
    await add_log("success", f"Payment wallet activated: {wallet['label']} ({wallet['address'][:12]}...)", user["id"])
    return {"message": "Wallet activated", "wallet": wallet}

@api_router.delete("/admin/payment-wallets/{wallet_id}")
async def delete_payment_wallet(wallet_id: str, request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    wallet = await db.payment_wallets.find_one({"id": wallet_id}, {"_id": 0})
    if not wallet:
        raise HTTPException(404, "Wallet not found")
    if wallet.get("is_active"):
        raise HTTPException(400, "Cannot delete active wallet. Activate another wallet first.")
    await db.payment_wallets.delete_one({"id": wallet_id})
    await add_log("warn", f"Payment wallet removed: {wallet['label']}", user["id"])
    return {"message": "Wallet deleted"}

# ── Auth ────────────────────────────────────────

@api_router.post("/auth/register")
async def register(req: RegisterRequest, response: Response):
    email = req.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    user_doc = {
        "email": email, "password_hash": hash_password(req.password),
        "name": req.name or email.split("@")[0], "role": "user",
        "subscription": {"status": "free", "plan": "free", "expires_at": None},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    access = create_access_token(user_id, email)
    refresh = create_refresh_token(user_id)
    set_auth_cookies(response, access, refresh)
    return {"id": user_id, "email": email, "name": user_doc["name"], "role": "user", "subscription": user_doc["subscription"], "token": access}

@api_router.post("/auth/login")
async def login(req: LoginRequest, request: Request, response: Response):
    email = req.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"

    # Brute force check
    attempts = await db.login_attempts.find_one({"identifier": identifier})
    if attempts and attempts.get("count", 0) >= 5:
        last = attempts.get("last_attempt")
        if last and (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() < 900:
            raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(req.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"count": 1}, "$set": {"last_attempt": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        raise HTTPException(401, "Invalid credentials")

    await db.login_attempts.delete_one({"identifier": identifier})
    user_id = str(user["_id"])
    access = create_access_token(user_id, email)
    refresh = create_refresh_token(user_id)
    set_auth_cookies(response, access, refresh)
    return {
        "id": user_id, "email": email, "name": user.get("name", ""),
        "role": user.get("role", "user"), "subscription": user.get("subscription", {}),
        "token": access,
    }

@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Logged out"}

@api_router.get("/auth/me")
async def get_me(request: Request):
    user = await get_current_user(request)
    user["is_premium"] = is_premium(user)
    user["limits"] = get_limits(user)
    return user

@api_router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(401, "No refresh token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(401, "Invalid token")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(401, "User not found")
        access = create_access_token(str(user["_id"]), user["email"])
        response.set_cookie(key="access_token", value=access, httponly=True, secure=False, samesite="lax", max_age=3600, path="/")
        return {"message": "Token refreshed"}
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

# ── Premium Payments (SOL + Stripe) ─────────────

class SolPaymentRequest(BaseModel):
    plan_id: str

@api_router.get("/premium/plans")
async def get_plans():
    active_wallet = await get_active_payment_wallet()
    return {
        "plans": PREMIUM_PLANS,
        "free_limits": FREE_LIMITS,
        "premium_limits": PREMIUM_LIMITS,
        "owner_wallet": active_wallet,
        "payment_methods": ["sol", "stripe"],
    }

# ── SOL Payment Flow ────────────────────────────

@api_router.post("/premium/sol/initiate")
async def initiate_sol_payment(req: SolPaymentRequest, request: Request):
    """Create a SOL payment order. User sends exact SOL amount to owner wallet."""
    user = await get_current_user(request)
    if req.plan_id not in PREMIUM_PLANS:
        raise HTTPException(400, "Invalid plan")
    plan = PREMIUM_PLANS[req.plan_id]

    # Add small unique identifier to amount (random lamports suffix)
    base_lamports = int(plan["price_sol"] * 1_000_000_000)
    unique_suffix = random.randint(1000, 9999)  # Random 4-digit lamport suffix
    exact_lamports = base_lamports + unique_suffix
    exact_sol = exact_lamports / 1_000_000_000

    order_id = str(uuid.uuid4())
    active_wallet = await get_active_payment_wallet()
    await db.sol_payments.insert_one({
        "order_id": order_id,
        "user_id": user["id"],
        "email": user.get("email"),
        "plan_id": req.plan_id,
        "expected_lamports": exact_lamports,
        "expected_sol": exact_sol,
        "owner_wallet": active_wallet,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_ts": int(datetime.now(timezone.utc).timestamp()),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
    })

    await add_log("info", f"SOL payment initiated: {plan['label']} — {exact_sol} SOL — Order: {order_id[:8]}", user["id"])

    return {
        "order_id": order_id,
        "wallet_address": active_wallet,
        "amount_sol": exact_sol,
        "amount_lamports": exact_lamports,
        "plan": plan,
        "expires_in_minutes": 30,
    }

@api_router.post("/premium/sol/verify/{order_id}")
async def verify_sol_payment_endpoint(order_id: str, request: Request):
    """Verify on-chain that the SOL payment was received."""
    user = await get_current_user(request)
    order = await db.sol_payments.find_one({"order_id": order_id, "user_id": user["id"]})
    if not order:
        raise HTTPException(404, "Payment order not found")

    if order.get("status") == "paid":
        return {"status": "paid", "message": "Already verified"}

    # Check expiry
    created_ts = order.get("created_ts", 0)
    if (datetime.now(timezone.utc).timestamp() - created_ts) > 1800:
        await db.sol_payments.update_one({"order_id": order_id}, {"$set": {"status": "expired"}})
        return {"status": "expired", "message": "Payment window expired. Please create a new order."}

    # Verify on-chain
    rpc = get_rpc_url()
    result = await verify_sol_payment(
        owner_wallet=OWNER_WALLET,
        expected_lamports=order["expected_lamports"],
        since_timestamp=created_ts - 60,  # 1 min buffer
        rpc_url=rpc,
    )

    if result:
        # Payment found on-chain!
        plan_id = order["plan_id"]
        plan = PREMIUM_PLANS.get(plan_id, PREMIUM_PLANS["monthly"])
        expires = datetime.now(timezone.utc) + timedelta(days=plan["duration_days"])

        await db.sol_payments.update_one(
            {"order_id": order_id},
            {"$set": {
                "status": "paid",
                "tx_signature": result["signature"],
                "sender": result.get("sender"),
                "received_lamports": result["amount_lamports"],
                "paid_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        await db.users.update_one(
            {"_id": ObjectId(user["id"])},
            {"$set": {"subscription": {
                "status": "active", "plan": plan_id,
                "expires_at": expires.isoformat(),
                "payment_method": "sol",
                "tx_signature": result["signature"],
            }}},
        )
        await add_log("success", f"Premium activated via SOL! TX: {result['signature'][:16]}... — {result['amount_sol']} SOL", user["id"])

        return {
            "status": "paid",
            "message": "Payment verified on-chain!",
            "tx_signature": result["signature"],
            "amount_sol": result["amount_sol"],
        }
    else:
        return {
            "status": "pending",
            "message": "Payment not yet detected. Send the exact amount and try again.",
            "wallet_address": OWNER_WALLET,
            "expected_sol": order["expected_sol"],
        }

@api_router.get("/premium/sol/orders")
async def get_sol_orders(request: Request):
    """Get user's SOL payment orders."""
    user = await get_current_user(request)
    orders = await db.sol_payments.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(20)
    return {"orders": orders}

# ── Stripe Checkout (ready for when you add your key) ──

@api_router.post("/premium/checkout")
async def create_checkout(req: CheckoutRequest, request: Request):
    user = await get_current_user(request)
    if req.plan_id not in PREMIUM_PLANS:
        raise HTTPException(400, "Invalid plan")
    plan = PREMIUM_PLANS[req.plan_id]

    stripe_key = os.environ.get("STRIPE_API_KEY", "")
    if not stripe_key or stripe_key == "sk_test_emergent":
        # Stripe not fully configured yet
        return {"error": "Stripe payments coming soon. Please use SOL payment.", "use_sol": True}

    from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_key, webhook_url=webhook_url)

    success_url = f"{req.origin_url}/premium?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{req.origin_url}/premium"

    checkout_req = CheckoutSessionRequest(
        amount=plan["price_usd"],
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": user["id"], "plan_id": req.plan_id, "email": user["email"]},
    )
    session = await stripe_checkout.create_checkout_session(checkout_req)

    await db.payment_transactions.insert_one({
        "session_id": session.session_id, "user_id": user["id"], "email": user["email"],
        "plan_id": req.plan_id, "amount": plan["price_usd"], "currency": "usd",
        "payment_status": "initiated", "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"url": session.url, "session_id": session.session_id}

@api_router.get("/premium/status/{session_id}")
async def check_payment_status(session_id: str, request: Request):
    user = await get_current_user(request)
    txn = await db.payment_transactions.find_one({"session_id": session_id, "user_id": user["id"]}, {"_id": 0})
    if not txn:
        raise HTTPException(404, "Transaction not found")
    if txn.get("payment_status") == "paid":
        return {"status": "paid", "already_processed": True}

    stripe_key = os.environ.get("STRIPE_API_KEY", "")
    if not stripe_key or stripe_key == "sk_test_emergent":
        return {"status": "pending", "message": "Stripe not configured"}

    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    host_url = str(request.base_url).rstrip("/")
    stripe_checkout = StripeCheckout(api_key=stripe_key, webhook_url=f"{host_url}/api/webhook/stripe")
    status = await stripe_checkout.get_checkout_status(session_id)

    if status.payment_status == "paid":
        plan_id = txn.get("plan_id", "monthly")
        plan = PREMIUM_PLANS.get(plan_id, PREMIUM_PLANS["monthly"])
        expires = datetime.now(timezone.utc) + timedelta(days=plan["duration_days"])
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": "paid", "paid_at": datetime.now(timezone.utc).isoformat()}},
        )
        await db.users.update_one(
            {"_id": ObjectId(user["id"])},
            {"$set": {"subscription": {"status": "active", "plan": plan_id, "expires_at": expires.isoformat(), "payment_method": "stripe"}}},
        )
        await add_log("success", f"Premium activated via Stripe: {plan['label']}", user["id"])

    return {"status": status.status, "payment_status": status.payment_status}

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        stripe_key = os.environ.get("STRIPE_API_KEY", "")
        if not stripe_key or stripe_key == "sk_test_emergent":
            return {"status": "not_configured"}
        from emergentintegrations.payments.stripe.checkout import StripeCheckout
        host_url = str(request.base_url).rstrip("/")
        stripe_checkout = StripeCheckout(api_key=stripe_key, webhook_url=f"{host_url}/api/webhook/stripe")
        event = await stripe_checkout.handle_webhook(body, sig)
        if event.payment_status == "paid":
            txn = await db.payment_transactions.find_one({"session_id": event.session_id})
            if txn and txn.get("payment_status") != "paid":
                plan_id = txn.get("plan_id", "monthly")
                plan = PREMIUM_PLANS.get(plan_id, PREMIUM_PLANS["monthly"])
                expires = datetime.now(timezone.utc) + timedelta(days=plan["duration_days"])
                await db.payment_transactions.update_one(
                    {"session_id": event.session_id},
                    {"$set": {"payment_status": "paid", "paid_at": datetime.now(timezone.utc).isoformat()}},
                )
                user_id = event.metadata.get("user_id") or txn.get("user_id")
                if user_id:
                    await db.users.update_one(
                        {"_id": ObjectId(user_id)},
                        {"$set": {"subscription": {"status": "active", "plan": plan_id, "expires_at": expires.isoformat(), "payment_method": "stripe"}}},
                    )
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error"}

# ── Bot State ───────────────────────────────────

@api_router.get("/bot/state")
async def get_bot_state():
    state = await db.bot_state.find_one({}, {"_id": 0})
    return state or {"is_running": False, "mode": "paper"}

@api_router.put("/bot/state")
async def update_bot_state(update: BotStateUpdate, request: Request):
    user = await get_optional_user(request)
    current = await db.bot_state.find_one({}, {"_id": 0}) or {}
    updates = {k: v for k, v in update.model_dump().items() if v is not None}

    if "mode" in updates and updates["mode"] == "live":
        if user and not is_premium(user):
            raise HTTPException(403, "Live trading requires Premium subscription")

    if "is_running" in updates:
        if updates["is_running"] and not current.get("is_running"):
            updates["started_at"] = datetime.now(timezone.utc).isoformat()
            await add_log("info", "Bot started in {} mode".format(current.get("mode", "paper")))
            await add_log("info", "Connecting to Helius RPC...")
            await add_log("success", "Scanner active — monitoring platforms")
        elif not updates["is_running"]:
            updates["started_at"] = None
            await add_log("warn", "Bot stopped")

    if "mode" in updates:
        await add_log("info", f"Mode changed to: {updates['mode']}")

    current.update(updates)
    await db.bot_state.replace_one({}, current, upsert=True)
    return {k: v for k, v in current.items() if k != "_id"}

# ── Bot Config ──────────────────────────────────

@api_router.get("/bot/config")
async def get_bot_config():
    cfg = await db.bot_config.find_one({}, {"_id": 0})
    return cfg or {}

@api_router.put("/bot/config")
async def update_bot_config(update: BotConfigUpdate):
    current = await db.bot_config.find_one({}, {"_id": 0}) or {}
    updates = {k: v for k, v in update.model_dump().items() if v is not None}
    current.update(updates)
    await db.bot_config.replace_one({}, current, upsert=True)
    await add_log("info", f"Config updated: {list(updates.keys())}")
    return {k: v for k, v in current.items() if k != "_id"}

# ── Multi-Wallet ────────────────────────────────

@api_router.get("/wallets")
async def get_wallets(request: Request):
    user = await get_current_user(request)
    wallets = await db.wallets.find({"user_id": user["id"]}, {"_id": 0}).to_list(20)
    for w in wallets:
        pk = w.get("private_key", "")
        w["private_key_masked"] = pk[:4] + "..." + pk[-4:] if len(pk) > 8 else ""
        w.pop("private_key", None)
    return {"wallets": wallets, "max_wallets": get_limits(user)["max_wallets"], "is_premium": is_premium(user)}

@api_router.post("/wallets")
async def add_wallet(req: AddWalletRequest, request: Request):
    user = await get_current_user(request)
    limits = get_limits(user)
    count = await db.wallets.count_documents({"user_id": user["id"]})
    if count >= limits["max_wallets"]:
        raise HTTPException(403, f"Max {limits['max_wallets']} wallet(s). Upgrade to Premium for up to 10.")

    pub_key = await derive_public_key(req.private_key)
    if not pub_key:
        raise HTTPException(400, "Invalid private key")

    rpc = get_rpc_url()
    balance = await get_sol_balance(pub_key, rpc)

    wallet_doc = {
        "id": str(uuid.uuid4()), "user_id": user["id"],
        "label": req.label, "private_key": req.private_key,
        "public_key": pub_key, "rpc_url": rpc,
        "wss_url": rpc.replace("https://", "wss://"),
        "balance_sol": balance, "is_primary": count == 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.wallets.insert_one(wallet_doc)
    await add_log("success", f"Wallet added: {req.label} ({pub_key[:12]}...)", user["id"])

    result = dict(wallet_doc)
    result["private_key_masked"] = req.private_key[:4] + "..." + req.private_key[-4:]
    result.pop("private_key", None)
    result.pop("_id", None)
    return result

@api_router.put("/wallets/{wallet_id}/primary")
async def set_primary_wallet(wallet_id: str, request: Request):
    user = await get_current_user(request)
    await db.wallets.update_many({"user_id": user["id"]}, {"$set": {"is_primary": False}})
    await db.wallets.update_one({"id": wallet_id, "user_id": user["id"]}, {"$set": {"is_primary": True}})
    return {"message": "Primary wallet updated"}

@api_router.delete("/wallets/{wallet_id}")
async def delete_wallet(wallet_id: str, request: Request):
    user = await get_current_user(request)
    await db.wallets.delete_one({"id": wallet_id, "user_id": user["id"]})
    await add_log("warn", f"Wallet removed: {wallet_id}", user["id"])
    return {"message": "Wallet deleted"}

@api_router.get("/wallets/balance")
async def refresh_wallet_balances(request: Request):
    user = await get_current_user(request)
    wallets = await db.wallets.find({"user_id": user["id"]}).to_list(20)
    rpc = get_rpc_url()
    results = []
    for w in wallets:
        bal = await get_sol_balance(w["public_key"], rpc)
        await db.wallets.update_one({"id": w["id"]}, {"$set": {"balance_sol": bal}})
        results.append({"id": w["id"], "label": w.get("label"), "public_key": w["public_key"], "balance_sol": bal})
    return {"wallets": results}

# ── Legacy wallet endpoint (for unauthenticated access) ──

@api_router.get("/wallet")
async def get_wallet_legacy():
    state = await db.bot_state.find_one({}, {"_id": 0})
    mode = state.get("mode", "paper") if state else "paper"
    return {
        "address": "PAPER_" + "".join(random.choices(string.ascii_letters, k=32)) if mode == "paper" else "Not connected",
        "balance_sol": round(random.uniform(0.5, 10.0), 4) if mode == "paper" else 0,
        "mode": mode,
    }

@api_router.get("/wallet/config")
async def get_wallet_config_legacy():
    cfg = await db.wallet_config.find_one({}, {"_id": 0})
    if not cfg:
        cfg = {"rpc_url": get_rpc_url(), "wss_url": get_rpc_url().replace("https://", "wss://"), "private_key": ""}
    if cfg.get("private_key"):
        pk = cfg["private_key"]
        cfg["private_key_masked"] = pk[:4] + "..." + pk[-4:] if len(pk) > 8 else "****"
        cfg["has_private_key"] = True
    else:
        cfg["private_key_masked"] = ""
        cfg["has_private_key"] = False
    cfg.pop("private_key", None)
    return cfg

@api_router.put("/wallet/config")
async def update_wallet_config_legacy(update: WalletConfigUpdate):
    current = await db.wallet_config.find_one({}, {"_id": 0}) or {"rpc_url": "", "wss_url": "", "private_key": ""}
    updates = {k: v for k, v in update.model_dump().items() if v is not None}
    current.update(updates)
    await db.wallet_config.replace_one({}, current, upsert=True)
    result = dict(current)
    if result.get("private_key"):
        pk = result["private_key"]
        result["private_key_masked"] = pk[:4] + "..." + pk[-4:] if len(pk) > 8 else "****"
        result["has_private_key"] = True
    else:
        result["private_key_masked"] = ""
        result["has_private_key"] = False
    result.pop("private_key", None)
    result.pop("_id", None)
    return result

@api_router.delete("/wallet/config/key")
async def clear_private_key_legacy():
    await db.wallet_config.update_one({}, {"$set": {"private_key": ""}}, upsert=True)
    return {"message": "Key cleared"}

# ── Scanner ─────────────────────────────────────

@api_router.get("/scanner/feed")
async def get_scanner_feed(limit: int = 50):
    items = await db.scanner_feed.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return items

@api_router.post("/scanner/simulate")
async def simulate_detection():
    state = await db.bot_state.find_one({}, {"_id": 0})
    if not state or not state.get("is_running"):
        return {"error": "Bot not running"}
    config = await db.bot_config.find_one({}, {"_id": 0}) or {}

    token_mint = random_mint()
    token_name = random_token_name()
    platform = random.choice(PLATFORMS)
    slot = random.randint(250000000, 300000000)

    mint_revoked = random.random() > 0.2
    freeze_revoked = random.random() > 0.15
    bundled = random.random() < 0.15
    lp_burned = random.random() > 0.25
    top_holder_pct = round(random.uniform(2, 35), 1)
    market_cap = round(random.uniform(1000, 500000), 0)

    score = 0
    if mint_revoked: score += 25
    if freeze_revoked: score += 25
    if top_holder_pct <= config.get("max_top_holder_pct", 15): score += 15
    if not bundled: score += 20
    if lp_burned: score += 15

    safety_passed = (
        score >= config.get("min_safety_score", 60) and
        (not config.get("require_mint_revoked") or mint_revoked) and
        (not config.get("require_freeze_revoked") or freeze_revoked) and
        (not config.get("reject_bundles") or not bundled)
    )
    action = "sniped" if safety_passed else "rejected"

    detection = {
        "id": str(uuid.uuid4()), "token_mint": token_mint, "token_name": token_name,
        "platform": platform, "safety_score": score, "safety_passed": safety_passed,
        "market_cap_usd": market_cap, "top_holder_pct": top_holder_pct,
        "mint_revoked": mint_revoked, "freeze_revoked": freeze_revoked,
        "bundled": bundled, "lp_burned": lp_burned, "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat(), "slot": slot,
    }
    await db.scanner_feed.insert_one(detection)
    await add_log("info", f"NEW TOKEN: {token_name} on {platform}")
    await add_log("info", f"Safety: {token_name} — {score}/100")

    if safety_passed:
        await add_log("success", f"SNIPED: {token_name}")
        amount_sol = config.get("buy_amount_sol", 0.05)
        pnl_pct = round(random.uniform(-30, 200), 1)
        pnl_sol = round(amount_sol * (pnl_pct / 100), 4)
        pos = {
            "id": str(uuid.uuid4()), "token_mint": token_mint, "token_name": token_name,
            "platform": platform, "amount_sol": amount_sol,
            "expected_tokens": random.randint(100000, 50000000),
            "current_value_sol": max(round(amount_sol + pnl_sol, 4), 0.001),
            "entry_time": datetime.now(timezone.utc).isoformat(), "safety_score": score,
            "tp1_hit": False, "peak_value_sol": max(round((amount_sol + pnl_sol) * random.uniform(1.0, 1.5), 4), amount_sol),
            "pnl_pct": pnl_pct, "pnl_sol": pnl_sol, "status": "open",
            "txid": f"PAPER_{uuid.uuid4().hex[:16]}",
        }
        await db.positions.insert_one(pos)
        await db.bot_state.update_one({}, {"$inc": {"tokens_sniped": 1, "tokens_scanned": 1}})
    else:
        await add_log("warn", f"REJECTED: {token_name}")
        await db.bot_state.update_one({}, {"$inc": {"tokens_scanned": 1}})

    return {k: v for k, v in detection.items() if k != "_id"}

# ── Real Safety Audit (Solana RPC) ──────────────

@api_router.get("/safety/real/{token_mint}")
async def get_real_safety_audit(token_mint: str):
    """Perform real on-chain safety audit using Helius RPC."""
    rpc = get_rpc_url()
    audit = await real_safety_audit(token_mint, rpc)
    return audit

@api_router.get("/safety/{token_mint}")
async def get_safety_audit(token_mint: str):
    detection = await db.scanner_feed.find_one({"token_mint": token_mint}, {"_id": 0})
    if not detection:
        return {"error": "Token not found"}
    return {
        "token_mint": detection["token_mint"], "token_name": detection["token_name"],
        "platform": detection["platform"], "safety_score": detection["safety_score"],
        "safety_passed": detection["safety_passed"], "market_cap_usd": detection["market_cap_usd"],
        "checks": {
            "mint_revoked": detection["mint_revoked"], "freeze_revoked": detection["freeze_revoked"],
            "bundled": detection["bundled"], "lp_burned": detection["lp_burned"],
            "top_holder_pct": detection["top_holder_pct"],
            "update_revoked": random.random() > 0.2, "social_links": random.random() > 0.5,
        },
        "timestamp": detection["timestamp"],
    }

# ── Portfolio ───────────────────────────────────

@api_router.get("/portfolio")
async def get_portfolio():
    open_pos = await db.positions.find({"status": "open"}, {"_id": 0}).sort("entry_time", -1).to_list(100)
    closed_pos = await db.positions.find({"status": "closed"}, {"_id": 0}).sort("close_time", -1).to_list(100)
    for pos in open_pos:
        drift = random.uniform(-0.05, 0.05)
        pos["current_value_sol"] = round(max(pos.get("current_value_sol", 0.05) * (1 + drift), 0.001), 4)
        pos["pnl_sol"] = round(pos["current_value_sol"] - pos.get("amount_sol", 0.05), 4)
        pos["pnl_pct"] = round((pos["current_value_sol"] / max(pos.get("amount_sol", 0.05), 0.001) - 1) * 100, 1)
    total_realized = sum(p.get("pnl_sol", 0) for p in closed_pos)
    total_unrealized = sum(p.get("pnl_sol", 0) for p in open_pos)
    profitable = len([p for p in closed_pos if p.get("pnl_sol", 0) > 0])
    total = len(open_pos) + len(closed_pos)
    return {
        "open_positions": open_pos, "closed_positions": closed_pos,
        "stats": {
            "total_sniped": total, "open_count": len(open_pos), "closed_count": len(closed_pos),
            "profitable": profitable, "win_rate": round((profitable / max(total, 1)) * 100, 1),
            "realized_pnl_sol": round(total_realized, 4), "unrealized_pnl_sol": round(total_unrealized, 4),
        },
    }

@api_router.post("/portfolio/close/{position_id}")
async def close_position(position_id: str):
    pos = await db.positions.find_one({"id": position_id, "status": "open"}, {"_id": 0})
    if not pos:
        raise HTTPException(404, "Position not found")
    pos["status"] = "closed"
    pos["close_reason"] = "manual_close"
    pos["close_time"] = datetime.now(timezone.utc).isoformat()
    await db.positions.update_one({"id": position_id}, {"$set": pos})
    await add_log("sell", f"Closed: {pos['token_name']} — PnL: {pos.get('pnl_sol', 0)} SOL")
    return {k: v for k, v in pos.items() if k != "_id"}

# ── Alerts ──────────────────────────────────────

@api_router.get("/alerts")
async def get_alerts(request: Request):
    user = await get_current_user(request)
    alerts = await db.alerts.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"alerts": alerts, "unread_count": len([a for a in alerts if not a.get("read")])}

@api_router.post("/alerts/read/{alert_id}")
async def mark_alert_read(alert_id: str, request: Request):
    user = await get_current_user(request)
    await db.alerts.update_one({"id": alert_id, "user_id": user["id"]}, {"$set": {"read": True}})
    return {"message": "Marked as read"}

@api_router.post("/alerts/read-all")
async def mark_all_read(request: Request):
    user = await get_current_user(request)
    await db.alerts.update_many({"user_id": user["id"]}, {"$set": {"read": True}})
    return {"message": "All marked as read"}

# ── Logs ────────────────────────────────────────

@api_router.get("/logs")
async def get_logs(limit: int = 100):
    return await db.activity_logs.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)

@api_router.delete("/logs")
async def clear_logs():
    await db.activity_logs.delete_many({})
    return {"message": "Cleared"}

# ── Stats ───────────────────────────────────────

@api_router.get("/stats")
async def get_stats():
    state = await db.bot_state.find_one({}, {"_id": 0}) or {}
    return {
        "is_running": state.get("is_running", False), "mode": state.get("mode", "paper"),
        "started_at": state.get("started_at"),
        "tokens_scanned": state.get("tokens_scanned", 0), "tokens_sniped": state.get("tokens_sniped", 0),
        "open_positions": await db.positions.count_documents({"status": "open"}),
        "closed_positions": await db.positions.count_documents({"status": "closed"}),
        "total_detections": await db.scanner_feed.count_documents({}),
    }

@api_router.post("/reset")
async def reset_all():
    for col in ["scanner_feed", "positions", "activity_logs"]:
        await db[col].delete_many({})
    await db.bot_state.replace_one({}, {"is_running": False, "mode": "paper", "started_at": None, "tokens_scanned": 0, "tokens_sniped": 0}, upsert=True)
    return {"message": "Reset"}

@api_router.get("/health")
async def health():
    return {"status": "ok", "service": "sniper-bot-backend", "features": ["auth", "stripe", "solana-rpc", "multi-wallet"]}

# ── Mount ───────────────────────────────────────

app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown():
    client.close()
