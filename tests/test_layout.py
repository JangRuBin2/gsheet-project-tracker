from datetime import date

import pytest

from gtrack.layout import (
    COL, DASH_HEADERS, DASHBOARD, DCOL, RAID, RAID_HEADERS, TASK_HEADERS, TIMELINE_COL, col_letter, dashboard_row,
    derive_status, next_id, next_task_id, parse_date, parse_progress, parse_task_refs, project_sheet_requests,
    quote_sheet, raid_sheet_requests, task_row, to_serial, validate_project_name, week_starts,
)


def test_col_letter():
    assert [col_letter(i) for i in (0, 11, 25, 26, 27, 701, 702)] == ["A", "L", "Z", "AA", "AB", "ZZ", "AAA"]


def test_quote_sheet_escapes_quote():
    assert quote_sheet("A'B") == "'A''B'"


def test_to_serial():
    assert to_serial(date(1899, 12, 31)) == 1
    assert to_serial(date(2026, 1, 1)) == 46023


@pytest.mark.parametrize("bad", ["", "  ", "a/b", "x[1]", "a'b", DASHBOARD, RAID, "x" * 91])
def test_validate_project_name_rejects(bad):
    with pytest.raises(ValueError):
        validate_project_name(bad)


def test_parse_date():
    assert parse_date("2026-02-28") == date(2026, 2, 28)
    for bad in ("2026-02-30", "2026/02/01", "26-1-1", "x"):
        with pytest.raises(ValueError):
            parse_date(bad)


def test_parse_progress():
    assert parse_progress("50") == 0.5
    assert parse_progress("100%") == 1
    assert parse_progress(0) == 0
    for bad in ("-1", "101", "abc"):
        with pytest.raises(ValueError):
            parse_progress(bad)


def test_parse_task_refs():
    assert parse_task_refs("") == ""
    assert parse_task_refs("t-1, T-003 T3") == "T-001, T-003"
    with pytest.raises(ValueError):
        parse_task_refs("작업1")


def test_derive_status():
    assert derive_status(1.0, None, "진행중") == "완료"
    assert derive_status(0.3, None, "대기") == "진행중"
    assert derive_status(0.3, None, "완료") == "진행중"
    assert derive_status(0.3, None, "보류") == "보류"
    assert derive_status(0.3, None, "차단") == "차단"
    assert derive_status(None, None, "보류") == "보류"
    assert derive_status(0.3, "차단", "대기") == "차단"
    with pytest.raises(ValueError):
        derive_status(None, "없는상태", "대기")


def test_next_ids():
    assert next_task_id([]) == "T-001"
    assert next_task_id(["T-001", "T-009", "메모", ""]) == "T-010"
    assert next_id(["R-002", "T-010"], "R") == "R-003"


def test_week_starts_aligned_to_monday():
    weeks = week_starts(date(2026, 10, 8), date(2026, 10, 26))  # 목 ~ 월
    assert weeks == [date(2026, 10, 5), date(2026, 10, 12), date(2026, 10, 19), date(2026, 10, 26)]


def test_task_row_layout_and_formulas():
    row = task_row(7, {"id": "T-001", "name": "x", "end": "2026-10-10"})
    assert len(row) == len(TASK_HEADERS)
    assert row[COL["status"]] == "대기" and row[COL["priority"]] == "보통"
    assert row[COL["baseline"]] == "2026-10-10"  # 기준종료일 = 최초 종료일
    s, e = col_letter(COL["start"]), col_letter(COL["end"])
    assert f"{s}7" in row[COL["planned"]] and f"{e}7" in row[COL["planned"]]
    assert f"{e}7-{col_letter(COL['baseline'])}7" in row[COL["slip"]]
    assert row[COL["variance"]].startswith("=IF(ISNUMBER(L7)")


def test_dashboard_row_references_project_and_raid():
    row = dashboard_row(3, {"name": "웹 개편", "start": "2026-10-01", "end": "2026-12-31", "sheet_id": 42})
    assert len(row) == len(DASH_HEADERS)
    assert row[DCOL["tasks"]] == "=COUNTA('웹 개편'!A2:A)"
    assert "'RAID'!B2:B" in row[DCOL["raid"]]
    assert "#gid=42" in row[DCOL["link"]]
    assert "위험" in row[DCOL["health"]] and "N3" not in row[DCOL["health"]]


def test_project_sheet_requests_sizes_timeline():
    reqs = project_sheet_requests(5, "P", date(2026, 10, 5), date(2026, 11, 1))  # 4주
    grid = reqs[0]["addSheet"]["properties"]["gridProperties"]
    assert grid["columnCount"] == TIMELINE_COL + 4
    header = reqs[1]["updateCells"]["rows"][0]["values"]
    assert header[TIMELINE_COL]["userEnteredValue"] == {"numberValue": to_serial(date(2026, 10, 5))}


def test_raid_sheet_requests():
    reqs = raid_sheet_requests(9)
    assert reqs[0]["addSheet"]["properties"]["title"] == RAID
    header = reqs[1]["updateCells"]["rows"][0]["values"]
    assert [c["userEnteredValue"]["stringValue"] for c in header] == RAID_HEADERS
