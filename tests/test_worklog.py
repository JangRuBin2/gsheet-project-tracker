"""git 커밋으로 일일 업무일지 작성"""
import json
import os
import subprocess
from datetime import date

import pytest

from gtrack import cli, worklog


def _git(repo, *args, when=None):
    env = {**os.environ}
    if when:
        env.update(GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def make_repo(path, email="me@example.com"):
    path.mkdir(parents=True)
    try:
        _git(path, "init", "-q", "-b", "main")
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("git 없음")
    _git(path, "config", "user.name", "me")
    _git(path, "config", "user.email", email)
    return path


def commit(repo, name, msg, when, email=None):
    (repo / name).parent.mkdir(parents=True, exist_ok=True)
    (repo / name).write_text(msg, encoding="utf-8")
    _git(repo, "add", ".")
    args = ["-c", f"user.email={email}"] if email else []
    _git(repo, *args, "commit", "-q", "-m", msg, when=when)


@pytest.fixture
def work(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "CONFIG_FILE", tmp_path / ".gtrack.json")
    monkeypatch.setattr(cli, "HOME", tmp_path)
    root = tmp_path / "work"
    api = make_repo(root / "bx-api")
    web = make_repo(root / "group" / "BX-web")
    make_repo(root / "other-app")
    commit(api, "src/search/a.py", "feat(search): 검색 필터 T-018", "2026-10-19T09:10:00+09:00")
    commit(api, "src/b.py", "fix: 로그인 오류", "2026-10-19T14:30:00+09:00")
    commit(api, "src/c.py", "남의 커밋", "2026-10-19T15:00:00+09:00", email="other@example.com")
    commit(api, "src/d.py", "docs: 어제 정리", "2026-10-18T18:00:00+09:00")
    _git(api, "checkout", "-q", "-b", "feat/cart")
    commit(api, "src/cart.py", "feat: 장바구니", "2026-10-19T16:00:00+09:00")
    _git(api, "checkout", "-q", "main")
    commit(web, "page.tsx", "작업 화면 수정", "2026-10-19T11:00:00+09:00")
    return root


def run(*argv):
    cli.run(cli.build_parser().parse_args(list(argv)), lambda interactive=True: None)


def test_find_repos_by_name_match(work):
    found = worklog.find_repos([{"path": str(work), "match": "bx"}])
    assert sorted(p.name for p in found) == ["BX-web", "bx-api"]
    assert [p.name for p in worklog.find_repos([{"path": str(work / "other-app")}])] == ["other-app"]


def test_read_commits_own_author_all_branches(work):
    cs = worklog.read_commits(work / "bx-api", date(2026, 10, 19), date(2026, 10, 19), "me@example.com")
    assert [c.subject for c in cs] == ["feat(search): 검색 필터 T-018", "fix: 로그인 오류", "feat: 장바구니"]
    assert cs[-1].branch == "feat/cart"


def test_write_and_show(work, tmp_path, capsys):
    run("worklog", "add", str(work), "--match", "bx")
    run("worklog", "write", "--date", "2026-10-19")
    path = tmp_path / "worklog" / "2026-10" / "2026-10-19.md"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# 업무일지 2026-10-19 (월)")
    assert "저장소 2곳 · 커밋 4건" in text and "관련 작업 T-018" in text
    assert "### 기능 개발\n\n- 09:10 검색 필터 T-018 `(search)` [T-018]" in text
    assert "### 버그 수정" in text and "### 기타" in text and "남의 커밋" not in text
    assert text.index("## bx-api") < text.index("## BX-web")  # 저장소 이름순 (대소문자 무시)

    # 메모는 다시 작성해도 남는다
    path.write_text(text + "내일: 결제 연동\n", encoding="utf-8")
    run("worklog", "write", "--date", "2026-10-19")
    assert path.read_text(encoding="utf-8").endswith("## 메모\n" + worklog.MEMO_HINT + "\n\n내일: 결제 연동\n")

    capsys.readouterr()
    run("worklog", "show", "--date", "2026-10-19", "--week")
    out = capsys.readouterr().out
    assert "# 업무일지 2026-10-19" in out and "# 업무일지 2026-10-18" not in out


def test_range_skips_empty_days(work, tmp_path, capsys):
    run("worklog", "add", str(work / "bx-api"))
    run("worklog", "write", "--from", "2026-10-17", "--to", "2026-10-19")
    files = sorted(p.name for p in (tmp_path / "worklog" / "2026-10").iterdir())
    assert files == ["2026-10-18.md", "2026-10-19.md"]


def test_catch_up_records_last_run(work, tmp_path):
    run("worklog", "add", str(work), "--match", "bx")
    run("worklog", "write", "--catch-up", "--quiet")
    cfg = json.loads(cli.CONFIG_FILE.read_text(encoding="utf-8"))
    assert cfg["worklog"]["last"] == date.today().isoformat()
    assert (tmp_path / "worklog" / "worklog.log").exists()


def test_add_rejects_non_repo_without_match(work):
    with pytest.raises(cli.TrackerError):
        run("worklog", "add", str(work))


def test_linked_repo_shows_project_and_task_rules(work, tmp_path):
    from gtrack import gitsync

    cli._save_config({"git_sync": {gitsync.normalize_repo(str(work / "bx-api")): {
        "path": str(work / "bx-api"), "project": "BX 리뉴얼", "scopes": {}, "paths": {"src/cart.py": "T-020"}}}})
    run("worklog", "add", str(work / "bx-api"))
    run("worklog", "write", "--date", "2026-10-19")
    text = (tmp_path / "worklog" / "2026-10" / "2026-10-19.md").read_text(encoding="utf-8")
    assert "프로젝트: BX 리뉴얼" in text and "장바구니 [T-020]" in text
