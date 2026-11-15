# Fix Remaining Issues Plan - CURRENT STATE ANALYSIS

## Current State (After "Revert")

The user reverted to a state that **still has all the bugs** causing 2-minute scans:

| Bug | Current Value | Problem |
|-----|---------------|---------|
| **GROQ_MODEL** | `openai/gpt-oss-20b` | 8000 TPM limit - too low |
| **GROQ_MODEL_FALLBACKS** | `["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.6-27b"]` | All low TPM |
| **_STRICT_STRUCTURED_MODELS** | `{"openai/gpt-oss-20b", "openai/gpt-oss-120b"}` | qwen NOT included → json_object mode → schema fails |
| **Batch size limit** | **NONE** | All findings in 1 request → TPM exceeded |
| **Retries** | 3 attempts, 30s max_delay | 3 × 30s = 90s per Groq call |
| **Trivy command** | `trivy fs --scanners misconfig,vuln` | 31s (policy init) |
| **Config-only mode** | **NONE** | IaC targets get full vuln scan |

---

## Root Cause of 2-Minute Delay

```
User scan (10-20 findings)
    → Trivy: 31s
    → Groq verify_batch(): ALL findings in 1 batch
        → Prompt tokens > 8000 TPM (gpt-oss-20b limit)
        → Groq returns 413/429 error
        → Retry 1: wait 2s → fails again
        → Retry 2: wait 4s → fails again  
        → Retry 3: wait 8s → fails again
        → Total Groq time: ~90s
    → Total: 31s + 90s + overhead = ~2 minutes
```

---

## Fix Plan (Exact Changes Needed)

### 1. backend/core/config.py - Fix Model Selection
```python
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")  # Higher TPM
GROQ_MODEL_FALLBACKS: list[str] = ["qwen/qwen3.6-27b"]  # Only qwen, fail fast
```

### 2. backend/compliance/verification.py - Add qwen to Strict Models + Batch Size Limit
```python
# Line 85: Add qwen
_STRICT_STRUCTURED_MODELS = {"openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.6-27b"}

# In GroqVerifier.__init__: Add max_batch_size parameter
def __init__(self, timeout: float = 60.0, max_batch_size: int = 10) -> None:
    ...
    self._max_batch_size = max_batch_size

# In verify_batch(): Split into batches of max_batch_size
def verify_batch(self, items: list[PendingVerification]) -> dict[int, VerificationDecision]:
    if not items:
        return {}
    
    # Split into batches
    all_results = {}
    for i in range(0, len(items), self._max_batch_size):
        batch = items[i:i + self._max_batch_size]
        batch_results = self._verify_single_batch(batch)
        all_results.update(batch_results)
    return all_results

# Reduce retries: attempts=2, max_delay=15.0 (lines 266-270)
```

### 3. backend/scanners/runners.py - Add Config-Only Trivy Mode
```python
# Add scan_mode parameter to TrivyScanner.run()
def run(self, target: str, timeout: int = 300, cancel_event: Event | None = None, scan_mode: str = "full") -> ...
    
# In run_scanners(): pass scan_mode from request
# For IaC targets (k8s, terraform): use "config-only" mode
# Command: trivy config --skip-check-update --skip-version-check --format json <target>
# Time: 15-20s vs 31s
```

### 4. backend/api/schemas.py - Add scan_mode to ScanRequest
```python
class ScanRequest(BaseModel):
    target: str
    scanners: list[str] | None = None
    scan_profile: str | None = None
    framework: str | None = None
    scan_mode: str = "full"  # "full" or "config-only"
```

---

## Target Times After Fixes

| Scenario | Trivy | Groq (batched) | Overhead | Total |
|----------|-------|----------------|----------|-------|
| **Config-only (IaC)** | 15-20s | 2-3s (1-2 batches) | ~5s | **22-28s** ✓ |
| **Full scan** | 26-31s | 3-5s (2-3 batches) | ~5s | **34-41s** |

---

## Validation

1. `pytest tests/test_scanners.py tests/test_mvp_workflow.py -v`
2. Config-only scan on Kubernetes YAML → **<30s total**
3. Check logs: Groq batch size ≤10, no TPM errors, valid structured output
4. Full scan on repo → **<45s** (after Trivy upgrade to 0.76.2)