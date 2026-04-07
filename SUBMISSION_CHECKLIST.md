# Submission Checklist

Use this list right before pushing the final hackathon submission.

## Required files

- [ ] `README.md` includes Hugging Face Space frontmatter and project documentation
- [ ] `Dockerfile` is present at the repo root
- [ ] `openenv.yaml` is present at the repo root
- [ ] `inference.py` is present at the repo root
- [ ] `data/emails_easy.json` exists
- [ ] `data/emails_medium.json` exists
- [ ] `data/emails_hard.json` exists
- [ ] `scripts/validate-submission.sh` exists
- [ ] `.env.example` exists

## Local quality gates

- [ ] `python -m pytest -q`
- [ ] `openenv validate`
- [ ] `python inference.py`
- [ ] `python scripts/baseline.py --provider heuristic`
- [ ] `python scripts/evaluate.py --provider heuristic`

## Structured inference logging

- [ ] `inference.py` prints `[START]` once per task
- [ ] `inference.py` prints one `[STEP]` line after each `env.step(...)`
- [ ] `inference.py` prints one `[END]` line for each task
- [ ] `score` stays in `[0.0, 1.0]`
- [ ] `reward` values are formatted to 2 decimal places

## Hugging Face Space settings

- [ ] Space SDK is `Docker`
- [ ] Space hardware is `CPU Basic`
- [ ] `PORT=7860`
- [ ] `MAX_CONCURRENT_ENVS=32`
- [ ] `API_BASE_URL=https://router.huggingface.co/v1`
- [ ] `MODEL_NAME=gpt-4.1-mini`
- [ ] `HF_TOKEN` added as a secret
- [ ] Space repo has the `openenv` tag

## Deployment checks

- [ ] `docker build -t openenv-email-triage .`
- [ ] `docker run --rm -p 7860:7860 openenv-email-triage`
- [ ] local `http://127.0.0.1:7860/health` returns `200`
- [ ] local `POST http://127.0.0.1:7860/reset` returns `200`
- [ ] live `https://<space-url>/health` returns `200`
- [ ] live `POST https://<space-url>/reset` returns `200`

## Documentation checks

- [ ] README explains the environment motivation
- [ ] README defines the action space
- [ ] README defines the observation space
- [ ] README describes `easy`, `medium`, and `hard`
- [ ] README explains the reward function
- [ ] README includes setup and usage commands
- [ ] README includes baseline score notes

## Final command set

```powershell
cd D:\EnvMeta
.\.venv\Scripts\Activate.ps1
python -m pytest -q
openenv validate
python scripts\baseline.py --provider heuristic
python scripts\evaluate.py --provider heuristic
python inference.py
python scripts\pre_submit_check.py
```
