"""git 커밋을 프로젝트 작업에 연결해 시트를 갱신한다.

연결 규칙 (.gtrack.json 의 git_sync.<저장소 경로>):
  project : 대상 프로젝트(시트) 이름
  since   : 이 날짜 이후 커밋만 반영 (YYYY-MM-DD)
  paths   : {"glob 패턴": "T-018"}   변경 파일 경로가 패턴에 맞으면 그 작업과 연결
  scopes  : {"search": "T-018"}      커밋 제목 끝 "(scope)" 의 scope 가 같으면 연결
커밋 메시지에 T-018 처럼 ID 를 직접 쓰면 항상 연결되고,
"T-018 완료" / "closes T-018" / "done T-018" 이면 그 작업을 완료 처리한다.
자세한 내용은 skill/gtrack/references/GIT_SYNC.md 참고.
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

HOOK_MARK = "gtrack-sync"
HOOK_NAMES = ("post-commit", "pre-push")

_ID = r"[Tt]-0*(\d+)"
_DONE_BEFORE = re.compile(rf"(?:closes?|close|done|완료)\s*[:#]?\s*{_ID}", re.I)
_DONE_AFTER = re.compile(rf"{_ID}\s*[\]:)]?\s*(?:완료|done)", re.I)
_ANY_ID = re.compile(rf"(?<![A-Za-z0-9]){_ID}(?![0-9])")
_SCOPE = re.compile(r"\(([^()]+)\)\s*$")
_TYPE = re.compile(r"\s*([A-Za-z]+)(?:\(([^)]*)\))?!?:")
APPLY_TYPES = {"feat", "fix", "perf"}
MAX_INFERRED = 3


@dataclass
class Commit:
    hash: str
    date: str  # ISO 8601
    author: str
    subject: str
    files: list[str] = field(default_factory=list)
    branch: str = ""
    tasks: list[str] = field(default_factory=list)   # 연결된 작업 (로그용)
    apply: list[str] = field(default_factory=list)   # 상태·시작일을 반영할 작업
    done: set[str] = field(default_factory=set)      # 완료 처리할 작업

    @property
    def short(self) -> str:
        return self.hash[:8]

    @property
    def day(self) -> str:
        return self.date[:10]


def _tid(n: str) -> str:
    return f"T-{int(n):03d}"


def normalize_repo(path: str) -> str:
    return str(Path(path).resolve()).replace("\\", "/").rstrip("/").lower()


def commit_type(subject: str) -> str:
    m = _TYPE.match(subject)
    return m.group(1).lower() if m else ""


def match_tasks(commit: Commit, rule: dict) -> Commit:
    """규칙에 따라 commit.tasks / apply / done 을 채운다.

    - 메시지에 직접 쓴 T-ID: 항상 반영
    - scope·경로 규칙으로 찾은 작업: feat/fix/perf 커밋이고 연결 작업이 MAX_INFERRED 개 이하일 때만 반영
      (refactor·style·docs 나 여러 화면을 한꺼번에 건드린 정리 커밋은 로그에만 남긴다)
    """
    explicit = list(dict.fromkeys(_tid(m.group(1)) for m in _ANY_ID.finditer(commit.subject)))
    done = {_tid(m.group(1)) for p in (_DONE_BEFORE, _DONE_AFTER) for m in p.finditer(commit.subject)}

    inferred: list[str] = []
    scope_map = rule.get("scopes") or {}
    # scope 는 "fix(search): …" 와 "fix: … (search)" 두 형식 모두 인식
    scopes = [m.group(1) for m in (_SCOPE.search(commit.subject),) if m]
    scopes += [m.group(2) for m in (_TYPE.match(commit.subject),) if m and m.group(2)]
    for text in scopes:
        for scope in re.split(r"[,·]\s*", text):
            if scope.strip() in scope_map:
                inferred.append(scope_map[scope.strip()])
    for pattern, task in (rule.get("paths") or {}).items():
        if any(fnmatch(f, pattern) for f in commit.files):
            inferred.append(task)
    inferred = [t for t in dict.fromkeys(inferred) if t not in explicit]

    applies = commit_type(commit.subject) in APPLY_TYPES and len(inferred) <= MAX_INFERRED
    commit.tasks = explicit + inferred
    commit.apply = explicit + (inferred if applies else [])
    commit.done = done
    return commit


def read_commits(repo: str, since: str | None = None, limit: int = 200) -> list[Commit]:
    """HEAD 에서 도달 가능한 커밋을 오래된 순으로 돌려준다."""
    fmt = "%x1e%H%x1f%aI%x1f%an%x1f%s"
    args = ["git", "-C", repo, "log", f"-n{limit}", f"--format={fmt}", "--name-only", "--no-merges"]
    if since:
        args.append(f"--since={since}T00:00:00")
    out = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", check=True).stdout
    branch = subprocess.run(["git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True,
                            text=True, encoding="utf-8").stdout.strip()
    commits = []
    for rec in out.split("\x1e"):
        if not rec.strip():
            continue
        head, _, rest = rec.partition("\n")
        h, date, author, subject = head.split("\x1f", 3)
        files = [f.strip() for f in rest.splitlines() if f.strip()]
        commits.append(Commit(h, date, author, subject, files, branch))
    return list(reversed(commits))


@contextmanager
def file_lock(path: Path, timeout: float = 90, stale: float = 300):
    """post-commit 과 pre-push 가 동시에 돌 때 중복 기록을 막는 간단한 잠금."""
    deadline = time.time() + timeout
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if time.time() - path.stat().st_mtime > stale:
                path.unlink(missing_ok=True)
                continue
            if time.time() > deadline:
                raise TimeoutError(f"잠금 대기 시간 초과: {path}")
            time.sleep(1)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def git_dir(repo: str) -> Path:
    out = subprocess.run(["git", "-C", repo, "rev-parse", "--absolute-git-dir"], capture_output=True, text=True,
                         encoding="utf-8", check=True).stdout.strip()
    return Path(out)


def hooks_dir(repo: str) -> Path:
    custom = subprocess.run(["git", "-C", repo, "config", "--get", "core.hooksPath"], capture_output=True,
                            text=True, encoding="utf-8").stdout.strip()
    if custom:
        p = Path(custom)
        return p if p.is_absolute() else Path(repo) / p
    return git_dir(repo) / "hooks"


def hook_script(python: str, tracker_dir: str, repo: str) -> str:
    to_posix = lambda p: str(p).replace("\\", "/")
    return f"""#!/bin/sh
