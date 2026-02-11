# Firestore Schema for Self-Learning System

## Overview
The system introduces three new collections nested under `chats/{chat_id}` to support dynamic lore, long-term memory, and behavioral adaptation.

## 1. Dynamic Lore (`lore`)

**Path:** `chats/{chat_id}/lore/current`
**Purpose:** Stores the active knowledge base used by the bot for generating responses and analyzing behavior. Replaces the static `LORE_DATA` in `src/utils/lore.py`.

**Fields:**
```json
{
  "data": {
    "universe": { ... },
    "characters": [ ... ],
    "concepts": { ... },
    "dictionary": { ... },
    "legendary_events": [ ... ]
  },
  "version": 1,
  "updated_at": "2026-02-11T12:00:00Z",
  "generated_by": "migration_script" // or "evolution_job", "admin_override"
}
```

## 2. Long-term Memory (`memories`)

**Path:** `chats/{chat_id}/memories/{date_key}` (e.g., `2026-02-11`)
**Purpose:** Summarized history of daily events. Used to provide context for future decisions without loading thousands of raw messages.

**Fields:**
```json
{
  "date": "2026-02-11",
  "summary": "The chat was active. Vanya argued with Vlad about Dota 2. Elya shared a photo of a cat.",
  "key_facts": [
    "Vanya reached Immortal rank in Dota 2",
    "Elya's cat is named Barsik"
  ],
  "emotional_vibe": "Competitive, slightly toxic",
  "message_count": 452,
  "major_events": [
    {
      "title": "Dota Dispute",
      "participants": ["@ioann_thegreat", "@prodolzhayem"],
      "outcome": "Vlad left the chat for 2 hours"
    }
  ]
}
```

## 3. Behavioral Lessons (`lessons`)

**Path:** `chats/{chat_id}/lessons/{lesson_id}`
**Purpose:** Stores rules learned from user feedback (replies to bot) or self-reflection. These are injected into the System Prompt.

**Fields:**
```json
{
  "created_at": "2026-02-11T12:30:00Z",
  "trigger_context": "Bot made a joke about Vanya's height. Vanya replied 'not funny'.",
  "learned_rule": "Avoid jokes about Vanya's physical appearance.",
  "status": "active", // "proposed", "active", "rejected"
  "confidence": 0.85,
  "expiration": "2026-03-11T12:30:00Z" // Optional: temporary rules
}
```

## Data Flow

1.  **Daily Cycle:**
    *   **Raw Logs** -> `analyze_daily_logs` -> **Daily Verdict** (Current)
    *   **Daily Verdict** + **User Replies** -> `analyze_feedback` -> **New Lesson** (Proposed)
    *   **Raw Logs** -> `summarize_day` -> **Memory Document**

2.  **Weekly/Monthly Cycle:**
    *   **Current Lore** + **Recent Memories** + **Active Lessons** -> `evolve_lore` -> **New Lore Version**
