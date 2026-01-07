# Temporal Cloud Integration - Architecture & Methodology
**Date & Time**: January 7, 2026, 11:51 UTC  
**Session Focus**: Step 1 - Temporal Cloud Connectivity with Worker Infrastructure

---

## 1. Overall Architecture

### System Components

```
┌─────────────────────────────────────────────────────────┐
│                  TEMPORAL CLOUD                          │
│     us-central1.gcp.api.temporal.io:7233                 │
│     Namespace: skalable.ocfwk                            │
│     Task Queue: ap-default                               │
└─────────────────────────────────────────────────────────┘
         ▲                                    ▲
         │                                    │
         │ mTLS (TEMPORAL_API_KEY)            │
         │                                    │
    ┌────────────────┐            ┌──────────────────┐
    │  Worker Process│            │  Client Scripts  │
    │ (Long-running) │            │ (One-off triggers)
    │                │            │                  │
    │ workers/       │            │ scripts/         │
    │ worker.py      │            │ start_ping.py    │
    │                │            │ (connects        │
    │ Listens on     │            │  independently)  │
    │ ap-default     │            │                  │
    │                │            │ Returns result   │
    │ Executes:      │            │ then disconnects │
    │ - PingWorkflow │            │                  │
    └────────────────┘            └──────────────────┘
```

### Connection Model

- **Worker**: Single long-lived connection to Temporal Cloud, stays alive indefinitely listening for tasks
- **Client Scripts**: Independent, short-lived connections that trigger workflows and wait for results
- **Authentication**: mTLS via `TEMPORAL_API_KEY` environment variable
- **Credentials Source**: `temporal_client.py` factory reads from environment variables

### File Structure

```
temporalinvoice/
├── temporal_client.py          # Factory for Temporal Cloud client connections
├── workers/
│   └── worker.py               # Long-running worker listening on ap-default
├── workflows/
│   └── ping_workflow.py         # Simple no-op workflow for connectivity test
├── scripts/
│   ├── start_ping.py            # Trigger PingWorkflow on Cloud
│   └── check_temporal_config.py # Verify credentials are configured
├── extraction/                  # (Step 0 completed)
├── reconciliation/              # (Step 0 completed)
├── storage/                     # (Step 0 completed)
├── models/                      # (Step 0 completed)
└── ARCHITECTURE_AND_METHODOLOGY.md  # This document
```

---

## 2. Most Repeated Issues & Fixes

### Issue #1: Worker Exiting Immediately (Critical - Fixed)

**Symptom**: Worker process exited with `exit code 1` after running for a few seconds

**Root Cause**: `except asyncio.CancelledError` handler in `workers/worker.py` was catching legitimate task execution cancellations and returning normally, causing the process to exit gracefully instead of staying alive.

**Fix Applied**:
```python
# WRONG - Catches cancellation and exits
try:
    await worker.run()
except asyncio.CancelledError:  # ❌ This catches and returns, exiting the worker
    logger.info("Cancelled")

# CORRECT - Let cancellation propagate naturally
try:
    await worker.run()
except KeyboardInterrupt:  # ✅ Only catch user interruption
    logger.info("Worker interrupted by user")
```

**Key Lesson**: Don't catch `CancelledError` in Python asyncio unless you have a very specific reason. It's a control flow mechanism that should propagate naturally.

---

### Issue #2: Worker Shutdown on Workflow Execution

**Symptom**: Worker stays running until a workflow is executed, then Temporal Cloud sends "Worker cancelled, shutting down" and the worker exits

**Status**: Under investigation - likely expected behavior or configuration issue

**Hypothesis**: 
- Possible: Worker lifecycle is tied to task execution completion
- Possible: Temporal Cloud has a default shutdown policy after task completion
- Possible: Connection management between worker and client affecting each other

**Investigation Approach**:
- Check Temporal Cloud UI for worker registration status
- Review Temporal Python SDK worker configuration options
- Verify task queue configuration in Cloud console

**Temporary Workaround**: Keep worker running in separate background process, independent from client script execution

---

### Issue #3: Connection Closure Side Effects

**Symptom**: When client script closed connection with `await client.close()`, worker would also shut down

**Fix Applied**: Removed explicit `client.close()` from `scripts/start_ping.py` - client and worker have independent connections and should not interfere with each other

**Code Change**:
```python
# BEFORE - Caused worker to shut down
finally:
    if client:
        await client.close()  # ❌ Interferes with worker connection

# AFTER - Worker stays independent
# (No client.close() - let connection be managed by asyncio cleanup)
```

---

### Issue #4: PowerShell Command Syntax Differences

**Symptom**: Commands like `head`, `2>&1 | Select-Object` worked differently in PowerShell vs bash

**Fix**: Adapted to PowerShell 5.1 idioms:
- Use `Select-Object -First 30` instead of `head -20`
- Use `Get-Process` instead of `ps`
- Use `Stop-Process` instead of `kill`

---

## 3. Development Methodology

### Verification Strategy (Multi-Layered)

#### Layer 1: Configuration Verification
```bash
.venv\Scripts\python.exe scripts/check_temporal_config.py
```
- Verifies `TEMPORAL_ENDPOINT`, `TEMPORAL_NAMESPACE`, `TEMPORAL_API_KEY` are set
- Tests basic connection to Temporal Cloud
- **Exit 0** = credentials valid and accessible

