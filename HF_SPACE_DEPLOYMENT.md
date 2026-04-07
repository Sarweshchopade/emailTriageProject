# Hugging Face Space Deployment

This repo is prepared for a Docker-based Hugging Face Space. Use the settings below exactly unless your team has a specific reason to change them.

## Required repo files

- `README.md` with Hugging Face Space frontmatter
- `Dockerfile`
- `openenv.yaml`
- `inference.py`
- `server/`
- `environment/`
- `data/`

## Space creation settings

Create a new Space with these values:

| Setting | Value |
|---------|-------|
| Space SDK | `Docker` |
| Space title | `OpenEnv Email Triage Assistant` |
| Visibility | `Public` recommended |
| Hardware | `CPU Basic` |
| Sleep time | default |
| Persistent storage | not required |

## Variables

Add these Space variables:

| Variable | Value |
|----------|-------|
| `PORT` | `7860` |
| `MAX_CONCURRENT_ENVS` | `32` |
| `API_BASE_URL` | `https://router.huggingface.co/v1` |
| `MODEL_NAME` | `gpt-4.1-mini` |

## Secrets

Add these Space secrets:

| Secret | Value |
|--------|-------|
| `HF_TOKEN` | your Hugging Face router token or provider key |

Optional local-only secret:

| Secret | Value |
|--------|-------|
| `OPENAI_API_KEY` | only needed for `scripts/baseline.py --provider openai` |

## Expected runtime behavior

- The container starts FastAPI from `server.app`.
- The app listens on port `7860`.
- OpenEnv endpoints are available at `/reset`, `/step`, `/state`, `/schema`, and `/health`.
- The custom web UI is available at `/`.

## Local smoke test before push

```powershell
cd D:\EnvMeta
docker build -t openenv-email-triage .
docker run --rm -p 7860:7860 --env PORT=7860 openenv-email-triage
```

In a second terminal:

```powershell
curl http://127.0.0.1:7860/health
curl -Method Post http://127.0.0.1:7860/reset -ContentType "application/json" -Body "{}"
python inference.py
```

## Post-deploy checks

Replace `<space-url>` with your live Space URL:

```powershell
curl https://<space-url>/health
curl -Method Post https://<space-url>/reset -ContentType "application/json" -Body "{}"
```

Expected results:

- `/health` returns HTTP `200`
- `/reset` returns HTTP `200`
- the Space root `/` loads the inbox UI
- `openenv validate` passes locally before push

## Notes

- `inference.py` reads `API_BASE_URL`, `MODEL_NAME`, and `HF_TOKEN` and uses the OpenAI client as required by the submission rules.
- If `HF_TOKEN` is absent, `inference.py` falls back to the deterministic heuristic agent so local smoke tests still complete.
- For the hackathon submission, keep `README.md`, `openenv.yaml`, and `inference.py` in the repo root.
