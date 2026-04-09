"""
Real-time Solana token scanner using Helius WebSocket.
Monitors Pump.fun, Raydium, and PumpSwap for new token launches.
"""
import asyncio
import json
import logging
import os
import time
from typing import Optional, Callable, Dict, Any
import websockets
import httpx

logger = logging.getLogger(__name__)

# Program IDs for DEX platforms
PUMP_FUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
RAYDIUM_AMM_PROGRAM = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
RAYDIUM_CPMM_PROGRAM = "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C"
PUMPSWAP_PROGRAM = "PSwapMdSai8tjrEXcxFeQth87xC4rRsa4VA5mhGhXkP"

# Known Solana token programs
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"

# SOL mint for wrapping
SOL_MINT = "So11111111111111111111111111111111111111112"

class TokenScanner:
    def __init__(self, rpc_url: str, wss_url: str, on_token_detected: Optional[Callable] = None):
        self.rpc_url = rpc_url
        self.wss_url = wss_url
        self.on_token_detected = on_token_detected
        self.running = False
        self._task = None
        self._seen_tokens = set()
        self._last_poll_time = 0
        self._warmed_up = False

    async def start(self):
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._scan_loop())
        logger.info("Token scanner started")

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Token scanner stopped")

    async def _scan_loop(self):
        """Main scanning loop - polls Helius for new token activity."""
        while self.running:
            try:
                await self._poll_new_tokens()
                # Scan interval based on config
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scanner error: {e}")
                await asyncio.sleep(10)

    async def _poll_new_tokens(self):
        """Poll Helius enhanced API for recent token-related transactions."""
        try:
            # Use Helius enhanced transactions API for new tokens
            api_key = self.rpc_url.split("api-key=")[-1] if "api-key=" in self.rpc_url else ""
            
            # Check Pump.fun for new token creates
            await self._check_program_activity(PUMP_FUN_PROGRAM, "pump.fun", api_key)
            await asyncio.sleep(1)
            # Check Raydium for new pools
            await self._check_program_activity(RAYDIUM_AMM_PROGRAM, "raydium", api_key)
            await asyncio.sleep(1)
            # Check PumpSwap
            await self._check_program_activity(PUMPSWAP_PROGRAM, "pumpswap", api_key)
            
            # After first poll cycle, mark as warmed up
            if not self._warmed_up:
                self._warmed_up = True
                logger.info("Scanner warmed up — now monitoring for NEW tokens only")
            
        except Exception as e:
            logger.error(f"Poll error: {e}")

    async def _check_program_activity(self, program_id: str, platform: str, api_key: str):
        """Check for recent transactions on a program and extract new token mints."""
        try:
            # Use getSignaturesForAddress to find recent transactions
            payload = {
                "jsonrpc": "2.0", "id": 1,
                "method": "getSignaturesForAddress",
                "params": [program_id, {"limit": 5}],
            }
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.post(self.rpc_url, json=payload)
                if resp.status_code != 200:
                    return
                data = resp.json()
                sigs = data.get("result", [])

            for sig_info in sigs:
                if sig_info.get("err"):
                    continue
                sig = sig_info.get("signature", "")
                if sig in self._seen_tokens:
                    continue
                self._seen_tokens.add(sig)
                # Keep set manageable
                if len(self._seen_tokens) > 500:
                    self._seen_tokens = set(list(self._seen_tokens)[-250:])

                # On first poll, just mark signatures as seen (warm-up)
                if not self._warmed_up:
                    continue

                # Get transaction details to extract token mint
                await self._process_transaction(sig, platform)
                await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Check {platform} error: {e}")

    async def _process_transaction(self, signature: str, platform: str):
        """Process a transaction to extract new token mint info."""
        try:
            payload = {
                "jsonrpc": "2.0", "id": 1,
                "method": "getTransaction",
                "params": [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
            }
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.post(self.rpc_url, json=payload)
                if resp.status_code != 200:
                    return
                data = resp.json()
                tx = data.get("result")
                if not tx:
                    return

            # Extract token mints from transaction
            token_mints = set()
            meta = tx.get("meta", {})
            
            # Check post token balances for new mints
            post_balances = meta.get("postTokenBalances", [])
            pre_balances = meta.get("preTokenBalances", [])
            
            post_mints = {b.get("mint") for b in post_balances if b.get("mint")}
            pre_mints = {b.get("mint") for b in pre_balances if b.get("mint")}
            
            # New mints that appear in post but not pre (new token interaction)
            new_mints = post_mints - pre_mints
            
            # Also check inner instructions for token creation
            if not new_mints:
                # Check all mints involved
                for b in post_balances:
                    mint = b.get("mint", "")
                    if mint and mint != SOL_MINT:
                        token_mints.add(mint)
            else:
                token_mints = new_mints

            # Filter out SOL
            token_mints.discard(SOL_MINT)
            
            for mint in list(token_mints)[:1]:  # Process 1 per tx
                if mint in self._seen_tokens:
                    continue
                self._seen_tokens.add(mint)
                
                slot = tx.get("slot", 0)
                block_time = tx.get("blockTime", int(time.time()))
                
                if self.on_token_detected:
                    await self.on_token_detected({
                        "token_mint": mint,
                        "platform": platform,
                        "signature": signature,
                        "slot": slot,
                        "block_time": block_time,
                    })

        except Exception as e:
            logger.error(f"Process tx error: {e}")


class WebSocketScanner:
    """Real-time scanner using Helius WebSocket log subscriptions."""
    
    def __init__(self, wss_url: str, on_token_detected: Optional[Callable] = None):
        self.wss_url = wss_url
        self.on_token_detected = on_token_detected
        self.running = False
        self._task = None
        self._seen = set()

    async def start(self):
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._ws_loop())
        logger.info("WebSocket scanner started")

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _ws_loop(self):
        while self.running:
            try:
                async with websockets.connect(self.wss_url, ping_interval=30, ping_timeout=10) as ws:
                    logger.info("WebSocket connected to Helius")
                    
                    # Subscribe to Pump.fun logs
                    await ws.send(json.dumps({
                        "jsonrpc": "2.0", "id": 1,
                        "method": "logsSubscribe",
                        "params": [
                            {"mentions": [PUMP_FUN_PROGRAM]},
                            {"commitment": "confirmed"}
                        ],
                    }))
                    
                    # Subscribe to Raydium logs
                    await ws.send(json.dumps({
                        "jsonrpc": "2.0", "id": 2,
                        "method": "logsSubscribe",
                        "params": [
                            {"mentions": [RAYDIUM_AMM_PROGRAM]},
                            {"commitment": "confirmed"}
                        ],
                    }))

                    while self.running:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=60)
                            data = json.loads(msg)
                            await self._handle_ws_message(data)
                        except asyncio.TimeoutError:
                            continue
                        except websockets.ConnectionClosed:
                            logger.warning("WebSocket connection closed, reconnecting...")
                            break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(5)

    async def _handle_ws_message(self, data: dict):
        """Handle incoming WebSocket log messages."""
        try:
            if "method" not in data or data["method"] != "logsNotification":
                return
            
            params = data.get("params", {})
            result = params.get("result", {})
            value = result.get("value", {})
            
            signature = value.get("signature", "")
            logs = value.get("logs", [])
            
            if signature in self._seen:
                return
            self._seen.add(signature)
            if len(self._seen) > 1000:
                self._seen = set(list(self._seen)[-500:])

            # Determine platform from logs
            platform = "unknown"
            for log in logs:
                if PUMP_FUN_PROGRAM in log:
                    platform = "pump.fun"
                    break
                elif RAYDIUM_AMM_PROGRAM in log:
                    platform = "raydium"
                    break
                elif PUMPSWAP_PROGRAM in log:
                    platform = "pumpswap"
                    break

            if platform == "unknown":
                return

            # Look for token-related log entries
            has_token_activity = any(
                "InitializeMint" in log or "MintTo" in log or "Transfer" in log
                for log in logs
            )

            if has_token_activity and self.on_token_detected:
                await self.on_token_detected({
                    "signature": signature,
                    "platform": platform,
                    "logs": logs,
                    "slot": result.get("context", {}).get("slot", 0),
                    "block_time": int(time.time()),
                })

        except Exception as e:
            logger.error(f"WS message error: {e}")
