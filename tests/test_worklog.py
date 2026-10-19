import os
import subprocess
from datetime import date

import pytest

from gtrack import worklog
from gtrack.gitsync import Commit
from gtrack.layout import WCOL, WORKLOG
from gtrack.tracker import Tracker

from .fake_sheets import FakeSheets


def entry(repo, subject, when, tasks=()):
    c = Commit("abcdef0123456789", when, "me", subject, [], "feat/x", list(tasks))
    return worklog.Entry(repo, "P", c)


def test_date_range():
    today = date(2026, 10, 22)  # 목요일
    assert worklog.date_range(today=today) == ("2026-10-22", "2026-10-22")
    assert worklog.date_range(on="2026-10-01", today=today) == ("2026-10-01", "2026-10-01")
    assert worklog.date_range(week=True, today=today) == ("2026-10-19", "2026-10-22")
    assert worklog.date_range(days=3, today=today) == ("2026-10-20", "2026-10-22")
    assert worklog.date_range(start="2026-10-10", today=today) == ("2026-10-10", "2026-10-22")
    with pytest.raises(ValueError):
        worklog.date_range(start="2026-10-10", end="2026-10-01", today=today)


def test_day_row_and_markdown():
    d = worklog.Day("2026-10-18", [entry("bx-store", "feat: 검색 (search)", "2026-10-18T10:00:00+09:00", ["T-018"]),
                                   entry("bx-api", "fix: 주문 API", "2026-10-18T11:30:00+09:00"),
                                   entry("bx-store", "fix: 정렬 T-018", "2026-10-18T15:00:00+09:00", ["T-018"])])
    row = d.row()
    assert row[:6] == ["2026-10-18", "일", 3, "bx-store, bx-api", "P", "T-018"]
    assert row[6].splitlines() == ["[bx-store] feat: 검색 (search) (T-018)", "[bx-api] fix: 주문 API",
                                   "[bx-store] fix: 정렬 T-018 (T-018)"]
    md = worklog.to_markdown([d])
    assert md.startswith("## 2026-10-18 (일) — 커밋 3건")
    assert md.index("**bx-store**") < md.index("**bx-api**")
    assert "  - 15:00 fix: 정렬 T-018 `T-018` — feat/x abcdef01" in md
    assert worklog.to_markdown([]) == ""


def test_write_worklog_upserts_keeps_memo_and_sorts():
    t = Tracker.create_worklog(FakeSheets())
    rows = lambda: t.service.sheets[WORKLOG]["rows"]
    assert rows()[0][0] == "날짜"
    t.write_worklog([["2026-10-17", "토", 1, "a", "P", "", "x"], ["2026-10-18", "일", 1, "a", "P", "", "y"]])
    assert [r[0] for r in rows()[1:]] == ["2026-10-18", "2026-10-17"]      # 최신이 위
    t.service.set_cell(WORKLOG, 2, WCOL["memo"], "회의 2건")                 # 10-17 줄에 직접 적은 메모
    out = t.write_worklog([["2026-10-17", "토", 2, "a", "P", "", "x\nz"], ["2026-10-19", "월", 1, "b", "P", "", "w"]])
    assert out == {"updated": ["2026-10-17"], "added": ["2026-10-19"]}
    assert [r[0] for r in rows()[1:]] == ["2026-10-19", "2026-10-18", "2026-10-17"]
    assert rows()[3][WCOL["commits"]] == 2 and rows()[3][WCOL["memo"]] == "회의 2건"
    assert [i["date"] for i in t.list_worklog("2026-10-18")] == ["2026-10-18", "2026-10-19"]


def _git(repo, *args, when=None):
    env = {**os.environ, **({"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when} if when else {})}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "bx-store"
    r.mkdir()
    try:
        _git(r, "init", "-q", "-b", "main")
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("git 없음")
    _git(r, "config", "user.name", "me")
    _git(r, "config", "user.email", "me@example.com")
    _git(r, "commit", "-q", "--allow-empty", "-m", "feat: 검색 (search)", when="2026-10-17T10:00:00+09:00")
    _git(r, "checkout", "-q", "-b", "feat/cart")
    _git(r, "commit", "-q", "--allow-empty", "-m", "feat: 장바구니", when="2026-10-18T09:00:00+09:00")
    _git(r, "-c", "user.name=other", "-c", "user.email=other@example.com", "commit", "-q", "--allow-empty",
         "-m", "fix: 남의 커밋", when="2026-10-18T10:00:00+09:00")
    _git(r, "checkout", "-q", "main")
    _git(r, "cherry-pick", "--allow-empty", "feat/cart~1", when="2026-10-18T11:00:00+09:00")
    return r


def test_collect_reads_my_commits_on_all_branches(repo):
    links = {"k": {"path": str(repo), "project": "P", "scopes": {"search": "T-018"}}}
    days = worklog.collect(links, "2026-10-17", "2026-10-18")
    assert [d.day for d in days] == ["2026-10-17", "2026-10-18"]
    assert [e.commit.subject for e in days[1].entries] == ["feat: 장바구니"]        # 다른 사람 커밋 제외
    assert sorted(days[1].entries[0].branches) == ["feat/cart", "main"]            # cherry-pick 은 한 줄로
    assert days[1].entries[0].repo == "bx-store"
    assert days[0].entries[0].commit.tasks == ["T-018"]
    assert [d.day for d in worklog.collect(links, "2026-10-18", "2026-10-18")] == ["2026-10-18"]
    assert len(worklog.collect(links, "2026-10-18", "2026-10-18", author="other")[0].entries) == 1
    assert worklog.collect({"x": {"path": str(repo / "없음")}}, "2026-10-17", "2026-10-18") == []
