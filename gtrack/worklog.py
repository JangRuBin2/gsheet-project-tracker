"""연결된 git 저장소의 내 커밋을 날짜별로 모아 일일 업무일지를 만든다.

대상 저장소는 .gtrack.json 의 git_sync (gtrack git link 로 연결한 저장소) 전부다.
작성자는 저장소마다 `git config user.email` 로 거른다 (.gtrack.json 의 worklog.author 로 바꿀 수 있다).
모든 브랜치의 커밋을 읽으므로 아직 병합하지 않은 작업 브랜치 커밋도 들어간다.
자세한 내용은 skill/gtrack/references/WORKLOG.md 참고.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from . import gitsync

WEEKDAYS = "월화수목금토일"


@dataclass
class Entry:
    repo: str      # 저장소 폴더 이름 (예: bx-store)
    project: str
    commit: gitsync.Commit
    branches: list[str] = field(default_factory=list)  # cherry-pick 으로 같은 커밋이 여러 브랜치에 있을 때

    def __post_init__(self):
        self.branches = self.branches or [self.commit.branch]


@dataclass
class Day:
    day: str
    entries: list[Entry] = field(default_factory=list)

    @property
    def weekday(self) -> str:
        return WEEKDAYS[date.fromisoformat(self.day).weekday()]

    def row(self) -> list:
        """업무일지 시트의 날짜~작업 내용 칸 (메모 칸 제외)"""
        uniq = lambda xs: ", ".join(dict.fromkeys(x for x in xs if x))
        tasks = uniq(t for e in self.entries for t in e.commit.tasks)
        work = "\n".join(_line(e) for e in self.entries)
        return [self.day, self.weekday, len(self.entries), uniq(e.repo for e in self.entries),
                uniq(e.project for e in self.entries), tasks, work]


def _line(e: Entry) -> str:
    c = e.commit
    tasks = f" ({', '.join(c.tasks)})" if c.tasks else ""
    return f"[{e.repo}] {c.subject}{tasks}"


def date_range(on: str | None = None, start: str | None = None, end: str | None = None,
               days: int | None = None, week: bool = False, today: date | None = None) -> tuple[str, str]:
    """CLI 범위 옵션 → (시작일, 종료일). 아무것도 없으면 오늘 하루."""
    today = today or date.today()
    if on:
        return date.fromisoformat(on).isoformat(), date.fromisoformat(on).isoformat()
    if week:
        monday = today - timedelta(days=today.weekday())
        return monday.isoformat(), today.isoformat()
    if days:
        return (today - timedelta(days=days - 1)).isoformat(), today.isoformat()
    s = date.fromisoformat(start) if start else today
    e = date.fromisoformat(end) if end else today
    if e < s:
        raise ValueError("종료일이 시작일보다 빠릅니다.")
    return s.isoformat(), e.isoformat()


def _repo_author(repo: str) -> str:
    return subprocess.run(["git", "-C", repo, "config", "user.email"], capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


def collect(links: dict, start: str, end: str, author: str | None = None) -> list[Day]:
    """links: .gtrack.json 의 git_sync. 날짜 오래된 순, 하루 안에서는 시간 순."""
    entries: list[Entry] = []
    for key, rule in links.items():
        repo = rule.get("path", key)
        if not Path(repo).exists():
            continue
        who = author or _repo_author(repo) or None
        # git 의 --since/--until 은 커밋 일시 기준이라 하루 넉넉히 읽고 작성일로 다시 거른다.
        since = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
        until = (date.fromisoformat(end) + timedelta(days=1)).isoformat()
        for c in gitsync.read_commits(repo, since, limit=5000, until=until, author=who, all_refs=True):
            if start <= c.day <= end:
                entries.append(Entry(Path(repo).name, rule.get("project", ""), gitsync.match_tasks(c, rule)))
    entries.sort(key=lambda e: e.commit.date)
    days: dict[str, Day] = {}
    seen: dict[tuple, Entry] = {}
    for e in entries:
        # 같은 날 같은 저장소의 같은 메시지는 cherry-pick 으로 보고 한 줄로 합친다.
        key = (e.commit.day, e.repo, e.commit.subject)
        if key in seen:
            seen[key].branches = list(dict.fromkeys(seen[key].branches + e.branches))
            continue
        seen[key] = e
        days.setdefault(e.commit.day, Day(e.commit.day)).entries.append(e)
    return sorted(days.values(), key=lambda d: d.day)


def to_markdown(days: list[Day]) -> str:
    out = []
    for d in days:
        out.append(f"## {d.day} ({d.weekday}) — 커밋 {len(d.entries)}건")
        for repo in dict.fromkeys(e.repo for e in d.entries):
            items = [e for e in d.entries if e.repo == repo]
            out.append(f"- **{repo}** ({items[0].project})")
            for e in items:
                c = e.commit
                tasks = f" `{', '.join(c.tasks)}`" if c.tasks else ""
                out.append(f"  - {c.date[11:16]} {c.subject}{tasks} — {', '.join(e.branches)} {c.short}")
        out.append("")
    return "\n".join(out).rstrip() + "\n" if out else ""
