# n8n + Ollama Dev Workflows — Setup Guide

## Architecture

```
┌──────────────────────────────────────────────┐
│  Your Machine (local)                        │
│                                              │
│  ┌─────────┐        ┌──────────────────┐     │
│  │  Ollama  │◄──────►│  n8n (Docker)    │     │
│  │  :11434  │  HTTP  │  :5678           │     │
│  │  (host)  │        │                  │     │
│  └─────────┘        │  Workflows:       │     │
│                      │  01 PR Risk       │     │
│  ┌─────────┐        │  02 Changelog     │     │
│  │  GitHub  │◄──────►│  03 Sprint Digest │     │
│  │  API     │  HTTP  │  04 PIPEDA Mon.   │     │
│  │          │        │  05 ADR Tracker   │     │
│  └─────────┘        └──────────────────┘     │
│                                              │
│  ┌──────────────────────────────────────┐    │
│  │  ~/Odoo-IFM/docs/adr/*.md           │    │
│  │  (mounted into n8n container)        │    │
│  └──────────────────────────────────────┘    │
└──────────────────────────────────────────────┘
```

## Prerequisites

- ✅ Ollama running on host with `qwen2.5-coder:7b` (already installed)
- ✅ n8n running in Docker on port 5678 (already running)
- GitHub personal access token (PAT) with `repo` scope

## Step 1: Mount Odoo docs into n8n container

Add this volume mount to the n8n service in `docker-compose.yml`:

```yaml
  n8n:
    # ... existing config ...
    volumes:
      - ./n8n:/home/node/.n8n
      - /home/kaung/Odoo-IFM/docs:/home/kaung/Odoo-IFM/docs:ro  # ADR files
```

Then restart: `docker compose restart n8n`

## Step 2: Set up GitHub Token credential in n8n

1. Open http://localhost:5678
2. Go to **Settings → Credentials → Add Credential**
3. Type: **Header Auth**
4. Name: `GitHub Token`
5. Header Name: `Authorization`
6. Header Value: `Bearer ghp_YOUR_PERSONAL_ACCESS_TOKEN`
7. Save — note the credential ID

## Step 3: Import workflows

For each workflow file in `n8n-workflows/`:

1. Open http://localhost:5678
2. Click **+ Add Workflow** (or the ⊕ button)
3. Click **⋯ (menu) → Import from File**
4. Select the JSON file
5. **Update credential references**: In each HTTP Request node that uses GitHub, select the `GitHub Token` credential you created
6. Save and activate

## Workflow Details

### 01 — PR Risk Assessment
- **Trigger**: Webhook (POST to `http://localhost:5678/webhook/pr-risk-assessment`)
- **What it does**: Receives a GitHub PR webhook → fetches the diff → classifies risk based on which IFM models are touched → sends diff to Ollama for semantic review → posts a risk-labeled comment on the PR
- **Local testing**: Use `curl` to simulate a PR webhook (see Testing section below)
- **Risk classification**:
  - 🔴 HIGH: 3+ files touching `_inherit` overrides, `write()` guards, state transitions, or context flags
  - 🟡 MEDIUM: 1-2 such files
  - 🟢 LOW: No sensitive files touched

### 02 — Changelog Enhancement
- **Trigger**: Webhook (POST to `http://localhost:5678/webhook/changelog-enhance`)
- **What it does**: On PR merge → fetches diff → Ollama generates a human-readable changelog entry → saves to `n8n/storage/changelog_entries.jsonl`
- **Output**: Entries accumulate locally; you can periodically copy them into your actual CHANGELOG.md

### 03 — Sprint Delivery Digest
- **Trigger**: Cron (every Friday at 5PM, timezone from n8n config: Asia/Rangoon)
- **What it does**: Pulls merged PRs from the last 7 days via GitHub API → Ollama generates a narrative sprint summary → saves as markdown in `n8n/storage/digests/`
- **Note**: Update the GitHub repo URL in the "Get Recent PRs" node to match your actual repo

### 04 — PIPEDA Compliance Monitor
- **Trigger**: Webhook (POST to `http://localhost:5678/webhook/pipeda-monitor`)
- **What it does**: On PR open → scans changed files for PII/medical model changes → if found, Ollama reviews for PIPEDA compliance concerns → posts a compliance flag comment on the PR
- **Monitors**: `medical_history`, `prescription`, `res_partner` models and PII fields like `sin_encrypted`, `birth_date`, `annual_income`, `medical_*`

### 05 — ADR Action Item Tracker
- **Trigger**: Cron (every Monday at 9AM)
- **What it does**: Reads all `docs/adr/ADR-*.md` files → Ollama extracts action items → classifies as TODO/IN PROGRESS/DONE → saves report to `n8n/storage/adr-reports/`
- **Requires**: The docs volume mount from Step 1

## Testing Locally

### Test PR Risk Assessment (simulated webhook):

```bash
curl -X POST http://localhost:5678/webhook-test/pr-risk-assessment \
  -H "Content-Type: application/json" \
  -d '{
    "action": "opened",
    "number": 1,
    "repository": { "full_name": "YOUR_ORG/ifm-odoo" },
    "pull_request": {
      "title": "test PR",
      "head": { "ref": "feature/test" },
      "merged": false
    }
  }'
```

### Test ADR Tracker (manual run):

In n8n UI, open the "05 - ADR Action Item Tracker" workflow and click **Execute Workflow** to run it manually.

### Test Sprint Digest (manual run):

Same — open workflow 03 and click **Execute Workflow**.

## Configuration Notes

- **Ollama URL**: Workflows use `http://172.19.0.1:11434` — this is the Docker host gateway address so n8n (in Docker) can reach Ollama (on host). If your Docker network gateway differs, update in each workflow's Ollama HTTP Request node.
- **Model**: All workflows use `qwen2.5-coder:7b`. To use a different model, update the `model` field in each Ollama request body.
- **Timeouts**: Ollama requests have 120s timeouts (180s for ADR tracker). Adjust if your machine is slower.
- **GitHub repo**: Workflow 03 has a hardcoded repo URL — update it to your actual org/repo.

## File Locations

| Item | Path |
|------|------|
| Workflow JSON files | `~/self_hosted/n8n-workflows/` |
| n8n data | `~/self_hosted/n8n/` |
| Sprint digests | `~/self_hosted/n8n/storage/digests/` |
| ADR reports | `~/self_hosted/n8n/storage/adr-reports/` |
| Changelog entries | `~/self_hosted/n8n/storage/changelog_entries.jsonl` |
