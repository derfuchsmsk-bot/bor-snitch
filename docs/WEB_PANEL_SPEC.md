# Web Admin Panel Specification

## Overview
An admin-only web dashboard for managing the BorSnitch bot, viewing global statistics, and monitoring chat activities.

## Architecture
- **Backend:** FastAPI (existing `src/main.py`)
- **Frontend:** Single Page Application (SPA) using React + Tailwind CSS, served from a `web/` directory or a separate static hosting.
- **Authentication:** JWT-based using the existing `JWT_SECRET` and `SECRET_TOKEN`.

## API Endpoints (Admin)

### Authentication
- `GET /api/admin/verify` - Check if the current token is valid.
- `POST /api/admin/login` - Exchange `SECRET_TOKEN` for a long-lived JWT.

### Statistics
- `GET /api/admin/stats/global` - Returns total chats, total users, total agreements.
- `GET /api/admin/chats` - List all active chats with basic info.
- `GET /api/admin/chats/{chat_id}` - Detailed info for a specific chat.
- `GET /api/admin/chats/{chat_id}/users` - Top users in a specific chat.

### Management
- `POST /api/admin/chats/{chat_id}/toggle` - Activate/Deactivate bot in a chat.
- `POST /api/admin/chats/{chat_id}/analyze` - Trigger manual daily analysis.
- `DELETE /api/admin/chats/{chat_id}/agreements/{agreement_id}` - Remove a specific agreement.

## Frontend Layout
1.  **Dashboard:** High-level metrics cards (Total Chats, Active Users, etc.).
2.  **Chat List:** Table of all chats where the bot is present.
3.  **Chat Detail View:**
    *   Leaderboard (Users & Ranks).
    *   Active Agreements.
    *   Lore/Facts for the chat.
4.  **Settings:** Basic bot configuration toggles.

## Implementation Plan

### Phase 1: Backend API
1.  Extend `UserRepository` and `AgreementRepository` with methods for global listing.
2.  Create `AdminService` to aggregate data.
3.  Implement FastAPI routers for `/api/admin/*`.

### Phase 2: Frontend Setup
1.  Initialize a Vite project in `web/`.
2.  Setup basic routing and API client.
3.  Implement login page.

### Phase 3: UI Components
1.  Build the dashboard cards.
2.  Build the chat table and detail view.
3.  Integrate actions (trigger analysis, toggle chat).
