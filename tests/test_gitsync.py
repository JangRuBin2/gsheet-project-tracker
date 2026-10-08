import subprocess
from datetime import date

import pytest

from gtrack import gitsync
from gtrack.gitsync import Commit, match_tasks
from gtrack.layout import COL, COMMIT_LOG
from gtrack.tracker import Tracker

from .fake_sheets import FakeSheets

RULE = {
    "paths": {"app/*/*/search/*": "T-002", "components/search/*": "T-002", "e2e/*": "T-003"},
    "scopes": {"search": "T-002", "main": "T-001"},
}


def c(subject, files=(), date_="2026-10-08T10:00:00+09:00", h="abcdef0123456789"):
    return Commit(h, date_, "dev", subject, list(files), "feat/x")


def test_match_by_path_scope_and_id():
    assert match_tasks(c("fix: 카드 (main)"), RULE).tasks == ["T-001"]
    assert match_tasks(c("feat: 화면", ["app/[domain]/[locale]/search/page.tsx"]), RULE).tasks == ["T-002"]
    m = match_tasks(c("feat: 검색 (search, main)", ["e2e/ui/search.spec.ts"]), RULE)
    assert m.tasks == ["T-002", "T-001", "T-003"]
    assert match_tasks(c("chore: T-7 정리"), RULE).tasks == ["T-007"]
    assert match_tasks(c("docs: 작업일지 (docs)", ["docs/logs/a.md"]), RULE).tasks == []


def test_done_markers():
    assert match_tasks(c("feat: 검색 마무리 T-002 완료"), RULE).done == {"T-002"}
    assert match_tasks(c("feat: closes T-2"), RULE).done == {"T-002"}
    assert match_tasks(c("feat: [T-002 done] 끝"), RULE).done == {"T-002"}
    assert match_tasks(c("feat: T-002 진행"), RULE).done == set()


def test_no_false_ids():
    assert match_tasks(c("build: Next.js 16 / UTF-8 / t1"), RULE).tasks == []


def test_apply_only_feat_fix_and_explicit():
    assert match_tasks(c("feat: 화면 (search)"), RULE).apply == ["T-002"]
    assert match_tasks(c("fix(search): 카드"), RULE).apply == ["T-002"]
    m = match_tasks(c("refactor: 정리 (search)"), RULE)
    assert m.tasks == ["T-002"] and m.apply == []
    assert match_tasks(c("docs: T-003 일지 (search)"), RULE).apply == ["T-003"]


def test_apply_skips_wide_commits():
    rule = {"paths": {f"p{i}/*": f"T-00{i}" for i in range(1, 6)}}
    wide = match_tasks(c("feat: 공통 수정", [f"p{i}/a.ts" for i in range(1, 5)]), rule)
    assert len(wide.tasks) == 4 and wide.apply == []
    narrow = match_tasks(c("feat: 수정", ["p1/a.ts", "p2/a.ts"]), rule)
    assert narrow.apply == ["T-001", "T-002"]


@pytest.fixture
def tracker():
    t = Tracker.create(FakeSheets(), "t", today=date(2026, 10, 8))
    t.add_project("P")
    t.add_tasks("P", [{"name": "메인", "status": "완료", "start": "2026-10-01", "end": "2026-10-01"},
                      {"name": "검색"}, {"name": "E2E", "status": "보류"}])
    return t


