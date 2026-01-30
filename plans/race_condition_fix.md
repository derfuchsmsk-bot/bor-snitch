# Fix for Duplicate Points (Race Condition)

## Problem Analysis
The user reported that points are sometimes awarded twice for the same event. Screenshots show two different "Daily Summary" messages, suggesting that the daily analysis was triggered twice concurrently.

The root cause is a **Race Condition** in `src/services/db.py`: `save_daily_results`.

Current logic:
1.  **Read**: Check if `daily_results/{date}` exists.
2.  **Write**: If it exists, revert old points.
3.  **Write**: Save new result.
4.  **Write**: Add new points.

If two processes run this simultaneously (e.g., Process A and Process B):
1.  A checks DB -> Not Found.
2.  B checks DB -> Not Found.
3.  A writes Result (e.g., User X +10).
4.  B writes Result (e.g., User X +10). Overwrites A's record.
5.  A adds points to User X -> Total +10.
6.  B adds points to User X -> Total +20.

Because B didn't see A's record (step 2 happened before step 3), B didn't revert A's points. The result is double points.

## Proposed Solution

Refactor `save_daily_results` to use a **Firestore Transaction**.

A transaction ensures that all reads and writes happen atomically. If the data changes between the read and the write, the transaction retries.

### Transaction Logic:
1.  **Read**: Get `daily_results/{date}`.
2.  **Read**: Get `user_stats` for all involved users (from both the existing record and the new analysis).
3.  **Logic**:
    *   If record exists: Calculate points to *remove* (Revert).
    *   Calculate points to *add* (New).
    *   Compute net change for each user.
4.  **Write**: Update `daily_results/{date}` and all `user_stats` documents in a single atomic commit.

## Additional Safeguards
*   **Distributed Lock**: Implement a simple lock file `locks/daily_analysis_{chat_id}_{date}` to prevent the AI analysis from even running twice in parallel, saving costs and reducing contention.

## Cleanup
We also need to know if we should create a script to fix the affected users' points (subtract the duplicates).
