"""프로젝트별 스프레드시트 파일: 생성·분리·파일 찾기"""
import json

import pytest

from gtrack import cli
from gtrack.layout import COMMIT_LOG, DASHBOARD, RAID
from gtrack.tracker import Tracker, TrackerError

from .fake_sheets import FakeDrive


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "CONFIG_FILE", tmp_path / ".gtrack.json")
    monkeypatch.delenv("GTRACK_SPREADSHEET_ID", raising=False)
    drive = FakeDrive()

    def run(*argv):
        cli.run(cli.build_parser().parse_args(list(argv)), lambda interactive=True: drive)

    return drive, run


def config():
    return json.loads(cli.CONFIG_FILE.read_text(encoding="utf-8"))


def rows(drive, sid, sheet):
    return drive.files[sid].sheets[sheet]["rows"]


def test_project_add_creates_file_per_project(env, capsys):
    drive, run = env
    run("project", "add", "알파", "--start", "2026-10-01")
    run("project", "add", "베타", "--start", "2026-10-01")
    files = config()["projects"]
    assert files == {"알파": "FILE1", "베타": "FILE2"}
    assert "알파" in drive.files["FILE1"].sheets and "베타" not in drive.files["FILE1"].sheets

    run("task", "add", "베타", "설계")
    run("raid", "add", "베타", "리스크", "일정 지연")
    assert rows(drive, "FILE2", "베타")[1][2] == "설계"
    assert rows(drive, "FILE2", RAID)[1][:2] == ["R-001", "베타"]

    capsys.readouterr()
    run("project", "list")
    out = capsys.readouterr().out
    assert "알파" in out and "베타" in out


def test_project_add_rejects_duplicate_and_bad_date_before_creating_file(env):
    drive, run = env
    run("project", "add", "알파")
    with pytest.raises(TrackerError):
        run("project", "add", "알파")
    with pytest.raises(ValueError):
        run("project", "add", "감마", "--start", "10/01")
    assert list(drive.files) == ["FILE1"]


def test_split_copies_project_out_of_shared_file(env, capsys):
    drive, run = env
    shared = Tracker.create(drive, "공용")
    cli._save_config({"spreadsheet_id": shared.spreadsheet_id})
    for name in ("알파", "베타"):
        shared.add_project(name, start="2026-10-01")
        shared.add_task(name, f"{name} 작업")
        shared.add_raid(name, "이슈", f"{name} 이슈")
    shared._write_rows(COMMIT_LOG, 2, [["2026-10-12 10:00", "알파", "main", "aaa", "me", "feat", "", ""],
                                       ["2026-10-12 11:00", "베타", "main", "bbb", "me", "fix", "", ""]], "RAW")

    run("project", "split", "베타")
    new = config()["projects"]["베타"]
    assert new != shared.spreadsheet_id
    assert rows(drive, new, "베타")[1][2] == "베타 작업"
    assert rows(drive, new, DASHBOARD)[1][0] == "베타"
    assert [r[:2] for r in rows(drive, new, RAID)[1:]] == [["R-002", "베타"]]
    assert [r[3] for r in rows(drive, new, COMMIT_LOG)[1:]] == ["bbb"]
    assert "베타" in drive.files[shared.spreadsheet_id].sheets  # 원본은 남는다

    # 이후 명령은 새 파일로 간다. 목록에는 한 번만 나온다.
    run("task", "add", "베타", "새 작업")
    assert rows(drive, new, "베타")[2][2] == "새 작업"
    assert len(rows(drive, shared.spreadsheet_id, "베타")) == 2
    capsys.readouterr()
    run("project", "list")
    names = [line.split()[0] for line in capsys.readouterr().out.splitlines()[2:]]
    assert names == ["알파", "베타"]

    with pytest.raises(TrackerError):
        run("project", "split", "베타")


def test_raid_update_finds_file_or_asks_for_project(env):
    drive, run = env
    run("project", "add", "알파")
    run("project", "add", "베타")
    run("raid", "add", "알파", "리스크", "A")
    with pytest.raises(TrackerError):
        run("raid", "update", "R-002", "--status", "해결")
    run("raid", "update", "R-001", "--status", "해결")
    assert rows(drive, "FILE1", RAID)[1][7] == "해결"

    run("raid", "add", "베타", "리스크", "B")
    with pytest.raises(TrackerError, match="--project"):
        run("raid", "update", "R-001", "--status", "종료")
    run("raid", "update", "R-001", "--project", "베타", "--status", "종료")
    assert rows(drive, "FILE2", RAID)[1][7] == "종료"
    assert rows(drive, "FILE1", RAID)[1][7] == "해결"


def test_link_registers_existing_file(env):
    drive, run = env
    other = Tracker.create(drive, "남이 만든 파일")
    other.add_project("감마")
    with pytest.raises(TrackerError):
        run("project", "link", "없는이름", other.spreadsheet_id)
    run("project", "link", "감마", other.spreadsheet_id)
    assert config()["projects"] == {"감마": other.spreadsheet_id}
    run("task", "add", "감마", "작업")
    assert rows(drive, other.spreadsheet_id, "감마")[1][2] == "작업"


def test_remove_unregisters_project_file(env):
    drive, run = env
    run("project", "add", "알파")
    run("project", "remove", "알파", "--yes")
    assert config()["projects"] == {}