# {HOOK_MARK}: gsheet-project-tracker 가 설치한 hook. 커밋을 구글 시트 작업에 반영한다.
# 제거: python -m gtrack git unlink --repo "{to_posix(repo)}"  (또는 이 파일 삭제)
# 백그라운드로 실행되어 커밋/푸시를 막지 않는다. 결과는 .git/gtrack-sync.log 에 남는다.
LOG="$(git rev-parse --absolute-git-dir)/gtrack-sync.log"
(cd "{to_posix(tracker_dir)}" && PYTHONIOENCODING=utf-8 "{to_posix(python)}" -m gtrack git sync --repo "{to_posix(repo)}" --quiet >> "$LOG" 2>&1) </dev/null >/dev/null 2>&1 &
exit 0
"""


def install_hooks(repo: str, python: str, tracker_dir: str) -> list[str]:
    """hook 을 설치한다. 다른 도구가 만든 같은 이름의 hook 이 있으면 덮어쓰지 않고 오류."""
    d = hooks_dir(repo)
    d.mkdir(parents=True, exist_ok=True)
    installed = []
    for name in HOOK_NAMES:
        path = d / name
        if path.exists() and HOOK_MARK not in path.read_text(encoding="utf-8", errors="ignore"):
            raise RuntimeError(f"이미 다른 {name} hook 이 있습니다: {path} — 직접 합쳐 주세요.")
        path.write_text(hook_script(python, tracker_dir, repo), encoding="utf-8", newline="\n")
        try:
            path.chmod(0o755)
        except OSError:
            pass
        installed.append(str(path))
    return installed


def uninstall_hooks(repo: str) -> list[str]:
    removed = []
    for name in HOOK_NAMES:
        path = hooks_dir(repo) / name
        if path.exists() and HOOK_MARK in path.read_text(encoding="utf-8", errors="ignore"):
            path.unlink()
            removed.append(str(path))
    return removed
