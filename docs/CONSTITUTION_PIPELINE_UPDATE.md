# Constitution Pipeline Update

## Changes Made

### 1. Moved Constitution Analysis After LLM-2

The Constitution now analyzes the **final refined message** instead of the initial LLM-1 response. This allows evaluation of the Constitution's effectiveness on real-world messages that users would actually see.

**Before:**
```
LLM-1 → Constitution → LLM-2 → Human Review
```

**After:**
```
LLM-1 → LLM-2 → Constitution → Human Review
```

### 2. Code Changes

#### `agents/supervisor_agent.py`
- Moved constitution analysis to after LLM-2 refinement
- Constitution now analyzes the joined bubble messages
- Removed constitution feedback from refinement prompt

#### `tests/test_hitl_supervisor.py`
- Updated tests to reflect new pipeline order
- Fixed test expectations for constitution analysis on refined messages

### 3. Key Benefits

1. **Real-world evaluation**: Constitution analyzes the actual message users would see
2. **Better metrics**: Can measure Constitution effectiveness on production-ready messages
3. **No blocking**: Constitution only provides risk analysis, never blocks messages
4. **Human decision**: Reviewers see risk scores and can make informed decisions

### 4. How It Works Now

1. User sends message
2. LLM-1 generates creative response (temp=0.8)
3. LLM-2 refines and formats into bubbles (temp=0.5)
4. Constitution analyzes final refined message
5. ReviewItem created with risk analysis
6. Human reviewer sees risk scores and violations
7. Human makes final decision to approve/reject

The Constitution's `analyze()` method returns:
- `flags`: List of detected issues
- `risk_score`: 0.0 (safe) to 1.0 (high risk)
- `recommendation`: approve/review/flag
- `violations`: Detailed list of triggered rules

This approach ensures the Constitution is tested on realistic scenarios while maintaining human oversight for all decisions.