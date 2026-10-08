"""시트 구조(헤더·수식·서식)를 만드는 순수 함수 모음. API 호출 없음.

양식 설계 근거는 docs/PM_GUIDE.md 참고.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

DASHBOARD = "대시보드"
RAID = "RAID"
RESERVED_SHEETS = (DASHBOARD, RAID)
MAX_ROWS = 500

STATUSES = ["대기", "진행중", "차단", "완료", "보류"]
DONE = "완료"
BLOCKED = "차단"
PRIORITIES = ["높음", "보통", "낮음"]

# 일정 건강도 기준 (실제 진척률 - 계획 진척률)
VARIANCE_WARN = -0.05
VARIANCE_RISK = -0.15

# ---------- 작업 시트 ----------
# 왼쪽(A~K)은 사람이 입력하는 칸, 오른쪽(L~R)은 수식/자동 기록 칸, T 부터 주 단위 간트 차트.
TASK_COLUMNS = [
    ("id", "ID"),
    ("phase", "단계"),
    ("name", "작업명"),
    ("owner", "담당자"),
    ("priority", "우선순위"),
    ("status", "상태"),
    ("progress", "진척률"),
    ("start", "시작일"),
    ("end", "종료일"),
    ("after", "선행작업"),
    ("note", "비고"),
    ("planned", "계획진척률"),
    ("variance", "일정차이"),
    ("remaining", "남은일수"),
    ("baseline", "기준종료일"),
    ("slip", "일정변경(일)"),
    ("done_date", "완료일"),
    ("duration", "기간(일)"),
]
TASK_KEYS = [k for k, _ in TASK_COLUMNS]
TASK_HEADERS = [h for _, h in TASK_COLUMNS]
COL = {k: i for i, k in enumerate(TASK_KEYS)}
INPUT_COLS = COL["note"] + 1
TIMELINE_COL = len(TASK_COLUMNS) + 1
MAX_WEEKS = 104

# ---------- 대시보드 ----------
DASH_COLUMNS = [
    ("name", "프로젝트"),
    ("owner", "PM"),
    ("start", "시작일"),
    ("end", "종료일"),
    ("tasks", "작업수"),
    ("done", "완료"),
    ("progress", "진척률"),
    ("elapsed", "기간경과"),
    ("variance", "일정차이"),
    ("late", "지연"),
    ("blocked", "차단"),
    ("raid", "열린 RAID"),
    ("next_due", "다음 마감"),
    ("health", "건강도"),
    ("bar", "진행 바"),
    ("link", "시트"),
]
DASH_KEYS = [k for k, _ in DASH_COLUMNS]
DASH_HEADERS = [h for _, h in DASH_COLUMNS]
DCOL = {k: i for i, k in enumerate(DASH_KEYS)}
HEALTH = ["정상", "주의", "위험", "완료", "대기"]

# ---------- RAID 로그 ----------
RAID_COLUMNS = [
    ("id", "ID"),
    ("project", "프로젝트"),
    ("type", "유형"),
    ("text", "내용"),
    ("impact", "영향도"),
    ("owner", "담당자"),
    ("action", "대응방안"),
    ("status", "상태"),
    ("created", "등록일"),
    ("due", "기한"),
    ("related", "관련작업"),
]
RAID_KEYS = [k for k, _ in RAID_COLUMNS]
RAID_HEADERS = [h for _, h in RAID_COLUMNS]
RCOL = {k: i for i, k in enumerate(RAID_KEYS)}
RAID_TYPES = ["리스크", "가정", "이슈", "의존성", "결정"]
RAID_STATUSES = ["열림", "대응중", "해결", "종료"]
RAID_CLOSED = ("해결", "종료")


def _rgb(hex_: str) -> dict:
    n = int(hex_[1:], 16)
    return {"red": ((n >> 16) & 255) / 255, "green": ((n >> 8) & 255) / 255, "blue": (n & 255) / 255}


COLORS = {
    "header": _rgb("#1f4e79"),
    "header_calc": _rgb("#5f6368"),
    "calc_bg": _rgb("#f8f9fa"),
    "white": _rgb("#ffffff"),
    "done": _rgb("#d9ead3"),
    "late": _rgb("#f4cccc"),
    "late_text": _rgb("#990000"),
    "warn": _rgb("#fff2cc"),
    "warn_text": _rgb("#7f6000"),
    "blocked": _rgb("#fce5cd"),
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
    if name in RESERVED_SHEETS:
        raise ValueError(f"'{name}'는 예약된 이름입니다.")
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


def _one_of(value: str, allowed: list[str], label: str) -> str:
    if value not in allowed:
        raise ValueError(f"{label}은(는) {', '.join(allowed)} 중 하나여야 합니다: '{value}'")
    return value


def validate_status(status: str) -> str:
    return _one_of(status, STATUSES, "상태")


def validate_priority(priority: str) -> str:
    return _one_of(priority, PRIORITIES, "우선순위")


def validate_raid_type(t: str) -> str:
    return _one_of(t, RAID_TYPES, "RAID 유형")


def validate_raid_status(s: str) -> str:
    return _one_of(s, RAID_STATUSES, "RAID 상태")


def validate_impact(s: str) -> str:
    return _one_of(s, PRIORITIES, "영향도")


def parse_task_refs(text: str) -> str:
    """'T-1, t-003' → 'T-001, T-003'. 빈 문자열은 그대로."""
    if not str(text).strip():
        return ""
    refs = []
    for part in re.split(r"[,\s]+", str(text).strip()):
        m = re.fullmatch(r"[Tt]-?(\d+)", part)
        if not m:
            raise ValueError(f"작업 ID 형식이 잘못되었습니다: '{part}' (예: T-001)")
        refs.append(f"T-{int(m.group(1)):03d}")
    return ", ".join(dict.fromkeys(refs))


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


def next_id(existing_ids, prefix: str = "T") -> str:
    pat = re.compile(rf"{prefix}-(\d+)")
    nums = [int(m.group(1)) for i in existing_ids if (m := pat.fullmatch(str(i).strip()))]
    return f"{prefix}-{max(nums, default=0) + 1:03d}"


def next_task_id(existing_ids) -> str:
    return next_id(existing_ids, "T")


# ---------- A1 표기 ----------

def quote_sheet(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"


def col_letter(index: int) -> str:
    s, n = "", index + 1
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


C = {k: col_letter(i) for k, i in COL.items()}    # 작업 시트 열 문자
D = {k: col_letter(i) for k, i in DCOL.items()}   # 대시보드 열 문자
R = {k: col_letter(i) for k, i in RCOL.items()}   # RAID 열 문자


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
    """작업 시트의 한 행. row 는 1부터 시작하는 시트 행 번호."""
    s, e, st, pg, bl = (f"{C[k]}{row}" for k in ("start", "end", "status", "progress", "baseline"))
    both = f"ISNUMBER({s}),ISNUMBER({e})"
    values = {
        "id": t["id"],
        "phase": t.get("phase") or "",
        "name": t["name"],
        "owner": t.get("owner") or "",
        "priority": t.get("priority") or "보통",
        "status": t.get("status") or "대기",
        "progress": t.get("progress") or 0,
        "start": t.get("start") or "",
        "end": t.get("end") or "",
        "after": t.get("after") or "",
        "note": t.get("note") or "",
        "planned": f'=IF(AND({both}),MAX(0,MIN(1,(TODAY()-{s}+1)/({e}-{s}+1))),"")',
        "variance": f'=IF(ISNUMBER({C["planned"]}{row}),{pg}-{C["planned"]}{row},"")',
        "remaining": f'=IF(OR({st}="{DONE}",NOT(ISNUMBER({e}))),"",{e}-TODAY())',
        "baseline": t.get("baseline") or t.get("end") or "",
        "slip": f'=IF(AND(ISNUMBER({e}),ISNUMBER({bl})),{e}-{bl},"")',
        "done_date": t.get("done_date") or "",
        "duration": f'=IF(AND({both}),{e}-{s}+1,"")',
    }
    return [values[k] for k in TASK_KEYS]


def dashboard_row(row: int, p: dict) -> list:
    """대시보드의 한 행. 프로젝트 시트를 참조하는 수식이라 시트를 직접 고쳐도 자동 반영된다."""
    q = quote_sheet(p["name"])
    rq = quote_sheet(RAID)
    col = lambda k: f"{q}!{C[k]}2:{C[k]}"
    me = lambda k: f"{D[k]}{row}"
    rcol = lambda k: f"{rq}!{R[k]}2:{R[k]}"
    raid_open = (f'{rcol("project")},{me("name")},{rcol("status")},"<>{RAID_CLOSED[0]}",'
                 f'{rcol("status")},"<>{RAID_CLOSED[1]}"')
    # 건강도(RAG): 위험 = 일정차이 -15% 이하 또는 지연 3건 이상
    #              주의 = 일정차이 -5% 미만, 지연·차단 1건 이상, 영향도 '높음'인 열린 RAID 존재
    high_raid = f'COUNTIFS({raid_open},{rcol("impact")},"높음")>0'
    values = {
        "name": p["name"],
        "owner": p.get("owner") or "",
        "start": p["start"],
        "end": p["end"],
        "tasks": f'=COUNTA({col("id")})',
        "done": f'=COUNTIF({col("status")},"{DONE}")',
        "progress": f'=IFERROR(AVERAGE({col("progress")}),0)',
        # 프로젝트 기간 중 지난 비율 (선형)
        "elapsed": f'=IFERROR(MAX(0,MIN(1,(TODAY()-{me("start")}+1)/({me("end")}-{me("start")}+1))),0)',
        # 날짜가 있는 작업들의 (실제 - 계획) 진척률 평균. 날짜 없는 작업은 제외된다.
        "variance": f'=IFERROR(AVERAGE({col("variance")}),0)',
        "late": f'=COUNTIFS({col("end")},"<"&TODAY(),{col("status")},"<>{DONE}",{col("id")},"<>")',
        "blocked": f'=COUNTIF({col("status")},"{BLOCKED}")',
        "raid": f"=COUNTIFS({raid_open})",
        "next_due": f'=IFERROR(1/(1/MINIFS({col("end")},{col("status")},"<>{DONE}",{col("end")},">="&TODAY())),"")',
        "health": (f'=IF({me("tasks")}=0,"대기",IF({me("done")}={me("tasks")},"{DONE}",'
                   f'IF(OR({me("variance")}<={VARIANCE_RISK},{me("late")}>=3),"위험",'
                   f'IF(OR({me("variance")}<{VARIANCE_WARN},{me("late")}>0,{me("blocked")}>0,{high_raid}),"주의","정상"))))'),
        "bar": f'=SPARKLINE({me("progress")},{{"charttype","bar";"max",1;"color1","#6fa8dc"}})',
        "link": f'=HYPERLINK("#gid={p["sheet_id"]}","열기")',
    }
    return [values[k] for k in DASH_KEYS]


def raid_row(item: dict) -> list:
    return [item.get(k) or "" for k in RAID_KEYS]


# ---------- batchUpdate 요청 생성 ----------

def _range(sheet_id, r0, r1, c0, c1) -> dict:
    return {"sheetId": sheet_id, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def _rows(sheet_id, c0, c1) -> dict:
    return _range(sheet_id, 1, MAX_ROWS, c0, c1)


def _header_row(sheet_id, values, calc_from: int | None = None) -> dict:
    """calc_from 이후 열은 '자동 계산' 열로 회색 헤더."""
    cells = []
    for i, v in enumerate(values):
        is_num = isinstance(v, int)
        calc = calc_from is not None and calc_from <= i and not is_num and v
        fmt = {
            "backgroundColor": COLORS["header_calc"] if calc else COLORS["header"],
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
            "wrapStrategy": "WRAP",
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
        "range": _rows(sheet_id, c0, c1),
        "cell": {"userEnteredFormat": {"numberFormat": {"type": type_, "pattern": pattern}}},
        "fields": "userEnteredFormat.numberFormat",
    }}


def _background(sheet_id, c0, c1, color) -> dict:
    return {"repeatCell": {
        "range": _rows(sheet_id, c0, c1),
        "cell": {"userEnteredFormat": {"backgroundColor": color}},
        "fields": "userEnteredFormat.backgroundColor",
    }}


def _col_width(sheet_id, c0, c1, px) -> dict:
    return {"updateDimensionProperties": {
        "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": c0, "endIndex": c1},
        "properties": {"pixelSize": px},
        "fields": "pixelSize",
    }}


def _header_height(sheet_id, px=40) -> dict:
    return {"updateDimensionProperties": {
        "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
        "properties": {"pixelSize": px},
        "fields": "pixelSize",
    }}


def _cond_format(ranges, formula, fmt) -> dict:
    # index 0 에 삽입하므로 나중에 추가한 규칙이 우선순위가 높다.
    return {"addConditionalFormatRule": {"index": 0, "rule": {
        "ranges": ranges,
        "booleanRule": {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": formula}]}, "format": fmt},
    }}}


def _validation(sheet_id, c0, c1, condition, strict=True) -> dict:
    return {"setDataValidation": {
        "range": _rows(sheet_id, c0, c1),
        "rule": {"condition": condition, "strict": strict, "showCustomUi": True},
    }}


def _list_validation(sheet_id, col, values) -> dict:
    return _validation(sheet_id, col, col + 1, {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in values]})


def _date_validation(sheet_id, col) -> dict:
    return _validation(sheet_id, col, col + 1, {"type": "DATE_IS_VALID"})


def _one(col) -> tuple[int, int]:
    return col, col + 1


def project_sheet_requests(sheet_id: int, title: str, start: date, end: date) -> list[dict]:
    """프로젝트 시트를 만들고 서식·검증·간트 차트까지 설정하는 요청들"""
    weeks = week_starts(start, end)
    last_col = TIMELINE_COL + len(weeks)
    data = [_rows(sheet_id, 0, len(TASK_COLUMNS))]
    gantt = [_rows(sheet_id, TIMELINE_COL, last_col)]
    T = col_letter(TIMELINE_COL)
    st, s, e, a = C["status"], C["start"], C["end"], C["after"]
    in_week = f"ISNUMBER(${s}2),ISNUMBER(${e}2),{T}$1<=${e}2,{T}$1+6>=${s}2"
    ids, sts = f"$A$2:$A${MAX_ROWS}", f"${st}$2:${st}${MAX_ROWS}"

    requests = [
        {"addSheet": {"properties": {
            "sheetId": sheet_id,
            "title": title,
            "gridProperties": {"rowCount": MAX_ROWS, "columnCount": last_col, "frozenRowCount": 1, "frozenColumnCount": 3},
        }}},
        _header_row(sheet_id, TASK_HEADERS + [""] + [to_serial(w) for w in weeks], calc_from=INPUT_COLS),
        _header_height(sheet_id),
        _background(sheet_id, INPUT_COLS, len(TASK_COLUMNS), COLORS["calc_bg"]),
        _number_format(sheet_id, *_one(COL["progress"]), "PERCENT", "0%"),
        _number_format(sheet_id, *_one(COL["planned"]), "PERCENT", "0%"),
        _number_format(sheet_id, *_one(COL["variance"]), "PERCENT", "+0%;-0%;0%"),
        _number_format(sheet_id, COL["start"], COL["end"] + 1, "DATE", "yyyy-mm-dd"),
        _number_format(sheet_id, *_one(COL["baseline"]), "DATE", "yyyy-mm-dd"),
        _number_format(sheet_id, *_one(COL["done_date"]), "DATE", "yyyy-mm-dd"),
        _number_format(sheet_id, *_one(COL["remaining"]), "NUMBER", "0"),
        _number_format(sheet_id, *_one(COL["slip"]), "NUMBER", "+0;-0;0"),
        _number_format(sheet_id, *_one(COL["duration"]), "NUMBER", "0"),
        _list_validation(sheet_id, COL["status"], STATUSES),
        _list_validation(sheet_id, COL["priority"], PRIORITIES),
        _validation(sheet_id, *_one(COL["progress"]), {
            "type": "NUMBER_BETWEEN", "values": [{"userEnteredValue": "0"}, {"userEnteredValue": "1"}]}),
        _date_validation(sheet_id, COL["start"]),
        _date_validation(sheet_id, COL["end"]),
        _date_validation(sheet_id, COL["baseline"]),
        _date_validation(sheet_id, COL["done_date"]),
        # 행 강조: 차단 < 지연 < 완료 순으로 우선
        _cond_format(data, f'=${st}2="{BLOCKED}"', {"backgroundColor": COLORS["blocked"]}),
        _cond_format(data, f'=AND(${st}2<>"{DONE}",ISNUMBER(${e}2),${e}2<TODAY())',
                     {"backgroundColor": COLORS["late"], "textFormat": {"foregroundColor": COLORS["late_text"]}}),
        _cond_format(data, f'=${st}2="{DONE}"', {"backgroundColor": COLORS["done"]}),
        # 셀 강조
        _cond_format([_rows(sheet_id, *_one(COL["priority"]))], f'=${C["priority"]}2="높음"',
                     {"textFormat": {"bold": True, "foregroundColor": COLORS["late_text"]}}),
        _cond_format([_rows(sheet_id, *_one(COL["variance"]))],
                     f'=AND(ISNUMBER(${C["variance"]}2),${C["variance"]}2<{VARIANCE_WARN})',
                     {"backgroundColor": COLORS["warn"], "textFormat": {"foregroundColor": COLORS["warn_text"]}}),
        _cond_format([_rows(sheet_id, *_one(COL["variance"]))],
                     f'=AND(ISNUMBER(${C["variance"]}2),${C["variance"]}2<={VARIANCE_RISK})',
                     {"backgroundColor": COLORS["late"], "textFormat": {"bold": True, "foregroundColor": COLORS["late_text"]}}),
        _cond_format([_rows(sheet_id, *_one(COL["slip"]))], f'=AND(ISNUMBER(${C["slip"]}2),${C["slip"]}2>0)',
                     {"textFormat": {"bold": True, "foregroundColor": COLORS["late_text"]}}),
        # 선행작업 중 미완료가 있으면 주황색
        _cond_format([_rows(sheet_id, *_one(COL["after"]))],
                     f'=AND(${a}2<>"",${st}2<>"{DONE}",'
                     f'SUMPRODUCT(({ids}<>"")*ISNUMBER(SEARCH({ids},${a}2))*({sts}<>"{DONE}"))>0)',
                     {"backgroundColor": COLORS["blocked"], "textFormat": {"bold": True}}),
        # 간트 차트
        _cond_format(gantt, f"=AND({in_week})", {"backgroundColor": COLORS["bar"]}),
        _cond_format(gantt, f'=AND(${st}2="{BLOCKED}",{in_week})', {"backgroundColor": COLORS["blocked"]}),
        _cond_format(gantt, f'=AND(${st}2="{DONE}",{in_week})', {"backgroundColor": COLORS["bar_done"]}),
        _cond_format([_range(sheet_id, 0, 1, TIMELINE_COL, last_col)], f"=AND({T}$1<=TODAY(),{T}$1+6>=TODAY())",
                     {"backgroundColor": COLORS["today"], "textFormat": {"foregroundColor": COLORS["header"]}}),
        _col_width(sheet_id, COL["id"], COL["id"] + 1, 56),
        _col_width(sheet_id, COL["phase"], COL["phase"] + 1, 110),
        _col_width(sheet_id, COL["name"], COL["name"] + 1, 240),
        _col_width(sheet_id, COL["priority"], COL["progress"] + 1, 64),
        _col_width(sheet_id, COL["start"], COL["end"] + 1, 90),
        _col_width(sheet_id, COL["note"], COL["note"] + 1, 200),
        _col_width(sheet_id, INPUT_COLS, len(TASK_COLUMNS), 74),
        _col_width(sheet_id, len(TASK_COLUMNS), TIMELINE_COL, 16),
    ]
    if weeks:
        requests.append(_col_width(sheet_id, TIMELINE_COL, last_col, 42))
    return requests


def dashboard_format_requests(sheet_id: int) -> list[dict]:
    """대시보드 시트 서식 요청. addSheet 는 포함하지 않는다."""
    health = [_rows(sheet_id, *_one(DCOL["health"]))]
    h = f'${D["health"]}2'
    v = [_rows(sheet_id, *_one(DCOL["variance"]))]
    return [
        {"updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "index": 0, "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 1}},
            "fields": "index,gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
        }},
        _header_row(sheet_id, DASH_HEADERS),
        _header_height(sheet_id),
        _number_format(sheet_id, DCOL["start"], DCOL["end"] + 1, "DATE", "yyyy-mm-dd"),
        _number_format(sheet_id, DCOL["progress"], DCOL["elapsed"] + 1, "PERCENT", "0%"),
        _number_format(sheet_id, *_one(DCOL["variance"]), "PERCENT", "+0%;-0%;0%"),
        _number_format(sheet_id, *_one(DCOL["next_due"]), "DATE", "yyyy-mm-dd"),
        _cond_format(health, f'={h}="주의"', {"backgroundColor": COLORS["warn"], "textFormat": {"bold": True, "foregroundColor": COLORS["warn_text"]}}),
        _cond_format(health, f'={h}="위험"', {"backgroundColor": COLORS["late"], "textFormat": {"bold": True, "foregroundColor": COLORS["late_text"]}}),
        _cond_format(health, f'={h}="정상"', {"backgroundColor": COLORS["done"], "textFormat": {"bold": True}}),
        _cond_format(health, f'={h}="{DONE}"', {"backgroundColor": COLORS["done"]}),
        _cond_format(v, f'=${D["variance"]}2<{VARIANCE_WARN}', {"textFormat": {"bold": True, "foregroundColor": COLORS["late_text"]}}),
        _col_width(sheet_id, 0, 1, 200),
        _col_width(sheet_id, DCOL["start"], DCOL["end"] + 1, 90),
        _col_width(sheet_id, DCOL["bar"], DCOL["bar"] + 1, 140),
    ]


def raid_sheet_requests(sheet_id: int, add_sheet: bool = True) -> list[dict]:
    """RAID 로그(리스크·가정·이슈·의존성·결정) 시트"""
    data = [_rows(sheet_id, 0, len(RAID_COLUMNS))]
    st, im, ty = (f"${R[k]}2" for k in ("status", "impact", "type"))
    closed = f'OR({st}="{RAID_CLOSED[0]}",{st}="{RAID_CLOSED[1]}")'
    requests = []
    if add_sheet:
        requests.append({"addSheet": {"properties": {
            "sheetId": sheet_id, "title": RAID, "index": 1,
            "gridProperties": {"rowCount": MAX_ROWS, "columnCount": len(RAID_COLUMNS), "frozenRowCount": 1},
        }}})
    return requests + [
        _header_row(sheet_id, RAID_HEADERS),
        _header_height(sheet_id),
        _list_validation(sheet_id, RCOL["type"], RAID_TYPES),
        _list_validation(sheet_id, RCOL["impact"], PRIORITIES),
        _list_validation(sheet_id, RCOL["status"], RAID_STATUSES),
        _validation(sheet_id, *_one(RCOL["project"]), {
            "type": "ONE_OF_RANGE", "values": [{"userEnteredValue": f"={quote_sheet(DASHBOARD)}!$A$2:$A"}]}),
        _date_validation(sheet_id, RCOL["created"]),
        _date_validation(sheet_id, RCOL["due"]),
        _number_format(sheet_id, RCOL["created"], RCOL["created"] + 1, "DATE", "yyyy-mm-dd"),
        _number_format(sheet_id, RCOL["due"], RCOL["due"] + 1, "DATE", "yyyy-mm-dd"),
        _cond_format(data, f'=AND(NOT({closed}),{ty}="이슈")', {"backgroundColor": COLORS["blocked"]}),
        _cond_format(data, f'=AND(NOT({closed}),{im}="높음")',
                     {"backgroundColor": COLORS["late"], "textFormat": {"foregroundColor": COLORS["late_text"]}}),
        _cond_format(data, f'=AND($A2<>"",{closed})', {"textFormat": {"foregroundColor": _rgb("#999999")}}),
        _col_width(sheet_id, RCOL["project"], RCOL["project"] + 1, 160),
        _col_width(sheet_id, RCOL["text"], RCOL["text"] + 1, 320),
        _col_width(sheet_id, RCOL["action"], RCOL["action"] + 1, 260),
    ]
