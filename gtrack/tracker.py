"""Google Sheets API 를 호출해 프로젝트/작업/RAID 를 관리한다."""
from __future__ import annotations

import random
from datetime import date, timedelta

from .layout import (
    COL, DASH_KEYS, DASHBOARD, DONE, RAID, RAID_KEYS, RCOL, RESERVED_SHEETS, TASK_KEYS, col_letter,
    dashboard_format_requests, dashboard_row, derive_status, next_id, parse_date, parse_progress,
    parse_task_refs, project_sheet_requests, quote_sheet, raid_row, raid_sheet_requests, task_row,
    validate_impact, validate_priority, validate_project_name, validate_raid_status, validate_raid_type,
    validate_status,
)

DEFAULT_WEEKS = 12


class TrackerError(Exception):
    pass


class Tracker:
    def __init__(self, service, spreadsheet_id: str, today: date | None = None):
        """service: googleapiclient.discovery.build('sheets', 'v4', ...) 결과"""
        self.service = service
        self.spreadsheet_id = spreadsheet_id
        self._today = today

    @property
    def today(self) -> date:
        return self._today or date.today()

    @property
    def url(self) -> str:
        return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit"

    @classmethod
    def create(cls, service, title: str, today: date | None = None) -> "Tracker":
        """새 스프레드시트를 만들고 대시보드·RAID 시트를 구성한다."""
        res = service.spreadsheets().create(body={
            "properties": {"title": title, "locale": "ko_KR", "timeZone": "Asia/Seoul"},
            "sheets": [{"properties": {"sheetId": 0, "title": DASHBOARD}}],
        }).execute()
        tracker = cls(service, res["spreadsheetId"], today)
        tracker._batch_update(dashboard_format_requests(0) + raid_sheet_requests(_new_sheet_id({DASHBOARD: 0})))
        return tracker

    def ensure_base_sheets(self) -> list[str]:
        """대시보드·RAID 시트가 없으면 만든다. 새로 만든 시트 이름 목록을 돌려준다."""
        sheets = self._sheet_map()
        requests, created = [], []
        if DASHBOARD not in sheets:
            sid = _new_sheet_id(sheets)
            sheets[DASHBOARD] = sid
            requests += [{"addSheet": {"properties": {"sheetId": sid, "title": DASHBOARD}}}] + dashboard_format_requests(sid)
            created.append(DASHBOARD)
        if RAID not in sheets:
            requests += raid_sheet_requests(_new_sheet_id(sheets))
            created.append(RAID)
        if requests:
            self._batch_update(requests)
        return created

    # ---------- 프로젝트 ----------

    def add_project(self, name: str, owner: str | None = None, start: str | None = None,
                    end: str | None = None) -> dict:
        title = validate_project_name(name)
        start_d = parse_date(start, "시작일") if start else self.today
        end_d = parse_date(end, "종료일") if end else start_d + timedelta(weeks=DEFAULT_WEEKS, days=-1)
        if end_d < start_d:
            raise TrackerError("종료일이 시작일보다 빠릅니다.")

        sheets = self._sheet_map()
        missing = [s for s in RESERVED_SHEETS if s not in sheets]
        if missing:
            raise TrackerError(f"{', '.join(missing)} 시트가 없습니다. 먼저 init 을 실행하세요.")
        if title in sheets:
            raise TrackerError(f"이미 있는 프로젝트입니다: {title}")

        sheet_id = _new_sheet_id(sheets)
        self._batch_update(project_sheet_requests(sheet_id, title, start_d, end_d))

        row = len(self._column_values(DASHBOARD, "A")) + 1
        project = {"name": title, "owner": owner, "start": start_d.isoformat(), "end": end_d.isoformat(),
                   "sheet_id": sheet_id}
        self._write_row(DASHBOARD, row, dashboard_row(row, project))
        return project

    def list_projects(self) -> list[dict]:
        rows = self._get_values(f"{quote_sheet(DASHBOARD)}!A2:{col_letter(len(DASH_KEYS) - 1)}")
        return [_record(DASH_KEYS, r) for r in rows if r and r[0]]

    def remove_project(self, name: str) -> None:
        sheets = self._sheet_map()
        if name in RESERVED_SHEETS or name not in sheets:
            raise TrackerError(f"프로젝트가 없습니다: {name}")
        requests = [{"deleteSheet": {"sheetId": sheets[name]}}]
        names = self._column_values(DASHBOARD, "A")
        if name in names[1:]:
            i = names.index(name, 1)
            requests.append({"deleteDimension": {"range": {
                "sheetId": sheets[DASHBOARD], "dimension": "ROWS", "startIndex": i, "endIndex": i + 1}}})
        self._batch_update(requests)

    # ---------- 작업 ----------

    def add_task(self, project: str, name: str, owner: str | None = None, start: str | None = None,
                 end: str | None = None, progress: str | None = None, status: str | None = None,
                 note: str | None = None, phase: str | None = None, priority: str | None = None,
                 after: str | None = None) -> dict:
        self._require_project(project)
        if not name:
            raise TrackerError("작업명이 필요합니다.")
        start_d = parse_date(start, "시작일") if start else None
        end_d = parse_date(end, "종료일") if end else None
        if start_d and end_d and end_d < start_d:
            raise TrackerError("종료일이 시작일보다 빠릅니다.")

        p = parse_progress(progress) if progress is not None else 0.0
        ids = self._column_values(project, "A")
        refs = parse_task_refs(after or "")
        self._check_refs(refs, ids[1:])
        st = derive_status(p, status, "대기")
        task = {
            "id": next_id(ids[1:], "T"),
            "phase": phase,
            "name": name,
            "owner": owner,
            "priority": validate_priority(priority) if priority else "보통",
            "status": st,
            "progress": 1.0 if st == DONE else p,
            "start": start_d.isoformat() if start_d else "",
            "end": end_d.isoformat() if end_d else "",
            "after": refs,
            "note": note,
            "done_date": self.today.isoformat() if st == DONE else "",
        }
        row = len(ids) + 1
        self._write_row(project, row, task_row(row, task))
        return task

    def add_tasks(self, project: str, tasks: list[dict]) -> list[dict]:
        """여러 작업을 한 번에 추가 (API 호출 최소화). 각 dict 는 add_task 인자와 같다."""
        self._require_project(project)
        ids = self._column_values(project, "A")
        existing = ids[1:]
        row0 = len(ids) + 1
        rows, out = [], []
        for t in tasks:
            if not t.get("name"):
                raise TrackerError("작업명이 필요합니다.")
            s = parse_date(t["start"], "시작일") if t.get("start") else None
            e = parse_date(t["end"], "종료일") if t.get("end") else None
            if s and e and e < s:
                raise TrackerError(f"종료일이 시작일보다 빠릅니다: {t['name']}")
            p = parse_progress(t["progress"]) if t.get("progress") is not None else 0.0
            st = derive_status(p, t.get("status"), "대기")
            tid = next_id(existing, "T")
            refs = parse_task_refs(t.get("after") or "")
            task = {
                **t, "id": tid, "status": st, "progress": 1.0 if st == DONE else p,
                "priority": validate_priority(t["priority"]) if t.get("priority") else "보통",
                "start": s.isoformat() if s else "", "end": e.isoformat() if e else "", "after": refs,
                "done_date": self.today.isoformat() if st == DONE else "",
            }
            existing.append(tid)
            self._check_refs(refs, existing)
            rows.append(task_row(row0 + len(rows), task))
            out.append(task)
        if rows:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id, range=f"{quote_sheet(project)}!A{row0}",
                valueInputOption="USER_ENTERED", body={"values": rows},
            ).execute()
        return out

    def update_task(self, project: str, task_id: str, **changes) -> dict:
        """changes: name, owner, start, end, progress, status, note, phase, priority, after
        (None 은 변경 안 함, '' 은 비움)"""
        self._require_project(project)
        tasks = self._read_tasks(project)
        task = next((t for t in tasks if t["id"] == task_id), None)
        if task is None:
            raise TrackerError(f"{project} 에 작업 {task_id} 가 없습니다.")
        changes = {k: v for k, v in changes.items() if v is not None}

        cells: dict[str, object] = {}
        for key in ("name", "owner", "note", "phase"):
            if key in changes:
                cells[key] = changes[key]
        if "priority" in changes:
            cells["priority"] = validate_priority(changes["priority"])
        if "after" in changes:
            refs = parse_task_refs(changes["after"])
            if task_id in refs.split(", "):
                raise TrackerError("자기 자신을 선행작업으로 지정할 수 없습니다.")
            self._check_refs(refs, [t["id"] for t in tasks])
            cells["after"] = refs
        for key, label in (("start", "시작일"), ("end", "종료일")):
            if key in changes:
                cells[key] = parse_date(changes[key], label).isoformat() if changes[key] else ""

        s, e = cells.get("start", task["start"]), cells.get("end", task["end"])
        if s and e and e < s:
            raise TrackerError("종료일이 시작일보다 빠릅니다.")
        # 기준종료일은 처음 정해진 종료일을 유지한다. 비어 있을 때만 채운다.
        if cells.get("end") and not task["baseline"]:
            cells["baseline"] = cells["end"]

        progress = parse_progress(changes["progress"]) if "progress" in changes else None
        if progress is not None:
            cells["progress"] = progress
        if "status" in changes:
            validate_status(changes["status"])
        status = derive_status(progress, changes.get("status"), task["status"])
        if status != task["status"]:
            cells["status"] = status
            if status == DONE:
                cells["done_date"] = self.today.isoformat()
            elif task["status"] == DONE:
                cells["done_date"] = ""
        if status == DONE and progress is None:
            cells["progress"] = 1  # 상태만 '완료'로 바꾸면 진척률도 100%로 맞춘다.

        if not cells:
            raise TrackerError("변경할 항목이 없습니다.")
        self._write_cells(project, task["row"], {COL[k]: v for k, v in cells.items()})

        if "progress" in cells:
            cells["progress"] = f"{round(float(cells['progress']) * 100)}%"
        return {**task, **cells}

    def list_tasks(self, project: str) -> list[dict]:
        self._require_project(project)
        return self._read_tasks(project)

    # ---------- RAID ----------

    def add_raid(self, project: str, type_: str, text: str, impact: str | None = None, owner: str | None = None,
                 action: str | None = None, due: str | None = None, related: str | None = None,
                 status: str | None = None) -> dict:
        self._require_project(project)
        if not text:
            raise TrackerError("내용이 필요합니다.")
        ids = self._column_values(RAID, "A")
        item = {
            "id": next_id(ids[1:], "R"),
            "project": project,
            "type": validate_raid_type(type_),
            "text": text,
            "impact": validate_impact(impact) if impact else "보통",
            "owner": owner,
            "action": action,
            "status": validate_raid_status(status) if status else "열림",
            "created": self.today.isoformat(),
            "due": parse_date(due, "기한").isoformat() if due else "",
            "related": parse_task_refs(related or ""),
        }
        self._write_row(RAID, len(ids) + 1, raid_row(item))
        return item

    def list_raid(self, project: str | None = None, open_only: bool = False) -> list[dict]:
        rows = self._get_values(f"{quote_sheet(RAID)}!A2:{col_letter(len(RAID_KEYS) - 1)}")
        items = []
        for i, r in enumerate(rows):
            if r and r[0]:
                item = _record(RAID_KEYS, r)
                item["row"] = i + 2
                items.append(item)
        if project:
            items = [i for i in items if i["project"] == project]
        if open_only:
            items = [i for i in items if i["status"] not in ("해결", "종료")]
        return items

    def update_raid(self, raid_id: str, **changes) -> dict:
        item = next((i for i in self.list_raid() if i["id"] == raid_id), None)
        if item is None:
            raise TrackerError(f"RAID 항목 {raid_id} 가 없습니다.")
        changes = {k: v for k, v in changes.items() if v is not None}
        cells: dict[str, object] = {}
        for key in ("text", "owner", "action"):
            if key in changes:
                cells[key] = changes[key]
        if "status" in changes:
            cells["status"] = validate_raid_status(changes["status"])
        if "impact" in changes:
            cells["impact"] = validate_impact(changes["impact"])
        if "type" in changes:
            cells["type"] = validate_raid_type(changes["type"])
        if "due" in changes:
            cells["due"] = parse_date(changes["due"], "기한").isoformat() if changes["due"] else ""
        if "related" in changes:
            cells["related"] = parse_task_refs(changes["related"])
        if not cells:
            raise TrackerError("변경할 항목이 없습니다.")
        self._write_cells(RAID, item["row"], {RCOL[k]: v for k, v in cells.items()})
        return {**item, **cells}

    # ---------- 내부 ----------

    def _check_refs(self, refs: str, known_ids: list[str]) -> None:
        unknown = [r for r in refs.split(", ") if r and r not in known_ids]
        if unknown:
            raise TrackerError(f"없는 작업 ID 입니다: {', '.join(unknown)}")

    def _read_tasks(self, project: str) -> list[dict]:
        rows = self._get_values(f"{quote_sheet(project)}!A2:{col_letter(len(TASK_KEYS) - 1)}")
        tasks = []
        for i, r in enumerate(rows):
            if r and r[0]:
                t = _record(TASK_KEYS, r)
                t["row"] = i + 2
                tasks.append(t)
        return tasks

    def _require_project(self, project: str) -> None:
        if project in RESERVED_SHEETS or project not in self._sheet_map():
            raise TrackerError(f"프로젝트가 없습니다: {project}")

    def _sheet_map(self) -> dict[str, int]:
        res = self.service.spreadsheets().get(
            spreadsheetId=self.spreadsheet_id, fields="sheets.properties(sheetId,title)").execute()
        return {s["properties"]["title"]: s["properties"]["sheetId"] for s in res.get("sheets", [])}

    def _get_values(self, a1: str) -> list[list]:
        res = self.service.spreadsheets().values().get(spreadsheetId=self.spreadsheet_id, range=a1).execute()
        return res.get("values", [])

    def _column_values(self, sheet: str, col: str) -> list[str]:
        return [r[0] if r else "" for r in self._get_values(f"{quote_sheet(sheet)}!{col}:{col}")]

    def _write_row(self, sheet: str, row: int, values: list) -> None:
        self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=f"{quote_sheet(sheet)}!A{row}",
            valueInputOption="USER_ENTERED",
            body={"values": [values]},
        ).execute()

    def _write_cells(self, sheet: str, row: int, cells: dict[int, object]) -> None:
        q = quote_sheet(sheet)
        data = [{"range": f"{q}!{col_letter(c)}{row}", "values": [[v]]} for c, v in cells.items()]
        self.service.spreadsheets().values().batchUpdate(
            spreadsheetId=self.spreadsheet_id, body={"valueInputOption": "USER_ENTERED", "data": data},
        ).execute()

    def _batch_update(self, requests: list[dict]) -> None:
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id, body={"requests": requests}).execute()


def _record(keys: list[str], row: list) -> dict:
    return dict(zip(keys, row + [""] * (len(keys) - len(row))))


def _new_sheet_id(sheets: dict[str, int]) -> int:
    used = set(sheets.values())
    while (sid := random.randint(1, 2_000_000_000)) in used:
        pass
    return sid
