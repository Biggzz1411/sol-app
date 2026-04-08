# Solana Sniper Bot - Mobile App

## Overview
Full-featured Solana meme coin sniper bot mobile app with real blockchain integration, SOL payments direct to owner wallet, premium subscription tiers, multi-wallet support, and admin payment wallet management.

## Admin Credentials
- Email: Superbiggzz1411@gmail.com
- Password: Biggzz1411!
- Role: admin (auto-premium, payment wallet management)

## Payment System
- **SOL Payments (Primary)**: Direct transfer to owner's active payment wallet
- **Stripe (Coming Soon)**: Placeholder ready, user can plug in their Stripe key later
- **Pricing**: Monthly 0.2 SOL (~$29) | Quarterly 0.5 SOL (~$69, 17% savings)
- **On-chain verification**: Helius RPC verifies incoming SOL transfers by matching unique amounts

## Admin Payment Wallet Management
- Admin can add multiple Solana wallets to receive payments
- Only one wallet active at a time (receives payments)
- Can switch active wallet, delete inactive wallets
- Default wallet: 8YjBBpAg8W3d8Juzrp7Xicga8wLe6sFwPphtswwJxgx9

## Features

### Auth System (JWT)
- Email/password registration & login with bcrypt + brute force protection
- Guest mode for unauthenticated browsing
- Admin auto-premium on startup

### Real Solana RPC (Helius)
- Live on-chain safety audits (mint/freeze authority, holder concentration)
- Real wallet balance checking
- Token supply and decimals from chain

### Free vs Premium Tiers
| Feature | Free | Premium |
|---------|------|---------|
| Wallets | 1 | 10 |
| Scan Interval | 30s | 5s |
| Trading Mode | Paper Only | Paper + Live |
| Push Alerts | No | Yes |
| Max Positions | 2 | 20 |

### Multi-Wallet (Premium)
- Up to 10 Solana wallets per user
- Real SOL balance fetching per wallet
- Private key validation via solders

### Screens
1. **Auth** — Login/Register with alien theme + guest skip
2. **Dashboard (HQ)** — Bot control, stats, wallet balance, PRO badge
3. **Scanner** — Token detection feed with safety audit drilldown
4. **Portfolio** — Open/closed positions, P&L tracking
5. **Premium** — Plan cards, SOL payment flow with copy-to-clipboard, verify button
6. **Config** — Admin wallet management, bot settings, safety filters, platform toggles
7. **Logs** — Terminal-style activity log

## Tech Stack
- Frontend: Expo SDK 54, React Native, expo-router, lucide-react-native, expo-clipboard
- Backend: FastAPI, Motor, bcrypt, PyJWT, httpx, solders
- Database: MongoDB
- Blockchain: Helius RPC (Solana mainnet)
- Payments: SOL direct transfer + Stripe (placeholder)
