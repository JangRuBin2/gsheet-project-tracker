"""비밀값이 git 에 올라가지 않는지 검사한다."""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SECRET_FILES = ["credentials.json", "client_secret_123.json", "token.json", ".gtrack.json"]
SECRET_PATTERNS = [
    re.compile(r"GOCSPX-[\w-]{10,}"),                   # OAuth client secret
    re.compile(r"1//0[\w-]{20,}"),                      # refresh token
    re.compile(r"ya29\.[\w-]{20,}"),                    # access token
    re.compile("-----BEGIN " + "PRIVATE KEY-----"),      # 서비스 계정 키 (이 파일 자체가 걸리지 않게 나눠 씀)
    re.compile(r'"(client_secret|refresh_token|private_key)"\s*:\s*"[^"]{8,}"'),
]


def _git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("git 저장소가 아님")


@pytest.mark.parametrize("name", SECRET_FILES)
def test_secret_files_are_ignored(name):
    assert _git("check-ignore", "-q", "--no-index", name).returncode == 0


def test_no_secrets_in_committable_files():
    # 추적 중인 파일 + .gitignore 에 걸리지 않는 새 파일 (= 커밋될 수 있는 모든 파일)
    files = set(_git("ls-files", "--cached", "--others", "--exclude-standard").stdout.splitlines())
    leaks = []
    for f in sorted(files):
        path = ROOT / f
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        leaks += [f"{f}: {p.pattern}" for p in SECRET_PATTERNS if p.search(text)]
    assert not leaks, f"비밀값으로 보이는 내용이 git 에 포함됨: {leaks}"
