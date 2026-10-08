"""시트 구조(헤더·수식·서식)를 만드는 순수 함수 모음. API 호출 없음."""
from __future__ import annotations

import re
from datetime import date, timedelta

DASHBOARD = "대시보드"
STATUSES = ["대기", "진행중", "완료", "보류"]
DONE = "완료"
MAX_ROWS = 500

# 작업 시트: A~J 는 작업 데이터, K 는 여백, L 부터 주 단위 간트 차트
TASK_HEADERS = ["ID", "작업명", "담당자", "시작일", "종료일", "기간(일)", "진척률", "상태", "남은일수", "비고"]
TASK_KEYS = ["id", "name", "owner", "start", "end", "duration", "progress", "status", "remaining", "note"]
COL = {k: i for i, k in enumerate(TASK_KEYS)}
TIMELINE_COL = 11
MAX_WEEKS = 104

DASH_HEADERS = ["프로젝트", "PM", "시작일", "종료일", "작업수", "완료", "진척률", "지연", "상태", "진행 바", "시트"]
DASH_KEYS = ["name", "owner", "start", "end", "tasks", "done", "progress", "late", "status"]


def _rgb(hex_: str) -> dict:
    n = int(hex_[1:], 16)
    return {"red": ((n >> 16) & 255) / 255, "green": ((n >> 8) & 255) / 255, "blue": (n & 255) / 255}


COLORS = {
    "header": _rgb("#1f4e79"),
    "white": _rgb("#ffffff"),
    "done": _rgb("#d9ead3"),
    "late": _rgb("#f4cccc"),
    "late_text": _rgb("#990000"),
    "bar": _rgb("#6fa8dc"),
    "bar_done": _rgb("#93c47d"),
    "today": _rgb("#ffe599"),
}

# ---------- 값 검증/변환 ----------

_INVALID_NAME = re.compile(r"[\[\]*?:/\\']")


def validate_project_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise ValueError("프로젝트 이름이 비어 있습니다.")
    if len(name) > 90:
        raise ValueError("프로젝트 이름은 90자 이하여야 합니다.")
    if _INVALID_NAME.search(name):
        raise ValueError("프로젝트 이름에 [ ] * ? : / \\ ' 문자는 쓸 수 없습니다.")
    if name == DASHBOARD:
        raise ValueError(f"'{DASHBOARD}'는 예약된 이름입니다.")
    return name


def parse_date(text: str, label: str = "날짜") -> date:
    s = str(text).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        try:
            return date.fromisoformat(s)
        except ValueError:
            pass
    raise ValueError(f"{label} 형식이 잘못되었습니다: '{text}' (YYYY-MM-DD)")


def parse_progress(text) -> float:
    """'50', '50%', 50 → 0.5"""
    try:
        n = float(str(text).strip().rstrip("%"))
    except ValueError:
        n = -1
    if not 0 <= n <= 100:
        raise ValueError(f"진척률은 0~100 사이여야 합니다: '{text}'")
    return n / 100


def validate_status(status: str) -> str:
    if status not in STATUSES:
        raise ValueError(f"상태는 {', '.join(STATUSES)} 중 하나여야 합니다: '{status}'")
    return status


def derive_status(progress: float | None, explicit: str | None, current: str | None) -> str | None:
    """진척률 변경에 맞춰 상태를 자동으로 정한다. 명시한 상태가 있으면 그것을 따른다."""
    if explicit:
        return validate_status(explicit)
    if progress is None:
        return current
    if progress >= 1:
        return DONE
    if progress > 0 and current in (None, "", "대기", DONE):
        return "진행중"
    if progress == 0 and current == DONE:
        return "진행중"
    return current


def next_task_id(existing_ids) -> str:
    nums = [int(m.group(1)) for i in existing_ids if (m := re.fullmatch(r"T-(\d+)", str(i).strip()))]
    return f"T-{max(nums, default=0) + 1:03d}"


# ---------- A1 표기 ----------

