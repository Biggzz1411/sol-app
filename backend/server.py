from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import random
import string
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'sniper_bot')]

app = FastAPI()
api_router = APIRouter(prefix="/api")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# ── Models ──────────────────────────────────────

class BotState(BaseModel):
    is_running: bool = False
    mode: str = "paper"  # "paper" or "live"
    started_at: Optional[str] = None
    tokens_scanned: int = 0
    tokens_sniped: int = 0

class BotConfig(BaseModel):
    strategy: str = "balanced"
    buy_amount_sol: float = 0.05
    slippage_bps: int = 1000
    priority_fee_lamports: int = 10000
    jito_tip_sol: float = 0.01
    max_open_positions: int = 5
    use_jito: bool = True
    auto_sell: bool = True
    take_profit_pct1: int = 100
    take_profit_pct2: int = 300
    stop_loss_pct: int = -30
    trailing_stop_pct: int = 15
    max_hold_seconds: int = 3600
    price_check_interval: int = 10000
    require_mint_revoked: bool = True
    require_freeze_revoked: bool = True
    require_update_revoked: bool = True
    require_lp_burned: bool = True
    max_top_holder_pct: int = 15
    reject_bundles: bool = True
    min_market_cap_usd: int = 5000
    max_token_age_minutes: int = 30
    min_safety_score: int = 60
    platform_pumpfun: bool = True
    platform_raydium: bool = True
    platform_pumpswap: bool = True
    rpc_url: str = "https://api.mainnet-beta.solana.com"
    wss_url: str = "wss://api.mainnet-beta.solana.com"

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
    rpc_url: Optional[str] = None
    wss_url: Optional[str] = None

class BotStateUpdate(BaseModel):
    is_running: Optional[bool] = None
    mode: Optional[str] = None

class TokenDetection(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    token_mint: str
    token_name: str
    platform: str
    safety_score: int
    safety_passed: bool
    market_cap_usd: float
    top_holder_pct: float
    mint_revoked: bool
    freeze_revoked: bool
    bundled: bool
    lp_burned: bool
    action: str  # "sniped", "rejected", "watching"
    timestamp: str
    slot: int

class Position(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    token_mint: str
    token_name: str
    platform: str
    amount_sol: float
    expected_tokens: int
    current_value_sol: float
    entry_time: str
    safety_score: int
    tp1_hit: bool = False
    peak_value_sol: float
    pnl_pct: float
    pnl_sol: float
    status: str = "open"  # "open" or "closed"
    close_reason: Optional[str] = None
    close_time: Optional[str] = None
    txid: str

class LogEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    level: str
    message: str
    timestamp: str

# ── Helpers ─────────────────────────────────────

def random_mint():
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=44))

def random_token_name():
    prefixes = ["ALIEN", "VOID", "MOON", "PEPE", "DOGE", "BONK", "WIF", "MYRO", "POPCAT", "MEW", "BOME", "SLERF", "TREMP", "JITO", "PYTH", "TNSR", "KMNO", "ZEUS", "DRIFT", "ZETA"]
    suffixes = ["INU", "COIN", "TOKEN", "SOL", "SWAP", "FI", "DAO", "X", "AI", "BOT", "MOON", "PUMP", "LAUNCH"]
    return random.choice(prefixes) + random.choice(suffixes)

PLATFORMS = ["pump.fun", "raydium", "pumpswap"]

LOG_MESSAGES = {
    "scan": [
        "Scanning for new token launches...",
        "WebSocket connection active — monitoring {platform}",
        "Block {slot}: checking for new pools",
        "Heartbeat — scanner alive, {count} tokens seen",
    ],
    "detect": [
        "NEW TOKEN: {mint} on {platform}",
        "Token detected: {name} — running safety audit",
        "Potential snipe target: {name} (slot {slot})",
    ],
    "safety": [
        "Safety audit: {name} — Score {score}/100",
        "Mint authority: {'REVOKED' if revoked else 'ACTIVE'}",
        "Freeze authority: {'REVOKED' if revoked else 'ACTIVE'}",
        "Top holder: {pct}% — {'PASS' if pct < 15 else 'FAIL'}",
        "Bundle check: {'CLEAN' if not bundled else 'BUNDLED — REJECT'}",
    ],
    "trade": [
        "BUY executed: {name} — {sol} SOL — TX: {txid}",
        "Position opened: {name} — Safety: {score}/100",
        "Quote: {tokens} tokens, impact: {impact}%",
    ],
    "sell": [
        "TP1 hit: {name} — selling 50%",
        "Stop loss triggered: {name} at {pnl}%",
        "Position closed: {name} — PnL: {pnl} SOL",
    ],
}

