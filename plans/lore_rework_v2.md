# Lore System Rework (Anti-Hallucination & Naturalness)

## Problem
The current bot is described as answering "terribly". Key issues identified:
1.  **Hallucinations:** It invents facts or misinterprets jokes as reality, treating them as absolute truth.
2.  **Robotic/Repetitive:** It forces "Lore" references (e.g., "shades", "tiles") where they don't belong, making it feel artificial.
3.  **Static/Incorrect:** It fails to distinguish between a "current state" (temporary) and "permanent traits".

## Solution Architecture

### 1. Data Structure Refinement ("Tiered Truth")
We will restructure the Lore in Firestore `chats/{id}/lore/current` to separate different types of information.

*   **`core` (Immutable-ish):** The base universe definitions.
    *   *Content:* Names, handles, base archetypes (e.g., "Shaloputnik is a gambler").
    *   *Update Policy:* Rare, manual, or major "Season" updates.
*   **`verified_facts` (High Confidence):** Specific, atomic facts that the bot "knows" for sure.
    *   *Content:* "Vanya has a cat named Barsik", "Vlad bought a PC in 2026".
    *   *Update Policy:* Added via explicit confirmation or high-frequency consistency.
*   **`current_context` (Ephemeral):** What is relevant *right now* (last 3-7 days).
    *   *Content:* "Vlad is on vacation", "They are arguing about Dota".
    *   *Update Policy:* Rotates based on `daily_summary`. Cleared if not reinforced.
*   **`style_guidelines`:** Learned behavioral instructions.
    *   *Content:* "Don't joke about Vanya's height", "Be more sarcastic about gambling".

### 2. Prompt Engineering Refactor
Update `src/utils/prompts.py` to:
*   **Strictly Separate Knowledge:**
    *   "Use `verified_facts` as absolute truth."
    *   "Use `current_context` as conversation starters, but verify if unsure."
    *   "Do NOT use `core` lore (historical memes like 'shades') unless the user provides a direct keyword trigger."
*   **Naturalness:** Instructions to avoid "narrator voice" and "forced references".

### 3. "Fact-Check" Mechanism (New Service)
Create `src/services/fact_service.py`:
*   **User Correction:** Support natural language corrections.
    *   *User:* "I sold that car already."
    *   *Bot Action:* Detects correction -> Removes "Has car" from `verified_facts` -> Adds "Sold car" -> Acknowledges.
*   **Explicit Command:** `/remember <fact>` to force-add a verified fact.

### 4. Refined Evolution Engine
Refactor `src/scripts/evolve_lore.py`:
*   **Validation Step:** Instead of blindly rewriting the whole JSON, it should:
    1.  Extract *Candidates* from daily memories.
    2.  Check for conflicts with `verified_facts`.
    3.  If conflict: Trust `verified_facts` (or flag for review).
    4.  If new: Add to `current_context` first. Only promote to `verified_facts` after N repetitions or explicit confirmation.

## Implementation Plan

1.  **Database Migration**:
    *   Create a script to restructure existing `lore` into the new schema (`core`, `facts`, `context`).
2.  **Prompt Update**:
    *   Modify `get_system_prompt` in `src/utils/prompts.py` to ingest the new schema.
    *   Add "Anti-Hallucination" directives (e.g., "If you don't know, ask.").
3.  **Fact Service Implementation**:
    *   Create `src/services/fact_service.py` to manage the collection `chats/{id}/facts`.
4.  **Integration**:
    *   Connect `FactService` to the message analysis pipeline (to detect corrections).
    *   Update `evolve_lore.py` to use `FactService`.
