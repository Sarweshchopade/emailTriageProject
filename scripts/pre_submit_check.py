from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.app import app


REQUIRED_FILES = [
    "README.md",
    "Dockerfile",
    "openenv.yaml",
    "inference.py",
    ".env.example",
    "HF_SPACE_DEPLOYMENT.md",
    "SUBMISSION_CHECKLIST.md",
    "scripts/validate-submission.sh",
    "data/emails_easy.json",
    "data/emails_medium.json",
    "data/emails_hard.json",
]


def print_check(name: str, ok: bool, detail: str = "") -> None:
    marker = "[OK]" if ok else "[FAIL]"
    suffix = f" - {detail}" if detail else ""
    print(f"{marker} {name}{suffix}")


def run_command(label: str, command: list[str]) -> bool:
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    ok = result.returncode == 0
    detail = ""
    if not ok:
        detail = (result.stderr or result.stdout).strip().splitlines()[-1] if (result.stderr or result.stdout) else ""
    print_check(label, ok, detail)
    return ok


def check_required_files() -> bool:
    ok = True
    for relative_path in REQUIRED_FILES:
        exists = (ROOT / relative_path).exists()
        print_check(f"file:{relative_path}", exists)
        ok &= exists
    return ok


def check_readme_frontmatter() -> bool:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", readme, re.DOTALL)
    if not match:
        print_check("readme_frontmatter", False, "Missing Hugging Face YAML frontmatter")
        return False

    frontmatter = match.group(1)
    checks = [
        ("readme_sdk", "sdk: docker" in frontmatter),
        ("readme_app_port", "app_port: 7860" in frontmatter),
        ("readme_openenv_tag", "openenv" in frontmatter),
    ]
    ok = True
    for label, passed in checks:
        print_check(label, passed)
        ok &= passed
    return ok


def check_http_endpoints() -> bool:
    client = TestClient(app)
    ok = True

    routes = [
        ("GET /", client.get("/")),
        ("GET /health", client.get("/health")),
        ("GET /state", client.get("/state")),
        ("GET /schema", client.get("/schema")),
        ("POST /reset", client.post("/reset", json={})),
    ]

    for label, response in routes:
        passed = response.status_code == 200
        print_check(label, passed, f"status={response.status_code}")
        ok &= passed

    reset_response = client.post("/reset", json={})
    if reset_response.status_code != 200:
        print_check("POST /step", False, "reset did not create a valid environment session")
        return False

    payload = reset_response.json()
    observation = payload.get("observation", {})
    emails = observation.get("current_emails", [])
    if not emails:
        print_check("POST /step", False, "no emails returned from reset")
        return False

    email_id = emails[0]["id"]
    step_response = client.post(
        "/step",
        json={
            "action": {
                "action_type": "classify",
                "email_id": email_id,
                "priority": "urgent",
            }
        },
    )
    passed = step_response.status_code == 200
    print_check("POST /step", passed, f"status={step_response.status_code}")
    ok &= passed
    return ok


def check_inference_output() -> bool:
    result = subprocess.run(
        [sys.executable, "inference.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print_check("inference.py", False, "script exited non-zero")
        return False

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    patterns = [
        ("inference_start", any(re.match(r"^\[START\] task=\S+ env=\S+ model=.+$", line) for line in lines)),
        ("inference_step", any(re.match(r"^\[STEP\] step=\d+ action=.+ reward=\d+\.\d{2} done=(true|false) error=.*$", line) for line in lines)),
        ("inference_end", any(re.match(r"^\[END\] success=(true|false) steps=\d+ score=\d+\.\d{3} rewards=.*$", line) for line in lines)),
    ]

    ok = True
    for label, passed in patterns:
        print_check(label, passed)
        ok &= passed
    return ok


def check_docker_if_available() -> bool:
    docker_path = shutil.which("docker")
    if not docker_path:
        print_check("docker_build", True, "skipped locally because docker is not installed")
        return True

    return run_command("docker_build", ["docker", "build", "-t", "openenv-email-triage", "."])


def main() -> int:
    print("OpenEnv Email Triage pre-submit check\n")
    ok = True

    ok &= check_required_files()
    ok &= check_readme_frontmatter()
    ok &= check_http_endpoints()
    ok &= run_command("pytest", [sys.executable, "-m", "pytest", "-q"])
    ok &= run_command("openenv_validate", ["openenv", "validate"])
    ok &= run_command("heuristic_baseline", [sys.executable, "scripts/baseline.py", "--provider", "heuristic"])
    ok &= check_inference_output()
    ok &= check_docker_if_available()

    print()
    if ok:
        print("All critical pre-submit checks passed.")
        return 0

    print("One or more critical pre-submit checks failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