#### Layer 2: Component Testing
```bash
.venv\Scripts\python.exe -c "
from temporal_client import get_temporal_client
from temporalio.worker import Worker
from workflows.ping_workflow import PingWorkflow

# Test: Can we create a client?
client = await get_temporal_client()  # ✓

# Test: Can we create a worker?
worker = Worker(client, task_queue='ap-default', workflows=[PingWorkflow])  # ✓
"
```
- Isolates client creation from worker execution
- Isolates worker creation from `worker.run()` blocking
- Helps identify which component is failing

#### Layer 3: Integration Testing
```bash
# Terminal 1: Start worker (background)
.venv\Scripts\python.exe workers/worker.py

# Terminal 2: Trigger workflow (foreground)
.venv\Scripts\python.exe scripts/start_ping.py
```
- Worker must stay running indefinitely
- Client script independently triggers workflow
- Check output for success messages

---

### Debugging Pattern

When something fails:

1. **Verify Configuration** (Layer 1)
   - Are environment variables set?
   - Can we connect at all?

2. **Isolate Components** (Layer 2)
   - Can we create a client?
   - Can we create a worker?
   - Where exactly does it fail?

3. **Test Integration** (Layer 3)
   - Run worker in one terminal
   - Run client in another terminal
   - Monitor both for errors

4. **Check Logs**
   - Worker logs (STDOUT)
   - Error output (STDERR)
   - Temporal Cloud UI for workflow execution status

---

## 4. Current Status

### ✅ Completed

- **Step 0**: Module refactoring - all business logic extracted to importable modules
  - `extraction/runner.py` - extraction logic
  - `reconciliation/engine.py` - reconciliation logic
  - `storage/artifacts.py` - artifact management
  - `models/refs.py` - data models

- **Step 1 (Partial)**: Temporal Cloud Infrastructure
  - ✅ Credentials configured and verified
  - ✅ Client factory working (`temporal_client.py`)
  - ✅ Worker process starts successfully (`workers/worker.py`)
  - ✅ Workflow definition complete (`workflows/ping_workflow.py`)
  - ✅ Trigger script working (`scripts/start_ping.py`)
  - ⚠️ Worker lifecycle issue with task execution (under investigation)

### 🔄 In Progress

- **Worker Stability**: Why worker shuts down after workflow execution
- **Long-running Worker Validation**: Ensure worker stays alive across multiple workflow executions

### ⏳ Pending

- Full end-to-end workflow execution in Temporal Cloud
- Validate workflow appears in Cloud UI with COMPLETED status
- Verify return value "ok" is received by client script

---

## 5. Next Steps (Recommendations)

### Immediate (Today)

1. **Investigate Worker Shutdown**
   - Check Temporal Cloud UI for worker status
   - Review Worker configuration options (heartbeat, polling, etc.)
   - Check if this is expected behavior or misconfiguration

2. **Test Worker Persistence**
   - Start worker
   - Execute multiple workflows back-to-back
   - Verify worker stays alive throughout

### Short-term (This Week)

1. **Add Logging & Monitoring**
   - Enhanced worker heartbeat logging
   - Task execution lifecycle logging
   - Connection lifecycle logging

2. **Create Dashboard**
   - Monitor worker status
   - Track workflow executions
   - View recent errors

### Medium-term (This Month)

1. **Implement Actual Workflows**
   - Move `extraction/runner.py` logic into activities
   - Move `reconciliation/engine.py` logic into workflows
   - Chain multiple activities in orchestration workflow

2. **Add Error Handling**
   - Retry policies for failed tasks
   - Dead letter queue handling
   - Alerting on workflow failures

---

## 6. Key Learnings

### What Worked Well

- **Modular Design** (Step 0): Separating business logic into importable modules made testing much easier
- **Environment-Based Configuration**: Using `TEMPORAL_API_KEY` env var for credentials is clean and secure
- **Layered Verification**: Testing each component in isolation before integration testing
- **Independent Processes**: Keeping worker and client as completely separate processes prevents interference

### What To Avoid

- **Catching CancelledError**: Python's asyncio uses this for control flow, not for error handling
- **Shared Connection Lifecycle**: Don't let client connection closure affect worker connection
- **Mixing Shell Commands**: PowerShell has different idioms than bash - stick to one or abstract them

### Best Practices Established

1. Always test configuration first (fail fast)
2. Isolate components before integrating
3. Keep long-running processes in separate terminals/processes
4. Log everything with timestamps for easy debugging
5. Use environment variables for sensitive credentials

---

## 7. Technical Stack Summary

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.11.1 |
| Runtime | venv | n/a |
| Temporal SDK | temporalio | Latest |
| Cloud Provider | Temporal Cloud | us-central1.gcp |
| Authentication | mTLS | Via API Key |
| Environment | Windows 11 | PowerShell 5.1 |

---

## 8. Temporal Cloud Configuration

```
Endpoint:   us-central1.gcp.api.temporal.io:7233
Namespace:  skalable.ocfwk
Task Queue: ap-default
Auth:       mTLS (Certificate in TEMPORAL_API_KEY)
Timeout:    30 seconds (default client timeout)
```

---

**Document Last Updated**: January 7, 2026, 11:51 UTC  
**Next Review**: After worker persistence testing
