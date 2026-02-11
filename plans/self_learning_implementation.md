# Self-Learning Implementation Plan

## Objective
Enable the bot to evolve its personality, knowledge base (Lore), and decision-making criteria based on chat history and user feedback.

## Architecture Overview

### 1. Database Schema (Firestore)

**Collection: `chats/{chat_id}/lore`**
*   **Document: `current`**
    *   Contains the full JSON structure currently in `lore.py`.
    *   Fields: `universe`, `characters`, `concepts`, `dictionary`, `legendary_events`, `version`, `last_updated`.

**Collection: `chats/{chat_id}/memories`**
*   **Document: `{date_key}`** (e.g., "2026-02-11")
    *   `summary`: Text summary of the day's key events.
    *   `new_facts`: JSON list of potential lore updates (new nicknames, terms).
    *   `emotional_vibe`: The general mood of the day.

**Collection: `chats/{chat_id}/lessons`**
*   **Document: `{timestamp}`**
    *   `trigger`: What caused the lesson (e.g., "Users angry about weather ban").
    *   `rule_adjustment`: Text description of how to adjust behavior.
    *   `status`: "pending" | "applied" (merged into system instructions).

### 2. Phase 1: Dynamic Lore (The Knowledge Base)
*   **Goal:** Decouple `LORE` from the code.
*   **Action:**
    *   Create `LoreService` to fetch/cache lore from Firestore.
    *   Refactor `prompts.py` to be a factory that accepts a `lore` object instead of importing a constant.
    *   Migration script: Upload current `src/utils/lore.py` to the DB for the main chat.

### 3. Phase 2: Daily Reflection (The Feedback Loop)
*   **Goal:** The bot learns from its own interactions.
*   **Action:**
    *   Implement `analyze_feedback` task (runs daily alongside `analyze_daily_logs`).
    *   **Input:** The bot's previous day's verdict/messages + User replies/reactions to them.
    *   **Output:** "Critique" (Did the chat agree? Was it funny? Was it too harsh?) -> Save to `lessons`.
    *   Inject `lessons` into the `SYSTEM_PROMPT` as "Temporary Guidelines".

### 4. Phase 3: Long-term Memory (The Context)
*   **Goal:** Retain narrative history beyond the context window.
*   **Action:**
    *   Implement `summarize_day` task.
    *   **Input:** Full day's logs.
    *   **Output:** Short narrative summary + extracted "Facts" (e.g., "Elya bought a new car").
    *   Store in `memories` collection.

### 5. Phase 4: Periodic Evolution (The Growth)
*   **Goal:** Permanent updates to the core Lore and Instructions.
*   **Action:**
    *   Implement `evolve_lore` task (Weekly/Monthly).
    *   **Input:** Current Lore + Last N `memories` + Validated `lessons`.
    *   **Output:** Updated Lore JSON (new events added, traits updated) + Updated "System Personality" tweaks.
    *   **Verification:** Post the "Changelog" to the chat? (e.g., "I have noticed you call Vanya 'Master' now. Recorded.").

## Execution Strategy

1.  **Refactor Prompts:** Make them dynamic.
2.  **DB Setup:** Create the initial Lore document.
3.  **Pipeline Update:** Update `analyze_today_thoughts.py` (or the cron handler) to include the new steps (Reflection -> Summary -> Analysis).
