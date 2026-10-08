from datetime import date

import pytest

from gtrack.layout import (
    DASHBOARD, col_letter, dashboard_row, derive_status, next_task_id, parse_date, parse_progress,
    project_sheet_requests, quote_sheet, task_row, to_serial, validate_project_name, week_starts,
)


def test_col_letter():
    assert [col_letter(i) for i in (0, 11, 25, 26, 27, 701, 702)] == ["A", "L", "Z", "AA", "AB", "ZZ", "AAA"]


def test_quote_sheet_escapes_quote():
    assert quote_sheet("A'B") == "'A''B'"


def test_to_serial():
    assert to_serial(date(1899, 12, 31)) == 1
    assert to_serial(date(2026, 1, 1)) == 46023


@pytest.mark.parametrize("bad", ["", "  ", "a/b", "x[1]", "a'b", DASHBOARD, "x" * 91])
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


def test_derive_status():
    assert derive_status(1.0, None, "진행중") == "완료"
    assert derive_status(0.3, None, "대기") == "진행중"
    assert derive_status(0.3, None, "완료") == "진행중"
    assert derive_status(0.3, None, "보류") == "보류"
    assert derive_status(None, None, "보류") == "보류"
    assert derive_status(0.3, "보류", "대기") == "보류"
    with pytest.raises(ValueError):
        derive_status(None, "없는상태", "대기")


def test_next_task_id():
    assert next_task_id([]) == "T-001"
    assert next_task_id(["T-001", "T-009", "메모", ""]) == "T-010"


def test_week_starts_aligned_to_monday():
    weeks = week_starts(date(2026, 10, 8), date(2026, 10, 26))  # 목 ~ 월
    assert weeks == [date(2026, 10, 5), date(2026, 10, 12), date(2026, 10, 19), date(2026, 10, 26)]


def test_task_row_formulas_reference_own_row():
    row = task_row(7, {"id": "T-001", "name": "x"})
    assert len(row) == 10
    assert "D7" in row[5] and "E7" in row[5]
    assert "H7" in row[8]
    assert row[7] == "대기"


def test_dashboard_row_references_project_sheet():
    row = dashboard_row(3, {"name": "웹 개편", "start": "2026-10-01", "end": "2026-12-31", "sheet_id": 42})
    assert row[4] == "=COUNTA('웹 개편'!A2:A)"
    assert "#gid=42" in row[10]
    assert "E3" in row[8]


def test_project_sheet_requests_sizes_timeline():
    reqs = project_sheet_requests(5, "P", date(2026, 10, 5), date(2026, 11, 1))  # 4주
    grid = reqs[0]["addSheet"]["properties"]["gridProperties"]
    assert grid["columnCount"] == 11 + 4
    header = reqs[1]["updateCells"]["rows"][0]["values"]
    assert header[11]["userEnteredValue"] == {"numberValue": to_serial(date(2026, 10, 5))}