def test_sync_updates_tasks_and_logs_once(tracker):
    commits = [match_tasks(c("feat: 검색 (search)", h="1111111111"), RULE),
               match_tasks(c("fix: 메인 (main)", date_="2026-10-09T09:00:00+09:00", h="2222222222"), RULE),
               match_tasks(c("feat: e2e", ["e2e/a.spec.ts"], h="3333333333"), RULE),
               match_tasks(c("refactor: 정리 (search)", date_="2026-10-01T09:00:00+09:00", h="4444444444"), RULE)]
    out = tracker.sync_commits("P", commits)
    assert [r["commit"] for r in out] == ["11111111", "22222222", "33333333", "44444444"]
    rows = tracker.service.sheets["P"]["rows"]
    # 검색: 진행중 + 시작일은 refactor(10-01) 가 아닌 feat 커밋 날짜
    assert rows[2][COL["status"]] == "진행중" and rows[2][COL["start"]] == "2026-10-08"
    assert rows[1][COL["status"]] == "완료"                                               # 메인: 그대로
    assert rows[3][COL["status"]] == "보류" and rows[3][COL["start"]] == "2026-10-08"    # 보류는 상태 유지
    log = tracker.service.sheets[COMMIT_LOG]["rows"]
    assert len(log) == 5 and log[1][3] == "11111111" and "T-002 진행중" in log[1][7]
    assert log[4][6] == "T-002" and log[4][7] == ""                                      # refactor 는 기록만
    # 같은 커밋은 다시 반영하지 않는다
    assert tracker.sync_commits("P", commits) == []
    assert len(tracker.service.sheets[COMMIT_LOG]["rows"]) == 5


def test_sync_done_marker_and_unknown_task(tracker):
    out = tracker.sync_commits("P", [match_tasks(c("feat: 검색 끝 T-002 완료, T-099"), RULE)])
    assert out[0]["applied"] == ["T-002 완료", "T-002 시작일 2026-10-08", "T-099 없음"]
    row = tracker.service.sheets["P"]["rows"][2]
    assert row[COL["status"]] == "완료" and row[COL["progress"]] == 1


def test_dry_run_changes_nothing(tracker):
    out = tracker.sync_commits("P", [match_tasks(c("feat: (search)"), RULE)], dry_run=True)
    assert out[0]["applied"] == ["T-002 진행중", "T-002 시작일 2026-10-08"]
    assert tracker.service.sheets["P"]["rows"][2][COL["status"]] == "대기"


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    try:
        _git(tmp_path, "init", "-q")
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("git 없음")
    _git(tmp_path, "config", "user.name", "dev")
    _git(tmp_path, "config", "user.email", "dev@example.com")
    (tmp_path / "e2e").mkdir()
    (tmp_path / "e2e" / "a.spec.ts").write_text("x")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "test: e2e 추가 (e2e)")
    (tmp_path / "b.txt").write_text("y")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "chore: T-002 완료")
    return tmp_path


def test_read_commits_oldest_first_with_files(repo):
    commits = gitsync.read_commits(str(repo))
    assert [x.subject for x in commits] == ["test: e2e 추가 (e2e)", "chore: T-002 완료"]
    assert commits[0].files == ["e2e/a.spec.ts"] and commits[0].branch


def test_install_and_uninstall_hooks(repo):
    installed = gitsync.install_hooks(str(repo), "C:/py/python.exe", "C:/tracker")
    assert len(installed) == 2
    text = (repo / ".git" / "hooks" / "post-commit").read_text(encoding="utf-8")
    assert gitsync.HOOK_MARK in text and "git sync --repo" in text and text.rstrip().endswith("exit 0")
    assert "\r\n" not in text
    assert len(gitsync.install_hooks(str(repo), "C:/py/python.exe", "C:/tracker")) == 2  # 재설치 가능
    assert len(gitsync.uninstall_hooks(str(repo))) == 2


def test_install_refuses_foreign_hook(repo):
    (repo / ".git" / "hooks" / "pre-push").write_text("#!/bin/sh\necho mine\n")
    with pytest.raises(RuntimeError):
        gitsync.install_hooks(str(repo), "py", "C:/tracker")


def test_file_lock(tmp_path):
    p = tmp_path / "x.lock"
    with gitsync.file_lock(p):
        assert p.exists()
        with pytest.raises(TimeoutError):
            with gitsync.file_lock(p, timeout=0):
                pass
    assert not p.exists()
