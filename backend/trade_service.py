"""
Real trade execution via Jupiter V6 API.
Signs and submits swap transactions on Solana.
"""
import asyncio
import base64
import logging
import os
from typing import Optional, Dict, Any

import httpx
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

logger = logging.getLogger(__name__)

JUPITER_QUOTE_URL = "https://api.jup.ag/swap/v1/quote"
JUPITER_SWAP_URL = "https://api.jup.ag/swap/v1/swap"
SOL_MINT = "So11111111111111111111111111111111111111112"


def get_keypair() -> Optional[Keypair]:
    pk = os.environ.get("TRADING_WALLET_PRIVKEY", "")
    if not pk:
        return None
    try:
        return Keypair.from_base58_string(pk)
    except Exception as e:
        logger.error(f"Invalid private key: {e}")
        return None


def get_wallet_pubkey() -> str:
    kp = get_keypair()
    if kp:
        return str(kp.pubkey())
    return os.environ.get("TRADING_WALLET_PUBKEY", "")


async def get_jupiter_quote(
    input_mint: str,
    output_mint: str,
    amount_lamports: int,
    slippage_bps: int = 1000,
) -> Optional[Dict[str, Any]]:
    """Get a swap quote from Jupiter."""
    try:
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount_lamports),
            "slippageBps": slippage_bps,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(JUPITER_QUOTE_URL, params=params)
            if resp.status_code != 200:
                logger.error(f"Jupiter quote error: {resp.status_code} {resp.text}")
                return None
            quote = resp.json()
            return quote
    except Exception as e:
        logger.error(f"Jupiter quote error: {e}")
        return None


async def execute_swap(
    input_mint: str,
    output_mint: str,
    amount_lamports: int,
    slippage_bps: int = 1000,
    priority_fee_lamports: int = 10000,
) -> Dict[str, Any]:
    """Execute a swap via Jupiter: get quote, build tx, sign, submit."""
    kp = get_keypair()
    if not kp:
        return {"success": False, "error": "No private key configured"}

    wallet = str(kp.pubkey())
    rpc_url = os.environ.get("HELIUS_RPC_URL", "")

    # Step 1: Get quote
    quote = await get_jupiter_quote(input_mint, output_mint, amount_lamports, slippage_bps)
    if not quote:
        return {"success": False, "error": "Failed to get Jupiter quote"}

    out_amount = int(quote.get("outAmount", 0))
    price_impact = quote.get("priceImpactPct", "0")

    # Step 2: Get swap transaction
    try:
        swap_body = {
            "quoteResponse": quote,
            "userPublicKey": wallet,
            "wrapAndUnwrapSol": True,
            "dynamicComputeUnitLimit": True,
            "dynamicSlippage": True,
            "prioritizationFeeLamports": {
                "priorityLevelWithMaxLamports": {
                    "maxLamports": priority_fee_lamports,
                    "priorityLevel": "veryHigh",
                }
            },
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(JUPITER_SWAP_URL, json=swap_body)
            if resp.status_code != 200:
                logger.error(f"Jupiter swap error: {resp.status_code} {resp.text}")
                return {"success": False, "error": f"Jupiter swap build failed: {resp.text[:200]}"}
            swap_data = resp.json()
    except Exception as e:
        logger.error(f"Jupiter swap request error: {e}")
        return {"success": False, "error": str(e)}

    swap_tx_b64 = swap_data.get("swapTransaction")
    if not swap_tx_b64:
        return {"success": False, "error": "No swap transaction returned"}

    # Step 3: Deserialize, sign, and submit
    try:
        tx_bytes = base64.b64decode(swap_tx_b64)
        tx = VersionedTransaction.from_bytes(tx_bytes)

        # Sign the transaction
        signed_tx = VersionedTransaction(tx.message, [kp])
        signed_bytes = bytes(signed_tx)
        signed_b64 = base64.b64encode(signed_bytes).decode("utf-8")

        # Submit via RPC
        send_payload = {
            "jsonrpc": "2.0", "id": 1,
            "method": "sendTransaction",
            "params": [
                signed_b64,
                {"encoding": "base64", "skipPreflight": True, "maxRetries": 3}
            ],
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(rpc_url, json=send_payload)
            result = resp.json()

        if "error" in result:
            err = result["error"]
            logger.error(f"Send tx error: {err}")
            return {"success": False, "error": f"Transaction failed: {err.get('message', str(err))[:200]}"}

        txid = result.get("result", "")
        logger.info(f"Swap submitted: {txid}")

        return {
            "success": True,
            "txid": txid,
            "input_mint": input_mint,
            "output_mint": output_mint,
            "amount_lamports": amount_lamports,
            "out_amount": out_amount,
            "price_impact": price_impact,
            "wallet": wallet,
        }

    except Exception as e:
        logger.error(f"Sign/submit error: {e}")
        return {"success": False, "error": str(e)}


async def buy_token(
    token_mint: str,
    amount_sol: float,
    slippage_bps: int = 1000,
    priority_fee: int = 10000,
) -> Dict[str, Any]:
    """Buy a token with SOL via Jupiter."""
    amount_lamports = int(amount_sol * 1_000_000_000)
    return await execute_swap(
        input_mint=SOL_MINT,
        output_mint=token_mint,
        amount_lamports=amount_lamports,
        slippage_bps=slippage_bps,
        priority_fee_lamports=priority_fee,
    )


async def sell_token(
    token_mint: str,
    amount_tokens: int,
    slippage_bps: int = 1000,
    priority_fee: int = 10000,
) -> Dict[str, Any]:
    """Sell a token for SOL via Jupiter."""
    return await execute_swap(
        input_mint=token_mint,
        output_mint=SOL_MINT,
        amount_lamports=amount_tokens,
        slippage_bps=slippage_bps,
        priority_fee_lamports=priority_fee,
    )


async def get_token_price_in_sol(token_mint: str) -> Optional[float]:
    """Get token price in SOL using Jupiter quote for 1 token."""
    try:
        # Get quote for small amount to check price
        quote = await get_jupiter_quote(token_mint, SOL_MINT, 1_000_000, 5000)
        if quote:
            out = int(quote.get("outAmount", 0))
            return out / 1_000_000_000
        return None
    except:
        return None
