"""git 커밋으로 일일 업무일지(Markdown)를 자동으로 만든다.

대상 저장소 (.gtrack.json 의 worklog.sources):
  {"path": "D:/work/bx-api"}               저장소 하나
  {"path": "D:/work", "match": "bx"}       폴더 아래(2단계까지) 이름에 bx 가 들어간 저장소 모두. 실행할 때마다 다시 찾는다.
작성자는 worklog.author, 없으면 각 저장소의 git config user.email 로 거른다.
일지는 worklog.dir (기본: 설치 폴더/worklog) 아래 YYYY-MM/YYYY-MM-DD.md 로 저장된다.
'## 메모' 아래에 직접 적은 내용은 일지를 다시 만들어도 그대로 남는다.
자세한 내용은 skill/gtrack/references/WORKLOG.md 참고.
"""
from __future__ import annotations

import re
import subprocess
from datetime import date, timedelta
from pathlib import Path

from .gitsync import Commit, commit_type, match_tasks

MEMO_HEADING = "## 메모"
MEMO_HINT = "<!-- 이 아래에 적은 내용은 업무일지를 다시 만들어도 그대로 남습니다. -->"
WEEKDAYS = "월화수목금토일"
TYPE_LABELS = {
    "feat": "기능 개발", "fix": "버그 수정", "perf": "성능 개선", "refactor": "리팩터링", "test": "테스트",
    "docs": "문서", "style": "스타일", "build": "빌드·설정", "ci": "빌드·설정", "chore": "빌드·설정",
}
LABEL_ORDER = list(dict.fromkeys(TYPE_LABELS.values())) + ["기타"]
_PREFIX = re.compile(r"\s*[A-Za-z]+(?:\(([^)]*)\))?!?:\s*")
SCAN_SKIP = {"node_modules", ".venv", "venv", "__pycache__", ".git"}


def is_repo(path: Path) -> bool:
    return (path / ".git").exists()


def find_repos(sources: list[dict], depth: int = 2) -> list[Path]:
    """sources 의 저장소를 찾는다. match 가 있으면 폴더 아래에서 이름에 match 가 들어간 저장소를 모두 찾는다."""
    found: dict[str, Path] = {}

    def scan(d: Path, match: str, level: int):
        try:
            children = sorted(p for p in d.iterdir() if p.is_dir() and p.name not in SCAN_SKIP)
        except OSError:
            return
        for p in children:
            if is_repo(p):
                if match in p.name.lower():
                    found.setdefault(str(p.resolve()), p)
            elif level < depth:
                scan(p, match, level + 1)

    for s in sources:
        root = Path(s["path"]).expanduser()
        match = (s.get("match") or "").lower()
        if match:
            if is_repo(root) and match in root.name.lower():
                found.setdefault(str(root.resolve()), root)
            scan(root, match, 1)
        elif is_repo(root):
            found.setdefault(str(root.resolve()), root)
    return list(found.values())


