# Solana Sniper Bot - Mobile App

## Overview
Full-featured Solana meme coin sniper bot mobile app with real blockchain integration, premium subscription tiers, and multi-wallet support. Built with Expo (React Native) + FastAPI + MongoDB.

## Features

### Auth System (JWT)
- Email/password registration & login
- Bcrypt password hashing, brute force protection
- Guest mode for unauthenticated browsing
- Admin account seeded on startup

### Real Solana RPC (Helius)
- **LIVE** on-chain safety audits via `/api/safety/real/{mint}`
- Real wallet balance checking
- Real mint/freeze authority verification
- Real top holder concentration analysis
- Token supply and decimals from chain

### Premium Subscription (Stripe)
- **Monthly**: $29/mo (30 days)
- **Quarterly**: $69 (90 days, 20% savings)
- Stripe Checkout integration with payment status polling
- Webhook support for payment confirmation

### Free vs Premium Tiers
| Feature | Free | Premium |
|---------|------|---------|
| Wallets | 1 | 10 |
| Scan Interval | 30s | 5s |
| Trading Mode | Paper Only | Paper + Live |
| Push Alerts | No | Yes |
| Max Positions | 2 | 20 |

### Multi-Wallet (Premium)
- Add up to 10 Solana wallets
- Private key validation via solders
- Real SOL balance fetching per wallet
- Set primary wallet for trading
- Keys masked in API responses

### Dashboard (HQ)
- Bot start/stop with glow animation
- Paper/Live mode toggle (live requires premium)
- Stats grid, wallet balance, status indicators
- User email, PRO badge, logout

### Scanner, Portfolio, Config, Logs
- All original features from MVP preserved
- Simulated token detections + real safety audits
- Full bot configuration with wallet/RPC settings
- Terminal-style activity log

## API Endpoints
| Endpoint | Description |
|----------|-------------|
| POST /api/auth/register | Create account |
| POST /api/auth/login | Login |
| GET /api/auth/me | Current user + premium status |
| GET /api/premium/plans | Subscription plans |
| POST /api/premium/checkout | Create Stripe session |
| GET /api/premium/status/:id | Poll payment |
| GET /api/safety/real/:mint | Real on-chain audit |
| GET/POST/DELETE /api/wallets | Multi-wallet CRUD |
| GET/PUT /api/bot/state | Bot control |
| GET/PUT /api/bot/config | Bot settings |
| GET /api/scanner/feed | Token detections |
| POST /api/scanner/simulate | Simulate detection |
| GET /api/portfolio | Positions & P&L |

## Tech Stack
- Frontend: Expo SDK 54, React Native, expo-router
- Backend: FastAPI, Motor, bcrypt, PyJWT, httpx, solders
- Database: MongoDB
- Payments: Stripe (emergentintegrations)
- Blockchain: Helius RPC (Solana mainnet)