# ── Seed Default Config ─────────────────────────

async def ensure_defaults():
    existing_state = await db.bot_state.find_one({}, {"_id": 0})
    if not existing_state:
        state = BotState().model_dump()
        await db.bot_state.insert_one(state)

    existing_config = await db.bot_config.find_one({}, {"_id": 0})
    if not existing_config:
        cfg = BotConfig().model_dump()
        await db.bot_config.insert_one(cfg)

@app.on_event("startup")
async def startup():
    await ensure_defaults()
    logger.info("Sniper bot backend started")

# ── Bot State ───────────────────────────────────

@api_router.get("/bot/state")
async def get_bot_state():
    state = await db.bot_state.find_one({}, {"_id": 0})
    if not state:
        return BotState().model_dump()
    return state

@api_router.put("/bot/state")
async def update_bot_state(update: BotStateUpdate):
    current = await db.bot_state.find_one({}, {"_id": 0})
    if not current:
        current = BotState().model_dump()

    updates = {k: v for k, v in update.model_dump().items() if v is not None}

    if "is_running" in updates:
        if updates["is_running"] and not current.get("is_running"):
            updates["started_at"] = datetime.now(timezone.utc).isoformat()
            # Add startup log
            await add_log("info", f"Bot started in {current.get('mode', 'paper')} mode")
            await add_log("info", "Connecting to RPC endpoint...")
            await add_log("success", "Scanner active — monitoring platforms")
        elif not updates["is_running"] and current.get("is_running"):
            updates["started_at"] = None
            await add_log("warn", "Bot stopped by user")

    if "mode" in updates:
        await add_log("info", f"Trading mode changed to: {updates['mode']}")

    current.update(updates)
    await db.bot_state.replace_one({}, current, upsert=True)
    return {k: v for k, v in current.items() if k != "_id"}

# ── Bot Config ──────────────────────────────────

@api_router.get("/bot/config")
async def get_bot_config():
    cfg = await db.bot_config.find_one({}, {"_id": 0})
    if not cfg:
        return BotConfig().model_dump()
    return cfg

@api_router.put("/bot/config")
async def update_bot_config(update: BotConfigUpdate):
    current = await db.bot_config.find_one({}, {"_id": 0})
    if not current:
        current = BotConfig().model_dump()

    updates = {k: v for k, v in update.model_dump().items() if v is not None}
    current.update(updates)
    await db.bot_config.replace_one({}, current, upsert=True)
    await add_log("info", f"Config updated: {list(updates.keys())}")
    return {k: v for k, v in current.items() if k != "_id"}

# ── Scanner Feed ────────────────────────────────

@api_router.get("/scanner/feed")
async def get_scanner_feed(limit: int = 50):
    detections = await db.scanner_feed.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return detections