def git_email(repo: Path) -> str:
    return subprocess.run(["git", "-C", str(repo), "config", "user.email"], capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


def read_commits(repo: Path, start: date, end: date, author: str) -> list[Commit]:
    """start~end(포함) 사이에 author 가 작성한 커밋. 모든 로컬 브랜치를 보고, 오래된 순으로 돌려준다.
    날짜는 작성 시각(author date) 기준이다."""
    fmt = "%x1e%H%x1f%aI%x1f%an%x1f%S%x1f%s"
    # git 의 --since/--until 은 커밋 시각 기준이라 앞뒤로 넉넉히 읽고 작성 날짜로 다시 거른다.
    args = ["git", "-C", str(repo), "log", "--branches", "--source", "--no-merges", "--name-only",
            f"--format={fmt}", f"--since={(start - timedelta(days=3)).isoformat()}T00:00:00",
            f"--author={author}"]
    out = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", check=True).stdout
    commits = []
    for rec in out.split("\x1e"):
        if not rec.strip():
            continue
        head, _, rest = rec.partition("\n")
        h, when, name, source, subject = head.split("\x1f", 4)
        if not start.isoformat() <= when[:10] <= end.isoformat():
            continue
        files = [f.strip() for f in rest.splitlines() if f.strip()]
        commits.append(Commit(h, when, name, subject, files, source.removeprefix("refs/heads/")))
    return sorted(commits, key=lambda c: c.date)


def collect(repos: list[dict], start: date, end: date) -> dict[str, list[dict]]:
    """repos: [{"path", "name", "author", "project", "rule"}] → {날짜: [{"repo": ..., "commits": [...]}]}"""
    days: dict[str, list[dict]] = {}
    for r in repos:
        commits = [match_tasks(c, r.get("rule") or {}) for c in read_commits(Path(r["path"]), start, end, r["author"])]
        by_day: dict[str, list[Commit]] = {}
        for c in commits:
            by_day.setdefault(c.day, []).append(c)
        for day, cs in by_day.items():
            days.setdefault(day, []).append({**r, "commits": cs})
    return days


def _title(subject: str) -> tuple[str, str]:
    """'feat(search): 검색 필터' → ('검색 필터', 'search')"""
    m = _PREFIX.match(subject)
    if not m or not commit_type(subject):
        return subject, ""
    return subject[m.end():] or subject, m.group(1) or ""


def render(day: str, entries: list[dict], memo: str = "") -> str:
    d = date.fromisoformat(day)
    commits = [c for e in entries for c in e["commits"]]
    files = {(e["name"], f) for e in entries for c in e["commits"] for f in c.files}
    tasks = list(dict.fromkeys(t for c in commits for t in c.tasks))
    summary = f"저장소 {len(entries)}곳 · 커밋 {len(commits)}건 · 변경 파일 {len(files)}개"
    if tasks:
        summary += f" · 관련 작업 {', '.join(tasks)}"
    lines = [f"# 업무일지 {day} ({WEEKDAYS[d.weekday()]})", "", f"> {summary}", ""]

    for e in sorted(entries, key=lambda e: e["name"].lower()):
        cs = e["commits"]
        info = [f"프로젝트: {e['project']}"] if e.get("project") else []
        info.append(f"브랜치: {', '.join(dict.fromkeys(c.branch for c in cs if c.branch))}")
        info.append(f"{cs[0].date[11:16]} ~ {cs[-1].date[11:16]}")
        lines += [f"## {e['name']}", "", " · ".join(info), ""]
        groups: dict[str, list[Commit]] = {}
        for c in cs:
            groups.setdefault(TYPE_LABELS.get(commit_type(c.subject), "기타"), []).append(c)
        for label in sorted(groups, key=LABEL_ORDER.index):
            lines += [f"### {label}", ""]
            for c in groups[label]:
                text, scope = _title(c.subject)
                extra = (f" `({scope})`" if scope else "") + (f" [{', '.join(c.tasks)}]" if c.tasks else "")
                lines.append(f"- {c.date[11:16]} {text}{extra} — `{c.short}` (파일 {len(c.files)}개)")
            lines.append("")
    lines += [MEMO_HEADING, MEMO_HINT, ""]
    body = "\n".join(lines)
    return body + ("\n" + memo.strip("\n") + "\n" if memo.strip() else "")


def read_memo(path: Path) -> str:
    """기존 일지의 '## 메모' 아래 내용 (안내 주석 제외)."""
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    _, found, memo = text.partition(f"\n{MEMO_HEADING}\n")
    return memo.replace(MEMO_HINT, "", 1).strip("\n") if found else ""


def log_path(base: Path, day: str) -> Path:
    return base / day[:7] / f"{day}.md"


def write_day(base: Path, day: str, entries: list[dict]) -> Path | None:
    """그날 일지를 (다시) 쓴다. 커밋이 없으면 새 파일을 만들지 않는다 (메모가 있는 기존 파일은 그대로 둔다)."""
    path = log_path(base, day)
    if not entries:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(day, entries, read_memo(path)), encoding="utf-8", newline="\n")
    return path


def day_range(start: date, end: date) -> list[str]:
    return [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]