def quote_sheet(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"


def col_letter(index: int) -> str:
    s, n = "", index + 1
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def to_serial(d: date) -> int:
    """Google Sheets 날짜 일련번호(1899-12-30 기준)"""
    return (d - date(1899, 12, 30)).days


def week_starts(start: date, end: date) -> list[date]:
    """start~end 를 덮는 주(월요일 시작) 목록"""
    d = start - timedelta(days=start.weekday())
    weeks = []
    while d <= end and len(weeks) < MAX_WEEKS:
        weeks.append(d)
        d += timedelta(days=7)
    return weeks


# ---------- 행 생성 ----------

def task_row(row: int, t: dict) -> list:
    """작업 시트의 한 행(A~J). row 는 1부터 시작하는 시트 행 번호."""
    return [
        t["id"],
        t["name"],
        t.get("owner") or "",
        t.get("start") or "",
        t.get("end") or "",
        f'=IF(AND(ISNUMBER(D{row}),ISNUMBER(E{row})),E{row}-D{row}+1,"")',
        t.get("progress") or 0,
        t.get("status") or "대기",
        f'=IF(OR(H{row}="{DONE}",NOT(ISNUMBER(E{row}))),"",E{row}-TODAY())',
        t.get("note") or "",
    ]


def dashboard_row(row: int, p: dict) -> list:
    """대시보드의 한 행. 프로젝트 시트를 참조하는 수식이라 시트를 직접 고쳐도 자동 반영된다."""
    q = quote_sheet(p["name"])
    return [
        p["name"],
        p.get("owner") or "",
        p["start"],
        p["end"],
        f"=COUNTA({q}!A2:A)",
        f'=COUNTIF({q}!H2:H,"{DONE}")',
        f"=IFERROR(AVERAGE({q}!G2:G),0)",
        f'=COUNTIFS({q}!E2:E,"<"&TODAY(),{q}!H2:H,"<>{DONE}",{q}!A2:A,"<>")',
        f'=IF(E{row}=0,"대기",IF(F{row}=E{row},"{DONE}",IF(H{row}>0,"지연","진행중")))',
        f'=SPARKLINE(G{row},{{"charttype","bar";"max",1;"color1","#6fa8dc"}})',
        f'=HYPERLINK("#gid={p["sheet_id"]}","열기")',
    ]


# ---------- batchUpdate 요청 생성 ----------

def _range(sheet_id, r0, r1, c0, c1) -> dict:
    return {"sheetId": sheet_id, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def _header_row(sheet_id, values) -> dict:
    cells = []
    for v in values:
        is_num = isinstance(v, int)
        fmt = {
            "backgroundColor": COLORS["header"],
            "horizontalAlignment": "CENTER",
            "textFormat": {"bold": True, "foregroundColor": COLORS["white"]},
        }
        if is_num:
            fmt["numberFormat"] = {"type": "DATE", "pattern": "MM/dd"}
        cells.append({
            "userEnteredValue": {"numberValue": v} if is_num else {"stringValue": v},
            "userEnteredFormat": fmt,
        })
    return {"updateCells": {
        "range": _range(sheet_id, 0, 1, 0, len(values)),
        "fields": "userEnteredValue,userEnteredFormat",
        "rows": [{"values": cells}],
    }}


def _number_format(sheet_id, c0, c1, type_, pattern) -> dict:
    return {"repeatCell": {
        "range": _range(sheet_id, 1, MAX_ROWS, c0, c1),
        "cell": {"userEnteredFormat": {"numberFormat": {"type": type_, "pattern": pattern}}},
        "fields": "userEnteredFormat.numberFormat",
    }}


def _col_width(sheet_id, c0, c1, px) -> dict:
    return {"updateDimensionProperties": {
        "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": c0, "endIndex": c1},
        "properties": {"pixelSize": px},
        "fields": "pixelSize",
    }}


def _cond_format(ranges, formula, fmt) -> dict:
    # index 0 에 삽입하므로 나중에 추가한 규칙이 우선순위가 높다.
    return {"addConditionalFormatRule": {"index": 0, "rule": {
        "ranges": ranges,
        "booleanRule": {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": formula}]}, "format": fmt},
    }}}


def _validation(sheet_id, c0, c1, condition) -> dict:
    return {"setDataValidation": {
        "range": _range(sheet_id, 1, MAX_ROWS, c0, c1),
        "rule": {"condition": condition, "strict": True, "showCustomUi": True},
    }}


def project_sheet_requests(sheet_id: int, title: str, start: date, end: date) -> list[dict]:
    """프로젝트 시트를 만들고 서식·검증·간트 차트까지 설정하는 요청들"""
    weeks = week_starts(start, end)
    last_col = TIMELINE_COL + len(weeks)
    data = [_range(sheet_id, 1, MAX_ROWS, 0, len(TASK_HEADERS))]
    gantt = [_range(sheet_id, 1, MAX_ROWS, TIMELINE_COL, last_col)]
    L = col_letter(TIMELINE_COL)
    in_week = f"ISNUMBER($D2),ISNUMBER($E2),{L}$1<=$E2,{L}$1+6>=$D2"

    requests = [
        {"addSheet": {"properties": {
            "sheetId": sheet_id,
            "title": title,
            "gridProperties": {"rowCount": MAX_ROWS, "columnCount": last_col, "frozenRowCount": 1, "frozenColumnCount": 2},
        }}},
        _header_row(sheet_id, TASK_HEADERS + [""] + [to_serial(w) for w in weeks]),
        _number_format(sheet_id, COL["start"], COL["end"] + 1, "DATE", "yyyy-mm-dd"),
        _number_format(sheet_id, COL["duration"], COL["duration"] + 1, "NUMBER", "0"),
        _number_format(sheet_id, COL["progress"], COL["progress"] + 1, "PERCENT", "0%"),
        _number_format(sheet_id, COL["remaining"], COL["remaining"] + 1, "NUMBER", "0"),
        _validation(sheet_id, COL["start"], COL["end"] + 1, {"type": "DATE_IS_VALID"}),
        _validation(sheet_id, COL["progress"], COL["progress"] + 1, {
            "type": "NUMBER_BETWEEN", "values": [{"userEnteredValue": "0"}, {"userEnteredValue": "1"}]}),
        _validation(sheet_id, COL["status"], COL["status"] + 1, {
            "type": "ONE_OF_LIST", "values": [{"userEnteredValue": s} for s in STATUSES]}),
        _cond_format(data, f'=AND($H2<>"{DONE}",ISNUMBER($E2),$E2<TODAY())',
                     {"backgroundColor": COLORS["late"], "textFormat": {"foregroundColor": COLORS["late_text"]}}),
        _cond_format(data, f'=$H2="{DONE}"', {"backgroundColor": COLORS["done"]}),
        _cond_format(gantt, f"=AND({in_week})", {"backgroundColor": COLORS["bar"]}),
        _cond_format(gantt, f'=AND($H2="{DONE}",{in_week})', {"backgroundColor": COLORS["bar_done"]}),
        _cond_format([_range(sheet_id, 0, 1, TIMELINE_COL, last_col)], f"=AND({L}$1<=TODAY(),{L}$1+6>=TODAY())",
                     {"backgroundColor": COLORS["today"], "textFormat": {"foregroundColor": COLORS["header"]}}),
        _col_width(sheet_id, COL["id"], COL["id"] + 1, 60),
        _col_width(sheet_id, COL["name"], COL["name"] + 1, 220),
        _col_width(sheet_id, COL["note"], COL["note"] + 1, 200),
        _col_width(sheet_id, COL["note"] + 1, TIMELINE_COL, 16),
    ]
    if weeks:
        requests.append(_col_width(sheet_id, TIMELINE_COL, last_col, 42))
    return requests


def dashboard_format_requests(sheet_id: int) -> list[dict]:
    """대시보드 시트 서식 요청. addSheet 는 포함하지 않는다."""
    status = [_range(sheet_id, 1, MAX_ROWS, 8, 9)]
    return [
        {"updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "index": 0, "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 1}},
            "fields": "index,gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
        }},
        _header_row(sheet_id, DASH_HEADERS),
        _number_format(sheet_id, 2, 4, "DATE", "yyyy-mm-dd"),
        _number_format(sheet_id, 6, 7, "PERCENT", "0%"),
        _cond_format(status, '=$I2="지연"', {"backgroundColor": COLORS["late"],
                                             "textFormat": {"foregroundColor": COLORS["late_text"], "bold": True}}),
        _cond_format(status, f'=$I2="{DONE}"', {"backgroundColor": COLORS["done"]}),
        _col_width(sheet_id, 0, 1, 180),
        _col_width(sheet_id, 9, 10, 140),
    ]
