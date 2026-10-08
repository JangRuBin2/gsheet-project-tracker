import pytest

from gtrack.layout import DASHBOARD
from gtrack.tracker import Tracker, TrackerError

from .fake_sheets import FakeSheets


@pytest.fixture
def tracker():
    return Tracker.create(FakeSheets(), "테스트")


def test_create_builds_dashboard(tracker):
    assert DASHBOARD in tracker.service.sheets
    assert tracker.service.sheets[DASHBOARD]["rows"][0][0] == "프로젝트"
    assert tracker.url.endswith("/SHEET123/edit")


def test_add_project_creates_sheet_and_dashboard_row(tracker):
    p = tracker.add_project("웹 개편", owner="홍길동", start="2026-10-01", end="2026-12-31")
    fake = tracker.service
    assert fake.sheets["웹 개편"]["id"] == p["sheet_id"]
    row = fake.sheets[DASHBOARD]["rows"][1]
    assert row[:4] == ["웹 개편", "홍길동", "2026-10-01", "2026-12-31"]


def test_add_project_duplicate_and_bad_dates(tracker):
    tracker.add_project("A")
    with pytest.raises(TrackerError):
        tracker.add_project("A")
    with pytest.raises(TrackerError):
        tracker.add_project("B", start="2026-10-10", end="2026-10-01")


def test_add_tasks_assigns_sequential_ids_and_rows(tracker):
    tracker.add_project("A")
    t1 = tracker.add_task("A", "기획", start="2026-10-01", end="2026-10-05")
    t2 = tracker.add_task("A", "개발", progress="30")
    assert (t1["id"], t2["id"]) == ("T-001", "T-002")
    assert t2["status"] == "진행중"
    rows = tracker.service.sheets["A"]["rows"]
    assert rows[1][0] == "T-001" and rows[2][0] == "T-002"
    assert "D3" in rows[2][5]


def test_update_task_progress_sets_status(tracker):
    tracker.add_project("A")
    tracker.add_task("A", "기획")
    t = tracker.update_task("A", "T-001", progress="100")
    assert t["status"] == "완료" and t["progress"] == "100%"
    row = tracker.service.sheets["A"]["rows"][1]
    assert row[6] == 1.0 and row[7] == "완료"


def test_update_task_status_done_fills_progress(tracker):
    tracker.add_project("A")
    tracker.add_task("A", "기획")
    tracker.update_task("A", "T-001", status="완료")
    assert tracker.service.sheets["A"]["rows"][1][6] == 1


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
        tracker.add_task("없는프로젝트", "x")
    with pytest.raises(TrackerError):
        tracker.add_task(DASHBOARD, "x")


def test_remove_project_deletes_sheet_and_dashboard_row(tracker):
    tracker.add_project("A")
    tracker.add_project("B")
    tracker.remove_project("A")
    assert "A" not in tracker.service.sheets
    assert [r[0] for r in tracker.service.sheets[DASHBOARD]["rows"]] == ["프로젝트", "B"]


def test_list_projects_and_tasks(tracker):
    tracker.add_project("A", owner="PM")
    tracker.add_task("A", "기획", owner="김")
    assert [p["name"] for p in tracker.list_projects()] == ["A"]
    tasks = tracker.list_tasks("A")
    assert tasks[0]["id"] == "T-001" and tasks[0]["owner"] == "김" and tasks[0]["row"] == 2
