# TASK T12: User Feedback Loop (Chat 👍/👎)
**Project:** /home/sebastian/personal-ai
**Status file:** /tmp/gilbertus_upgrade/status/T12.done

## Context
Table `response_feedback` exists in PG with columns: id, ask_run_id, rating, comment, created_at.
Backend has /feedback/trends and /feedback/weak-areas but NO endpoint for user to submit chat feedback.
Frontend has NO thumbs up/down in the chat interface.
The chat response already returns `run_id` (from AskResponse.run_id).

## What to do

### Step 1: Verify backend structure
```
cat /home/sebastian/personal-ai/app/api/feedback.py
grep -n "run_id\|ask_run_id" /home/sebastian/personal-ai/app/api/schemas.py | head -10
grep -n "run_id" /home/sebastian/personal-ai/app/api/main.py | head -10
```

### Step 2: Add POST /feedback/submit endpoint to app/api/feedback.py

Add to the existing feedback.py router:

```python
from pydantic import BaseModel, Field

class ChatFeedback(BaseModel):
    run_id: int
    rating: int = Field(..., ge=-1, le=1, description="1=thumbs up, -1=thumbs down")
    comment: str | None = None

@router.post("/submit")
def submit_chat_feedback(body: ChatFeedback) -> dict:
    """Submit user feedback for a chat answer (thumbs up/down)."""
    try:
        from app.db.postgres import get_pg_connection
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                # Check if feedback already exists for this run
                cur.execute(
                    "SELECT id FROM response_feedback WHERE ask_run_id = %s",
                    (body.run_id,)
                )
                existing = cur.fetchone()
                if existing:
                    # Update existing
                    cur.execute(
                        "UPDATE response_feedback SET rating = %s, comment = %s WHERE ask_run_id = %s",
                        (body.rating, body.comment, body.run_id)
                    )
                else:
                    # Insert new
                    cur.execute(
                        "INSERT INTO response_feedback (ask_run_id, rating, comment) VALUES (%s, %s, %s)",
                        (body.run_id, body.rating, body.comment)
                    )
            conn.commit()
        return {"status": "ok", "run_id": body.run_id, "rating": body.rating}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

### Step 3: Add submitFeedback to frontend API client

Add to /home/sebastian/personal-ai/frontend/packages/api-client/src/chat.ts:

```typescript
export async function submitChatFeedback(
  runId: number,
  rating: 1 | -1,
  comment?: string,
): Promise<{ status: string }> {
  return customFetch<{ status: string }>({
    url: '/feedback/submit',
    method: 'POST',
    data: { run_id: runId, rating, comment },
  });
}
```

Export it from the package index (find the index.ts in api-client/src and add it there).

### Step 4: Add feedback buttons to chat messages in frontend

Find the chat message component. Look in:
- /home/sebastian/personal-ai/frontend/apps/web/lib/hooks/use-chat.ts (for store/state)
- /home/sebastian/personal-ai/frontend/apps/web/app/(app)/chat/ or similar path

First find where chat messages are rendered:
```
find /home/sebastian/personal-ai/frontend -name "*.tsx" | xargs grep -l "assistant.*message\|ChatMessage\|chat.*bubble" 2>/dev/null | grep -v node_modules | head -10
```

In the assistant message component, add feedback buttons BELOW the answer text:

```tsx
// Add to imports
import { submitChatFeedback } from '@gilbertus/api-client';
import { ThumbsUp, ThumbsDown } from 'lucide-react';
import { useState } from 'react';

// In the component, after message.content display:
{message.runId && (
  <FeedbackButtons runId={message.runId} />
)}
```

Create a simple FeedbackButtons component:
```tsx
function FeedbackButtons({ runId }: { runId: number }) {
  const [submitted, setSubmitted] = useState<1 | -1 | null>(null);
  
  const handleFeedback = async (rating: 1 | -1) => {
    if (submitted !== null) return;
    setSubmitted(rating);
    await submitChatFeedback(runId, rating);
  };

  return (
    <div className="flex items-center gap-2 mt-2 pt-2 border-t border-[var(--border)] opacity-60 hover:opacity-100 transition-opacity">
      <span className="text-xs text-[var(--text-muted)]">Przydatne?</span>
      <button
        onClick={() => handleFeedback(1)}
        disabled={submitted !== null}
        className={`p-1 rounded hover:bg-[var(--surface-hover)] transition-colors ${submitted === 1 ? 'text-green-500' : 'text-[var(--text-muted)]'}`}
        title="Tak, pomocne"
      >
        <ThumbsUp size={14} />
      </button>
      <button
        onClick={() => handleFeedback(-1)}
        disabled={submitted !== null}
        className={`p-1 rounded hover:bg-[var(--surface-hover)] transition-colors ${submitted === -1 ? 'text-red-400' : 'text-[var(--text-muted)]'}`}
        title="Nie, niepomocne"
      >
        <ThumbsDown size={14} />
      </button>
      {submitted !== null && (
        <span className="text-xs text-[var(--text-muted)]">Dziękuję!</span>
      )}
    </div>
  );
}
```

### Step 5: Ensure run_id flows to frontend

Check if run_id is in the chat message state. Look at:
```
cat /home/sebastian/personal-ai/frontend/apps/web/lib/hooks/use-chat.ts | grep -A 20 "run_id\|runId"
```

If run_id is not stored in message state, add it:
- Find the store/state type for chat messages
- Add `runId?: number` field
- In the handler that processes API response, map `response.run_id` to message state

### Step 6: Rebuild frontend and test
```
cd /home/sebastian/personal-ai/frontend/apps/web && npm run build 2>&1 | tail -10
# If dev server running, it should hot reload automatically
```

Test the endpoint directly:
```
# Find a recent run_id
docker exec gilbertus-postgres psql -U gilbertus -c "SELECT id FROM ask_runs ORDER BY created_at DESC LIMIT 1;" 2>/dev/null

# Test feedback submission
curl -s -X POST http://127.0.0.1:8000/feedback/submit \
  -H 'Content-Type: application/json' \
  -d '{"run_id": 1, "rating": 1, "comment": "test"}' | python3 -m json.tool
```

### Step 7: Commit
```
cd /home/sebastian/personal-ai
git add app/api/feedback.py frontend/
git commit -m "feat(feedback): add user thumbs up/down to chat interface

- New POST /feedback/submit endpoint
- Frontend FeedbackButtons component on each assistant message
- run_id flows from API response to UI state
- response_feedback table stores all ratings"
```

## Completion
```
echo "done" > /tmp/gilbertus_upgrade/status/T12.done
openclaw system event --text "Upgrade T12 done: chat feedback 👍/👎 buttons live" --mode now
```
