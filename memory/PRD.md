# Solana Sniper Bot - Mobile App

## Overview
Full-featured Solana meme coin sniper bot mobile app with real blockchain integration, dual payment system (SOL + Stripe), referral program, premium tiers, and admin payment wallet management.

## Admin
- Email: Superbiggzz1411@gmail.com
- Password: Biggzz1411!
- Auto-premium, manages payment wallets

## Payment System
### SOL Payments (Primary)
- Direct transfer to admin's active payment wallet
- Dynamic wallet — admin can add/switch/remove wallets from Config screen
- Default: 8YjBBpAg8W3d8Juzrp7Xicga8wLe6sFwPphtswwJxgx9
- On-chain verification via Helius RPC

### Stripe (Live)
- Live key connected (sk_live_...)
- Stripe Checkout flow with redirect
- Monthly $29 / Quarterly $69

### Pricing
| Plan | SOL | USD | Duration | Savings |
|------|-----|-----|----------|---------|
| Monthly | 0.2 SOL | $29 | 30 days | — |
| Quarterly | 0.5 SOL | $69 | 90 days | 17% |

## Referral Program
- Referrer: +7 days free premium per referral
- Referee: +3 days free premium on signup
- Unique codes: SNIPE-XXXXXX format
- Stacks with existing subscription time
- Stats tracking (total referrals, days earned)

## Features
- JWT Auth with bcrypt + brute force protection + guest mode
- Real Solana RPC via Helius (safety audits, wallet balance)
- Admin payment wallet management (add/switch/delete)
- Multi-wallet support (10 for premium, 1 for free)
- 6 tabs: HQ, Scanner, Portfolio, Premium, Config, Logs
- Dark alien theme (black #030206, purple #9D4CDD, green #39FF14)

## Tech Stack
- Frontend: Expo SDK 54, React Native, expo-router, expo-clipboard
- Backend: FastAPI, Motor, bcrypt, PyJWT, httpx, solders
- Database: MongoDB
- Payments: Stripe (live) + SOL direct transfer
- Blockchain: Helius RPC (Solana mainnet)
