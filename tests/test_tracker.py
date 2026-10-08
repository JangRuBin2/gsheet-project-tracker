from datetime import date

import pytest

from gtrack.layout import COL, DASHBOARD, RAID, RCOL
from gtrack.tracker import Tracker, TrackerError

from .fake_sheets import FakeSheets

TODAY = date(2026, 10, 8)


@pytest.fixture
def tracker():
    return Tracker.create(FakeSheets(), "테스트", today=TODAY)


def rows(tracker, sheet):
    return tracker.service.sheets[sheet]["rows"]


def test_create_builds_dashboard_and_raid(tracker):
    assert rows(tracker, DASHBOARD)[0][0] == "프로젝트"
    assert rows(tracker, RAID)[0][0] == "ID"
    assert tracker.url.endswith("/SHEET123/edit")


def test_ensure_base_sheets_adds_missing(tracker):
    tracker.service.sheets.pop(RAID)
    assert tracker.ensure_base_sheets() == [RAID]
    assert tracker.ensure_base_sheets() == []


def test_add_project_creates_sheet_and_dashboard_row(tracker):
    p = tracker.add_project("웹 개편", owner="홍길동", start="2026-10-01", end="2026-12-31")
    assert tracker.service.sheets["웹 개편"]["id"] == p["sheet_id"]
    assert rows(tracker, DASHBOARD)[1][:4] == ["웹 개편", "홍길동", "2026-10-01", "2026-12-31"]


def test_add_project_defaults_and_errors(tracker):
    p = tracker.add_project("A")
    assert (p["start"], p["end"]) == ("2026-10-08", "2026-12-30")
    with pytest.raises(TrackerError):
        tracker.add_project("A")
    with pytest.raises(TrackerError):
        tracker.add_project("B", start="2026-10-10", end="2026-10-01")


def test_add_tasks_assigns_ids_baseline_and_refs(tracker):
    tracker.add_project("A")
    t1 = tracker.add_task("A", "기획", phase="기획", start="2026-10-01", end="2026-10-05", priority="높음")
    t2 = tracker.add_task("A", "개발", progress="30", after="t-1")
    assert (t1["id"], t2["id"]) == ("T-001", "T-002")
    assert t2["status"] == "진행중" and t2["after"] == "T-001"
    r = rows(tracker, "A")
    assert r[1][COL["baseline"]] == "2026-10-05" and r[1][COL["priority"]] == "높음"
    with pytest.raises(TrackerError):
        tracker.add_task("A", "x", after="T-099")
    with pytest.raises(ValueError):
        tracker.add_task("A", "x", priority="급함")


def test_add_tasks_bulk(tracker):
    tracker.add_project("A")
    tracker.add_task("A", "기존")
    out = tracker.add_tasks("A", [
        {"name": "설계", "phase": "설계", "start": "2026-10-01", "end": "2026-10-03"},
        {"name": "구현", "after": "T-002", "progress": "100"},
    ])
    assert [t["id"] for t in out] == ["T-002", "T-003"]
    r = rows(tracker, "A")
    assert r[3][COL["status"]] == "완료" and r[3][COL["done_date"]] == "2026-10-08"
    assert f"H3" in r[2][COL["duration"]]


def test_update_task_progress_status_and_done_date(tracker):
    tracker.add_project("A")
    tracker.add_task("A", "기획")
    t = tracker.update_task("A", "T-001", progress="100")
    assert t["status"] == "완료" and t["progress"] == "100%"
    r = rows(tracker, "A")[1]
    assert r[COL["progress"]] == 1.0 and r[COL["done_date"]] == "2026-10-08"
    tracker.update_task("A", "T-001", progress="50")
    r = rows(tracker, "A")[1]
    assert r[COL["status"]] == "진행중" and r[COL["done_date"]] == ""


def test_update_task_keeps_baseline_when_end_moves(tracker):
    tracker.add_project("A")
    tracker.add_task("A", "기획", end="2026-10-10")
    tracker.add_task("A", "개발")
    tracker.update_task("A", "T-001", end="2026-10-20")
    tracker.update_task("A", "T-002", end="2026-10-30")
    r = rows(tracker, "A")
    assert (r[1][COL["end"]], r[1][COL["baseline"]]) == ("2026-10-20", "2026-10-10")
    assert r[2][COL["baseline"]] == "2026-10-30"  # 기준이 없던 작업은 처음 정한 종료일이 기준


def test_update_task_status_done_fills_progress(tracker):
    tracker.add_project("A")
    tracker.add_task("A", "기획")
    tracker.update_task("A", "T-001", status="완료")
    assert rows(tracker, "A")[1][COL["progress"]] == 1


def test_update_task_errors(tracker):
    tracker.add_project("A")
    tracker.add_task("A", "기획", start="2026-10-05")
    with pytest.raises(TrackerError):
        tracker.update_task("A", "T-999", progress="10")
    with pytest.raises(TrackerError):
        tracker.update_task("A", "T-001")
    with pytest.raises(TrackerError):
        tracker.update_task("A", "T-001", end="2026-10-01")
    with pytest.raises(TrackerError):
        tracker.update_task("A", "T-001", after="T-001")
    with pytest.raises(TrackerError):
        tracker.add_task("없는프로젝트", "x")
    for reserved in (DASHBOARD, RAID):
        with pytest.raises(TrackerError):
            tracker.add_task(reserved, "x")


def test_raid_add_list_update(tracker):
    tracker.add_project("A")
    tracker.add_project("B")
    tracker.add_task("A", "기획")
    r1 = tracker.add_raid("A", "리스크", "결제 연동 지연", impact="높음", related="T-1")
    r2 = tracker.add_raid("B", "이슈", "빌드 실패")
    assert (r1["id"], r2["id"], r1["related"], r1["status"]) == ("R-001", "R-002", "T-001", "열림")
    assert rows(tracker, RAID)[1][RCOL["created"]] == "2026-10-08"
    assert [i["id"] for i in tracker.list_raid("A")] == ["R-001"]
    tracker.update_raid("R-002", status="해결", action="캐시 삭제")
    assert [i["id"] for i in tracker.list_raid(open_only=True)] == ["R-001"]
    with pytest.raises(ValueError):
        tracker.add_raid("A", "걱정", "x")
    with pytest.raises(TrackerError):
        tracker.update_raid("R-999", status="종료")


def test_remove_project_deletes_sheet_and_dashboard_row(tracker):
    tracker.add_project("A")
    tracker.add_project("B")
    tracker.remove_project("A")
    assert "A" not in tracker.service.sheets
    assert [r[0] for r in rows(tracker, DASHBOARD)] == ["프로젝트", "B"]
    with pytest.raises(TrackerError):
        tracker.remove_project(RAID)


def test_list_projects_and_tasks(tracker):
    tracker.add_project("A", owner="PM")
    tracker.add_task("A", "기획", owner="김")
    assert [p["name"] for p in tracker.list_projects()] == ["A"]
    tasks = tracker.list_tasks("A")
    assert tasks[0]["id"] == "T-001" and tasks[0]["owner"] == "김" and tasks[0]["row"] == 2
