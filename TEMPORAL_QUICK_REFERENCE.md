# Temporal Cloud Quick Reference

## Setup Checklist

- [ ] Create account at https://cloud.temporal.io/
- [ ] Create namespace
- [ ] Generate API key
- [ ] Copy endpoint
- [ ] Add to `.env` file:
  ```
  TEMPORAL_ENDPOINT=<namespace>.tmprl.cloud:7233
  TEMPORAL_NAMESPACE=<namespace>
  TEMPORAL_API_KEY=<key>
  ```

## Quick Commands

### Check Configuration
```bash
python scripts/check_temporal_config.py
```

### Test Locally (No Cloud)
```bash
python test_temporal_local.py
```

### Start Worker
```bash
python workers/worker.py
```

### Start Workflow
```bash
python scripts/start_ping.py
```

## Environment Variables

| Variable | Required | Example |
|----------|----------|---------|
| `TEMPORAL_ENDPOINT` | Yes | `my-namespace.tmprl.cloud:7233` |
| `TEMPORAL_NAMESPACE` | No | `my-namespace` (default: "default") |
| `TEMPORAL_API_KEY` | Yes | `<your-mTLS-key>` |
| `TEMPORAL_CERT_PATH` | No | `/path/to/cert.pem` (default: system certs) |

## Code Structure

### Start a Workflow
```python
from temporal_client import get_temporal_client
from workflows.ping_workflow import PingWorkflow

client = await get_temporal_client()
handle = await client.start_workflow(
    PingWorkflow.run,
    task_queue="ap-default",
    id="unique-id"
)
result = await handle.result()
```

### Create a Workflow
```python
from temporalio import workflow

@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self, param: str) -> str:
        # Do work here
        return result
```

### Register in Worker
```python
from temporalio.worker import Worker
from workflows.my_workflow import MyWorkflow

worker = Worker(
    client,
    task_queue="ap-default",
    workflows=[MyWorkflow],
)
await worker.run()
```

## Files

| File | Purpose |
|------|---------|
| `temporal_client.py` | Temporal Cloud connection |
| `workflows/ping_workflow.py` | Example workflow |
| `workers/worker.py` | Worker that runs workflows |
| `scripts/start_ping.py` | Start workflow script |
| `scripts/check_temporal_config.py` | Configuration verification |
| `test_temporal_local.py` | Local code testing |

## Task Queue

- **Name:** `ap-default`
- **Purpose:** AP automation tasks
- **Workers:** `workers/worker.py` listens here
- **Workflows:** All workflows route to this queue

## Monitoring

View workflows in Temporal Cloud UI:
1. Go to https://cloud.temporal.io/
2. Select your namespace
3. Click "Workflows"
4. See all executions with status

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "TEMPORAL_ENDPOINT not set" | Add to `.env` file |
| "Connection refused" | Verify endpoint, check Temporal Cloud |
| "Authentication failed" | Verify API key matches namespace |
| Worker won't start | Check environment variables, run `check_temporal_config.py` |
| Workflow times out | Increase timeout or check worker is running |

---

See `STEP_1_TEMPORAL_SETUP.md` for full documentation.