@api_router.post("/scanner/simulate")
async def simulate_detection():
    """Generate a simulated token detection"""
    state = await db.bot_state.find_one({}, {"_id": 0})
    if not state or not state.get("is_running"):
        return {"error": "Bot is not running"}

    config = await db.bot_config.find_one({}, {"_id": 0})
    if not config:
        config = BotConfig().model_dump()

    token_mint = random_mint()
    token_name = random_token_name()
    platform = random.choice(PLATFORMS)
    slot = random.randint(250000000, 300000000)

    # Generate safety check results
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

    detection = TokenDetection(
        token_mint=token_mint,
        token_name=token_name,
        platform=platform,
        safety_score=score,
        safety_passed=safety_passed,
        market_cap_usd=market_cap,
        top_holder_pct=top_holder_pct,
        mint_revoked=mint_revoked,
        freeze_revoked=freeze_revoked,
        bundled=bundled,
        lp_burned=lp_burned,
        action=action,
        timestamp=datetime.now(timezone.utc).isoformat(),
        slot=slot,
    ).model_dump()

    await db.scanner_feed.insert_one(detection)

    # Add logs
    await add_log("info", f"NEW TOKEN: {token_name} ({token_mint[:12]}...) on {platform}")
    await add_log("info", f"Safety audit: {token_name} — Score {score}/100")

    if safety_passed:
        await add_log("success", f"ALL CHECKS PASSED ({score}/100) — Executing buy...")
        # Create position
        amount_sol = config.get("buy_amount_sol", 0.05)
        expected_tokens = random.randint(100000, 50000000)
        pnl_pct = round(random.uniform(-30, 200), 1)
        pnl_sol = round(amount_sol * (pnl_pct / 100), 4)
        current_value = round(amount_sol + pnl_sol, 4)

        position = Position(
            token_mint=token_mint,
            token_name=token_name,
            platform=platform,
            amount_sol=amount_sol,
            expected_tokens=expected_tokens,
            current_value_sol=max(current_value, 0.001),
            entry_time=datetime.now(timezone.utc).isoformat(),
            safety_score=score,
            peak_value_sol=max(current_value * random.uniform(1.0, 1.5), amount_sol),
            pnl_pct=pnl_pct,
            pnl_sol=pnl_sol,
            txid=f"PAPER_{uuid.uuid4().hex[:16]}",
        ).model_dump()

        await db.positions.insert_one(position)
        await add_log("snipe", f"Position opened: {token_name} — {amount_sol} SOL — Safety: {score}/100")

        # Update state counters
        await db.bot_state.update_one({}, {"$inc": {"tokens_sniped": 1, "tokens_scanned": 1}})
    else:
        reasons = []
        if not mint_revoked: reasons.append("mint_not_revoked")
        if not freeze_revoked: reasons.append("freeze_not_revoked")
        if bundled: reasons.append("bundled_launch")
        if top_holder_pct > config.get("max_top_holder_pct", 15): reasons.append(f"top_holder_{top_holder_pct}%")
        await add_log("warn", f"REJECTED: {token_name} — {', '.join(reasons)}")
        await db.bot_state.update_one({}, {"$inc": {"tokens_scanned": 1}})

    result = {k: v for k, v in detection.items() if k != "_id"}
    return result

# ── Portfolio ───────────────────────────────────

@api_router.get("/portfolio")
async def get_portfolio():
    open_positions = await db.positions.find({"status": "open"}, {"_id": 0}).sort("entry_time", -1).to_list(100)
    closed_positions = await db.positions.find({"status": "closed"}, {"_id": 0}).sort("close_time", -1).to_list(100)

    # Simulate P&L fluctuation for open positions
    for pos in open_positions:
        drift = random.uniform(-0.05, 0.05)
        pos["current_value_sol"] = round(max(pos.get("current_value_sol", 0.05) * (1 + drift), 0.001), 4)
        pos["pnl_sol"] = round(pos["current_value_sol"] - pos.get("amount_sol", 0.05), 4)
        pos["pnl_pct"] = round((pos["current_value_sol"] / max(pos.get("amount_sol", 0.05), 0.001) - 1) * 100, 1)
        if pos["current_value_sol"] > pos.get("peak_value_sol", 0):
            pos["peak_value_sol"] = pos["current_value_sol"]

    total_realized = sum(p.get("pnl_sol", 0) for p in closed_positions)
    total_unrealized = sum(p.get("pnl_sol", 0) for p in open_positions)
    total_sniped = len(open_positions) + len(closed_positions)
    profitable = len([p for p in closed_positions if p.get("pnl_sol", 0) > 0])
    win_rate = round((profitable / max(total_sniped, 1)) * 100, 1)

    return {
        "open_positions": open_positions,
        "closed_positions": closed_positions,
        "stats": {
            "total_sniped": total_sniped,
            "open_count": len(open_positions),
            "closed_count": len(closed_positions),
            "profitable": profitable,
            "win_rate": win_rate,
            "realized_pnl_sol": round(total_realized, 4),
            "unrealized_pnl_sol": round(total_unrealized, 4),
        }
    }

