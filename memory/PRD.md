# PRD — Arabic Multiplayer Mafia Platform

## Problem Statement
Build a fully functional Arabic RTL multiplayer game platform. MVP focuses on Mafia — Host creates a room, shares room code, players (with real accounts) join, real-time lobby, server-authoritative game state machine (Night → Discussion → Voting → Game Over), private role assignment, and win condition detection.

## Architecture
- **Backend**: FastAPI + MongoDB (Motor async) + WebSockets. JWT auth (bcrypt). Modular monolith: `server.py`, `auth.py`, `models.py`, `ws_manager.py`, `mafia_engine.py`.
- **Frontend**: React JS + React Router + TailwindCSS + Shadcn UI + Sonner + Framer. Arabic RTL, Dark Gaming Theme (Changa + IBM Plex Sans Arabic fonts, blood-red primary).
- **Real-time**: FastAPI native WebSocket at `/api/ws?token=<jwt>` with `SUBSCRIBE_ROOM` event and per-room broadcast.

## User Personas
- **Host**: Creates room, configures Mafia (players, roles, timers), controls start.
- **Player**: Joins by room code with own account, plays through phases.

## Core Requirements (Static)
1. Auth: Register + Login with email/username uniqueness, bcrypt hashing, JWT.
2. Room creation with configurable Mafia settings (server-validated).
3. Random unique room code (A-Z2-9, ambiguous chars removed).
4. Join by room code + real-time lobby with online/offline indicators.
5. Host-only Start Game (server-side authorization via hostId).
6. Server-authoritative Mafia state machine (LOBBY → ROLE_ASSIGNMENT → NIGHT → NIGHT_RESULT → DISCUSSION → VOTING → VOTE_RESULT → CHECK_WIN → GAME_OVER).
7. Private role reveal (per-user socket send, never leak in public payload).
8. Roles: MAFIA, CITIZEN, DOCTOR, DETECTIVE with role-specific night actions.
9. Server-side timers (phase_ends_at persisted; client displays countdown).
10. Win condition: Citizens win when 0 mafia alive; Mafia wins when mafia >= non-mafia.

## Implemented (Feb 21, 2026)
- Full auth flow (register/login/me) with JWT + bcrypt. JWT_SECRET loaded from .env (no fallback default).
- Landing/Login/Register/Dashboard/CreateGame/JoinRoom/Lobby/Game/Profile pages.
- Room CRUD with unique 6-char codes.
- Real-time WebSocket connection manager with per-user + per-room + per-mafia sub-channel broadcasts.
- MafiaEngine phases: LOBBY → ROLE_ASSIGNMENT → **MAFIA_DISCUSSION** → **NIGHT_ACTIONS** → NIGHT_RESULT → DISCUSSION → VOTING → VOTE_RESULT → GAME_OVER.
- Mafia private chat + target voting during MAFIA_DISCUSSION and NIGHT_ACTIONS (server-authoritative permission checks).
- Connected Accounts: manual linking for Twitch/YouTube/TikTok/Kick — extensible for OAuth later.
- MongoDB indexes on all unique constraints. Membership check on /rooms/{id}/state.
- **Backend tests: 43/43 passing** (full pytest suite in /app/backend/tests/).

## Prioritized Backlog (P0/P1/P2)
- **P1**: Reconnection UX polish (rejoin during active game with role intact — currently works via `/state` refetch).
- **P1**: Rate limiting on auth + game actions.
- **P2**: Player stats, leaderboard, game history.
- **P2**: Additional games (Quiz, Bingo, Roulette, Word Rush, Memory Match).
- **P2**: More roles (Jester, Bodyguard, Sniper, Witch).
- **P2**: Host Pause/Resume, spectator chat, replay.
