# Solana Sniper Bot - Mobile App

## Overview
Mobile app conversion of a Solana meme coin sniper bot CLI tool. Built with Expo (React Native) frontend and FastAPI backend with MongoDB. Features an alien-themed dark UI with black & purple design.

## Current Status
- **Blockchain Integration**: SIMULATED (mock data) — wallet config screen ready for Helius RPC integration later
- **Trading**: Paper mode with simulated token detections and portfolio tracking

## Features
### Dashboard (HQ)
- Bot start/stop reactor button with glow animation
- Paper/Live mode toggle
- Stats grid: Scanned, Sniped, Open, Closed positions
- Wallet balance display
- Status indicators (scanner, trading mode, platforms)

### Scanner Feed
- Live token detection feed (simulated)
- Platform badges (pump.fun, raydium, pumpswap)
- Safety score display with pass/reject status
- Simulate detection button
- Token safety audit detail view with 7-point checklist

### Portfolio & P&L
- Realized/unrealized P&L display
- Open/Closed position tabs
- Position cards with close button
- Win rate and stats

### Bot Configuration
- **Wallet & RPC**: Private key input (masked), Helius RPC URL, WebSocket URL
- Strategy presets: Aggressive, Balanced, Safe
- Buy settings: Amount, slippage, priority fee, Jito tip, max positions
- Sell settings: Auto-sell, TP1/TP2, stop loss, trailing stop, max hold time
- Safety filters: Mint/freeze/update revoked, LP burned, bundle rejection, holder limits
- Platform toggles: Pump.fun, Raydium, PumpSwap

### Activity Logs
- Terminal-style log viewer with color-coded entries
- Auto-scroll to latest entries
- Clear logs button

## Tech Stack
- **Frontend**: Expo SDK 54, React Native, expo-router, lucide-react-native
- **Backend**: FastAPI, Motor (async MongoDB), Pydantic
- **Database**: MongoDB
- **Design**: Alien Tech Void theme (#030206 bg, #9D4CDD primary, #39FF14 success)

## API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/health | Health check |
| GET/PUT | /api/bot/state | Bot running state |
| GET/PUT | /api/bot/config | Full bot configuration |
| GET | /api/scanner/feed | Token detections |
| POST | /api/scanner/simulate | Generate simulated detection |
| GET | /api/portfolio | Positions & P&L stats |
| POST | /api/portfolio/close/:id | Close a position |
| GET | /api/safety/:mint | Safety audit for token |
| GET/PUT | /api/wallet/config | Wallet & RPC configuration |
| DELETE | /api/wallet/config/key | Clear private key |
| GET | /api/wallet | Wallet info |
| GET | /api/stats | Dashboard stats |
| GET/DELETE | /api/logs | Activity logs |
| POST | /api/reset | Reset all data |

## Next Steps
- Wire up real Solana RPC via Helius for live blockchain data
- Real token scanning from on-chain program logs
- Real safety audits (mint authority, freeze authority checks)
- Jupiter API swap integration for live trading
