"""Google Sheets API 를 호출해 프로젝트/작업을 관리한다."""
from __future__ import annotations

import random
from datetime import date, timedelta

from .layout import (
    COL, DASH_KEYS, DASHBOARD, DONE, TASK_KEYS, col_letter, dashboard_format_requests, dashboard_row,
    derive_status, next_task_id, parse_date, parse_progress, project_sheet_requests, quote_sheet, task_row,
    validate_project_name, validate_status,
)

DEFAULT_WEEKS = 12


class TrackerError(Exception):
    pass


class Tracker:
    def __init__(self, service, spreadsheet_id: str):
        """service: googleapiclient.discovery.build('sheets', 'v4', ...) 결과"""
        self.service = service
        self.spreadsheet_id = spreadsheet_id

    @property
    def url(self) -> str:
        return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit"

    @classmethod
    def create(cls, service, title: str) -> "Tracker":
        """새 스프레드시트를 만들고 대시보드를 구성한다."""
        res = service.spreadsheets().create(body={
            "properties": {"title": title, "locale": "ko_KR", "timeZone": "Asia/Seoul"},
            "sheets": [{"properties": {"sheetId": 0, "title": DASHBOARD}}],
        }).execute()
        tracker = cls(service, res["spreadsheetId"])
        tracker._batch_update(dashboard_format_requests(0))
        return tracker

    def ensure_dashboard(self) -> bool:
        """기존 스프레드시트에 대시보드가 없으면 만든다. 만들었으면 True."""
        sheets = self._sheet_map()
        if DASHBOARD in sheets:
            return False
        sheet_id = _new_sheet_id(sheets)
        self._batch_update([{"addSheet": {"properties": {"sheetId": sheet_id, "title": DASHBOARD}}}]
                           + dashboard_format_requests(sheet_id))
        return True

    # ---------- 프로젝트 ----------

    def add_project(self, name: str, owner: str | None = None, start: str | None = None,
                    end: str | None = None) -> dict:
        title = validate_project_name(name)
        start_d = parse_date(start, "시작일") if start else date.today()
        end_d = parse_date(end, "종료일") if end else start_d + timedelta(weeks=DEFAULT_WEEKS, days=-1)
        if end_d < start_d:
            raise TrackerError("종료일이 시작일보다 빠릅니다.")

        sheets = self._sheet_map()
        if DASHBOARD not in sheets:
            raise TrackerError(f"'{DASHBOARD}' 시트가 없습니다. 먼저 init 을 실행하세요.")
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
        rows = self._get_values(f"{quote_sheet(DASHBOARD)}!A2:I")
        return [dict(zip(DASH_KEYS, r + [""] * (len(DASH_KEYS) - len(r)))) for r in rows if r and r[0]]

    def remove_project(self, name: str) -> None:
        sheets = self._sheet_map()
        if name == DASHBOARD or name not in sheets:
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
                 note: str | None = None) -> dict:
        self._require_project(project)
        if not name:
            raise TrackerError("작업명이 필요합니다.")
        start_d = parse_date(start, "시작일") if start else None
        end_d = parse_date(end, "종료일") if end else None
        if start_d and end_d and end_d < start_d:
            raise TrackerError("종료일이 시작일보다 빠릅니다.")

        p = parse_progress(progress) if progress is not None else 0.0
        ids = self._column_values(project, "A")
        row = len(ids) + 1
        task = {
            "id": next_task_id(ids[1:]),
            "name": name,
            "owner": owner,
            "start": start_d.isoformat() if start_d else "",
            "end": end_d.isoformat() if end_d else "",
            "progress": p,
            "status": derive_status(p, status, "대기"),
            "note": note,
        }
        self._write_row(project, row, task_row(row, task))
        return task

    def update_task(self, project: str, task_id: str, **changes) -> dict:
        """changes: name, owner, start, end, progress, status, note (None 은 변경 안 함, '' 은 비움)"""
        self._require_project(project)
        task = next((t for t in self._read_tasks(project) if t["id"] == task_id), None)
        if task is None:
            raise TrackerError(f"{project} 에 작업 {task_id} 가 없습니다.")
        changes = {k: v for k, v in changes.items() if v is not None}

        cells: dict[str, object] = {}
        for key in ("name", "owner", "note"):
            if key in changes:
                cells[key] = changes[key]
        for key, label in (("start", "시작일"), ("end", "종료일")):
            if key in changes:
                cells[key] = parse_date(changes[key], label).isoformat() if changes[key] else ""

        s, e = cells.get("start", task["start"]), cells.get("end", task["end"])
        if s and e and e < s:
            raise TrackerError("종료일이 시작일보다 빠릅니다.")

        progress = parse_progress(changes["progress"]) if "progress" in changes else None
        if progress is not None:
            cells["progress"] = progress
        if "status" in changes:
            validate_status(changes["status"])
        status = derive_status(progress, changes.get("status"), task["status"])
        if status != task["status"]:
            cells["status"] = status
        if status == DONE and progress is None:
            cells["progress"] = 1  # 상태만 '완료'로 바꾸면 진척률도 100%로 맞춘다.

        if not cells:
            raise TrackerError("변경할 항목이 없습니다.")
        q = quote_sheet(project)
        data = [{"range": f"{q}!{col_letter(COL[k])}{task['row']}", "values": [[v]]} for k, v in cells.items()]
        self.service.spreadsheets().values().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"valueInputOption": "USER_ENTERED", "data": data},
        ).execute()

        if "progress" in cells:
            cells["progress"] = f"{round(float(cells['progress']) * 100)}%"
        return {**task, **cells}

    def list_tasks(self, project: str) -> list[dict]:
        self._require_project(project)
        return self._read_tasks(project)

    # ---------- 내부 ----------

    def _read_tasks(self, project: str) -> list[dict]:
        rows = self._get_values(f"{quote_sheet(project)}!A2:J")
        tasks = []
        for i, r in enumerate(rows):
            if r and r[0]:
                t = dict(zip(TASK_KEYS, r + [""] * (len(TASK_KEYS) - len(r))))
                t["row"] = i + 2
                tasks.append(t)
        return tasks

    def _require_project(self, project: str) -> None:
        if project == DASHBOARD or project not in self._sheet_map():
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

    def _batch_update(self, requests: list[dict]) -> None:
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id, body={"requests": requests}).execute()


def _new_sheet_id(sheets: dict[str, int]) -> int:
    used = set(sheets.values())
    while (sid := random.randint(1, 2_000_000_000)) in used:
        pass
    return sid