@api_router.post("/portfolio/close/{position_id}")
async def close_position(position_id: str):
    pos = await db.positions.find_one({"id": position_id, "status": "open"}, {"_id": 0})
    if not pos:
        return {"error": "Position not found or already closed"}

    close_reason = "manual_close"
    pos["status"] = "closed"
    pos["close_reason"] = close_reason
    pos["close_time"] = datetime.now(timezone.utc).isoformat()

    await db.positions.update_one({"id": position_id}, {"$set": pos})
    await add_log("sell", f"Position closed: {pos['token_name']} — Reason: {close_reason} — PnL: {pos.get('pnl_sol', 0)} SOL")

    return {k: v for k, v in pos.items() if k != "_id"}

# ── Safety Audit ────────────────────────────────

@api_router.get("/safety/{token_mint}")
async def get_safety_audit(token_mint: str):
    detection = await db.scanner_feed.find_one({"token_mint": token_mint}, {"_id": 0})
    if not detection:
        return {"error": "Token not found"}

    return {
        "token_mint": detection["token_mint"],
        "token_name": detection["token_name"],
        "platform": detection["platform"],
        "safety_score": detection["safety_score"],
        "safety_passed": detection["safety_passed"],
        "market_cap_usd": detection["market_cap_usd"],
        "checks": {
            "mint_revoked": detection["mint_revoked"],
            "freeze_revoked": detection["freeze_revoked"],
            "bundled": detection["bundled"],
            "lp_burned": detection["lp_burned"],
            "top_holder_pct": detection["top_holder_pct"],
            "update_revoked": random.random() > 0.2,
            "social_links": random.random() > 0.5,
        },
        "timestamp": detection["timestamp"],
    }

# ── Activity Logs ───────────────────────────────

async def add_log(level: str, message: str):
    entry = LogEntry(
        level=level,
        message=message,
        timestamp=datetime.now(timezone.utc).isoformat(),
    ).model_dump()
    await db.activity_logs.insert_one(entry)

@api_router.get("/logs")
async def get_logs(limit: int = 100):
    logs = await db.activity_logs.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return logs

@api_router.delete("/logs")
async def clear_logs():
    await db.activity_logs.delete_many({})
    return {"message": "Logs cleared"}

# ── Wallet ──────────────────────────────────────

@api_router.get("/wallet")
async def get_wallet():
    state = await db.bot_state.find_one({}, {"_id": 0})
    mode = state.get("mode", "paper") if state else "paper"
    return {
        "address": "PAPER_" + "".join(random.choices(string.ascii_letters, k=32)) if mode == "paper" else "Not connected",
        "balance_sol": round(random.uniform(0.5, 10.0), 4) if mode == "paper" else 0,
        "mode": mode,
    }

# ── Stats ───────────────────────────────────────

@api_router.get("/stats")
async def get_stats():
    state = await db.bot_state.find_one({}, {"_id": 0})
    if not state:
        state = BotState().model_dump()

    open_count = await db.positions.count_documents({"status": "open"})
    closed_count = await db.positions.count_documents({"status": "closed"})
    total_detections = await db.scanner_feed.count_documents({})

    return {
        "is_running": state.get("is_running", False),
        "mode": state.get("mode", "paper"),
        "started_at": state.get("started_at"),
        "tokens_scanned": state.get("tokens_scanned", 0),
        "tokens_sniped": state.get("tokens_sniped", 0),
        "open_positions": open_count,
        "closed_positions": closed_count,
        "total_detections": total_detections,
    }

# ── Reset ───────────────────────────────────────

@api_router.post("/reset")
async def reset_all():
    await db.scanner_feed.delete_many({})
    await db.positions.delete_many({})
    await db.activity_logs.delete_many({})
    await db.bot_state.replace_one({}, BotState().model_dump(), upsert=True)
    await add_log("info", "All data reset")
    return {"message": "Reset complete"}

# ── Health ──────────────────────────────────────

@api_router.get("/health")
async def health():
    return {"status": "ok", "service": "sniper-bot-backend"}

# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
