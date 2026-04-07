---
title: OpenEnv Email Triage Assistant
emoji: "📬"
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
suggested_hardware: cpu-basic
pinned: false
tags:
  - openenv
  - fastapi
  - email
  - productivity
---

# OpenEnv Email Triage Assistant

`OpenEnv Email Triage Assistant` is a deterministic OpenEnv benchmark for a real workplace task: managing an inbox under time pressure. Instead of solving a toy game, agents must classify, draft, delegate, schedule, snooze, and clean up email threads the way an operations lead, founder, PM, or customer-facing teammate would.

## Motivation

Email triage is a strong agent benchmark because it combines:

- prioritization under constrained action budgets
- natural-language drafting with concrete commitments
- workflow routing through delegation and scheduling
- mixed-value inbox noise alongside genuinely urgent work

The environment is intentionally deterministic so graders are reproducible and task scores stay in the `0.0` to `1.0` range required by the OpenEnv evaluation pipeline.

## Tasks

| Task | Difficulty | Objective |
|------|------------|-----------|
| `easy` | Easy | Classify 5 emails into `urgent`, `important`, `low`, or `spam` |
| `medium` | Medium | Process 3 active threads with response drafting, delegation, and scheduling |
| `hard` | Hard | Manage a 10-email mixed inbox with conflicting priorities, low-value noise, and ordering pressure |

## Action Space

The environment accepts a typed `EmailAction` model with:

- `action_type`: `classify`, `archive`, `delete`, `respond`, `delegate`, `snooze`, `schedule`
- `email_id`: target email identifier
- `priority`: required for `classify`
- `response_text`: optional but required for `respond`
- `delegate_to`: required for `delegate`
- `snooze_until`: required for `snooze`
- `scheduled_time`: required for `schedule`
- `rationale`: optional free-form reasoning field

## Observation Space

Each step returns a typed `Observation` model containing:

- `current_emails`: unresolved inbox items still available for action
- `action_history`: full action trace so far
- `remaining_actions`: step budget left in the episode
- `task_name`: active task id
- `task_description`: natural-language objective for the task

## Reward Function

The `Reward` model includes:

- `score`: cumulative task completion score in `[0.0, 1.0]`
- `delta`: incremental reward from the most recent action
- `breakdown`: deterministic grader details per email

Reward shaping is based on partial progress toward expected outcomes. The environment also:

- penalizes inefficient late-episode behavior with a small delta reduction
- ends the episode on invalid actions
- gives the hard grader extra signal for urgency ordering and correct delegation

## Baselines

The repo ships with two baseline modes:

- `heuristic`: deterministic local smoke-test agent with no API key required
- `openai`: OpenAI SDK baseline for model-driven action generation

Latest local heuristic smoke baseline:

| Task | Score |
|------|-------|
| `easy` | `1.00` |
| `medium` | `1.00` |
| `hard` | `0.87` |

These scores are useful for reproducibility and CI, though they should not be treated as the final ceiling of benchmark difficulty.

## Project Layout

```text
environment/
data/
scripts/
server/
tests/
openenv.yaml
inference.py
Dockerfile
requirements.txt
```

## Quick Start

```powershell
cd D:\EnvMeta
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
python scripts\baseline.py --provider heuristic
python scripts\evaluate.py --provider heuristic
python inference.py
openenv validate
```

## Run in VS Code

```powershell
code D:\EnvMeta
cd D:\EnvMeta
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
python scripts\baseline.py --provider heuristic
python scripts\evaluate.py --provider heuristic
python inference.py
openenv validate
python -m server.app
```

Once the server starts, open [http://127.0.0.1:7860/](http://127.0.0.1:7860/) in Chrome. API docs are available at [http://127.0.0.1:7860/docs](http://127.0.0.1:7860/docs).

## Run in Chrome

```powershell
cd D:\EnvMeta
.\.venv\Scripts\Activate.ps1
python -m server.app
start chrome http://127.0.0.1:7860/
```

If `chrome` is not recognized:

```powershell
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" "http://127.0.0.1:7860/"
```

## Optional OpenAI Baseline

```powershell
$env:OPENAI_API_KEY="your-openai-key"
$env:OPENAI_MODEL="gpt-4.1-mini"
python scripts\baseline.py --provider openai
```

## Submission Inference Script

The root `inference.py` is wired for the submission contract and reads:

- `API_BASE_URL`
- `MODEL_NAME`
- `HF_TOKEN`

Example:

```powershell
$env:API_BASE_URL="https://router.huggingface.co/v1"
$env:MODEL_NAME="gpt-4.1-mini"
$env:HF_TOKEN="your-token"
python inference.py
```

If `HF_TOKEN` is not set, `inference.py` falls back to the deterministic heuristic agent so local smoke tests still complete.

## Hugging Face Space Deployment

This repo is set up for a Docker-based Space. Use these exact settings:

| Setting | Value |
|---------|-------|
| SDK | `Docker` |
| Hardware | `CPU Basic` |
| Port | `7860` |
| Variable | `PORT=7860` |
| Variable | `MAX_CONCURRENT_ENVS=32` |
| Variable | `API_BASE_URL=https://router.huggingface.co/v1` |
| Variable | `MODEL_NAME=gpt-4.1-mini` |
| Secret | `HF_TOKEN=<your token>` |

Detailed deployment notes are in `HF_SPACE_DEPLOYMENT.md`.

## Pre-Submission Validation

Run the local cross-platform checker:

```powershell
python scripts\pre_submit_check.py
```

You can also run the shell validator against a live Space URL:

```bash
bash scripts/validate-submission.sh https://your-space-url.hf.space .
```

## Environment Contract

- HTTP endpoints: `/reset`, `/step`, `/state`, `/schema`, `/health`
- UI endpoint: `/`
- OpenEnv metadata: `openenv.yaml`
- Container entrypoint: `python -m server.app`

## Notes

- Datasets are handcrafted and deterministic for stable grading.
- The hard-task grader rewards both correctness and urgent-sequencing behavior.
- Local `openenv validate` passes in this workspace.
