import subprocess
import re
import sys


def test_inference_script_runs_and_emits_structured_tags():
    result = subprocess.run(
        [sys.executable, "inference.py"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert any(re.match(r"^\[START\] task=\S+ env=\S+ model=.+$", line) for line in lines)
    assert any(re.match(r"^\[STEP\] step=\d+ action=.+ reward=\d+\.\d{2} done=(true|false) error=.*$", line) for line in lines)
    assert any(re.match(r"^\[END\] success=(true|false) steps=\d+ score=\d+\.\d{3} rewards=.*$", line) for line in lines)
