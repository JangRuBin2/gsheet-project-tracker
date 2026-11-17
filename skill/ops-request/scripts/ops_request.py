"""운영 개선 요청서(구글 시트) 행 추가 · 회신 · 스크린샷 업로드 도구.

시트 양식(「요청 목록」 탭):
  A=No(수식) B..M=① 운영팀 작성  N=작성 점검(수식)  O..S=② 개발팀 작성  T,U=③ 운영팀 확인
A · N 열은 수식이므로 절대 쓰지 않는다. T · U 열은 운영팀 칸이라 쓰지 않는다.

인증: gtrack 설치 폴더의 credentials.json 을 쓰고, 토큰은 별도 파일(token_ops.json)에
spreadsheets + drive.file 범위로 저장한다. gtrack 의 token.json 은 건드리지 않는다.
drive.file 은 이 앱이 만든 파일만 볼 수 있는 최소 권한이다.

사용:
  python ops_request.py show
  python ops_request.py add   <row.json>            # 빈 행 첫 칸에 추가 (+ shots 업로드)
  python ops_request.py reply <No> <reply.json>     # O..S 회신 칸만 갱신
  python ops_request.py shots <No> <이미지...> [--force]
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path

DEFAULT_SID = "1V-Ducwkd00AyBml_UxEWL6NR32fcZ70bdRloicsz3g4"
SHEET = "요청 목록"
FIRST_ROW = 6          # 5행은 작성 예시
PARENT_FOLDER = "운영 개선 요청 스크린샷"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]
GTRACK_DIR = Path(os.environ.get("GTRACK_HOME", Path.home() / "gsheet-project-tracker" / "gsheet-project-tracker"))

# B..M (운영팀 칸) 키 순서
REQ_KEYS = ["요청일", "요청자", "서비스", "메뉴 경로", "화면 URL", "사용 환경", "유형", "긴급도",
            "현상", "재현 방법", "기대 결과", "스크린샷"]
# O..S (개발팀 칸) 키 순서
DEV_KEYS = ["담당자", "상태", "회신", "완료 예정일", "운영 반영일"]
# 드롭다운 허용값은 「목록」 탭 열에서 읽는다
LIST_COLS = {"서비스": 0, "사용 환경": 1, "유형": 2, "긴급도": 3, "상태": 4}


def _creds():
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    key = GTRACK_DIR / "credentials.json"
    token = GTRACK_DIR / "token_ops.json"
    if not key.exists():
        sys.exit(f"인증 파일이 없습니다: {key} (gtrack 의 references/SETUP.md 참고)")
    creds = None
    if token.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token), SCOPES)
        except (ValueError, json.JSONDecodeError):
            creds = None
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(token, creds)
            return creds
        except RefreshError:
            print("로그인이 만료되어 다시 인증합니다.", flush=True)
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = InstalledAppFlow.from_client_secrets_file(str(key), SCOPES).run_local_server(
        port=0, open_browser=True,
        authorization_prompt_message="브라우저에서 로그인하세요 (열리지 않으면 이 주소를 직접 여세요):\n{url}",
        success_message="인증이 완료되었습니다. 이 창을 닫아도 됩니다.",
    )
    _save_token(token, creds)
    return creds


def _save_token(path: Path, creds) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(creds.to_json())


class Ops:
    def __init__(self, sid: str):
        from googleapiclient.discovery import build

        creds = _creds()
        self.sid = sid
        self.values = build("sheets", "v4", credentials=creds, cache_discovery=False).spreadsheets().values()
        self._drive_creds = creds
        self._drive = None

    @property
    def drive(self):
        if self._drive is None:
            from googleapiclient.discovery import build

            self._drive = build("drive", "v3", credentials=self._drive_creds, cache_discovery=False)
        return self._drive

    # ---------- sheet ----------
    def rows(self):
        vals = self.values.get(spreadsheetId=self.sid, range=f"'{SHEET}'!A{FIRST_ROW}:U").execute().get("values", [])
        return [(FIRST_ROW + i, r) for i, r in enumerate(vals)]

    def allowed(self):
        vals = self.values.get(spreadsheetId=self.sid, range="'목록'!A3:F").execute().get("values", [])
        out = {}
        for k, c in LIST_COLS.items():
            out[k] = [r[c] for r in vals if len(r) > c and r[c]]
        return out

    def check_choices(self, data: dict):
        allowed = self.allowed()
        bad = [f"{k}={data[k]!r} (허용: {', '.join(allowed[k])})"
               for k in allowed if data.get(k) and data[k] not in allowed[k]]
        if bad:
            sys.exit("드롭다운에 없는 값: " + "; ".join(bad))

    def row_of(self, no: int) -> int:
        row = FIRST_ROW + no - 1
        r = self.values.get(spreadsheetId=self.sid, range=f"'{SHEET}'!B{row}").execute().get("values", [])
        if not r or not r[0] or not r[0][0]:
            sys.exit(f"No {no} (시트 {row}행)이 비어 있습니다.")
        return row

    def next_empty_row(self) -> int:
        for row, r in self.rows():
            if not any(c for c in r[1:13] if c) and not any(c for c in r[14:19] if c):
                return row
        return FIRST_ROW + len(self.rows())

    def write(self, ranges: list[tuple[str, list]]):
        data = [{"range": f"'{SHEET}'!{a1}", "values": [vals]} for a1, vals in ranges]
        self.values.batchUpdate(spreadsheetId=self.sid,
                                body={"valueInputOption": "USER_ENTERED", "data": data}).execute()

    # ---------- drive ----------
    def _folder(self, name: str, parent: str | None):
        q = [f"name = '{name.replace(chr(39), chr(92) + chr(39))}'",
             "mimeType = 'application/vnd.google-apps.folder'", "trashed = false"]
        if parent:
            q.append(f"'{parent}' in parents")
        found = self.drive.files().list(q=" and ".join(q), fields="files(id,webViewLink)").execute().get("files", [])
        if found:
            return found[0]
        body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent:
            body["parents"] = [parent]
        return self.drive.files().create(body=body, fields="id,webViewLink").execute()

    def upload_shots(self, no: int, files: list[str]) -> tuple[str, int]:
        from googleapiclient.http import MediaFileUpload

        paths = [Path(f) for f in files]
        missing = [str(p) for p in paths if not p.is_file()]
        if missing:
            sys.exit(f"파일이 없습니다: {missing}")
        parent = self._folder(PARENT_FOLDER, None)
        folder = self._folder(f"No-{no}", parent["id"])
        existing = {f["name"] for f in self.drive.files().list(
            q=f"'{folder['id']}' in parents and trashed = false", fields="files(name)").execute().get("files", [])}
        n = 0
        for p in paths:
            if p.name in existing:
                print(f"  건너뜀(이미 있음): {p.name}")
                continue
            mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            self.drive.files().create(body={"name": p.name, "parents": [folder["id"]]},
                                      media_body=MediaFileUpload(str(p), mimetype=mime), fields="id").execute()
            print(f"  업로드: {p.name}")
            n += 1
        return folder["webViewLink"], len(existing) + n


def _link_formula(url: str, count: int) -> str:
    return f'=HYPERLINK("{url}", "캡처 {count}장 (드라이브 폴더)")'


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_show(ops: Ops, _):
    for row, r in ops.rows():
        if not any(r[1:]):
            continue
        r = r + [""] * (21 - len(r))
        print(f"No {r[0]} (행 {row}) | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[7]}/{r[8]} | 점검={r[13]} | "
              f"상태={r[15]} | 반영일={r[18]} | 확인={r[19]}")
        print(f"    현상: {r[9][:80]}")


def cmd_add(ops: Ops, a):
    data = _load(a.json)
    missing = [k for k in ["요청일", "요청자", "서비스", "메뉴 경로", "사용 환경", "유형", "긴급도", "현상", "기대 결과"]
               if not data.get(k)]
    if missing:
        sys.exit(f"필수 값 누락: {missing}")
    ops.check_choices(data)
    row = ops.next_empty_row()
    no = row - FIRST_ROW + 1
    shots = data.get("shots") or []
    if shots:
        url, cnt = ops.upload_shots(no, shots)
        data["스크린샷"] = _link_formula(url, cnt)
    ranges = [(f"B{row}:M{row}", [data.get(k, "") for k in REQ_KEYS])]
    if any(data.get(k) for k in DEV_KEYS):
        ranges.append((f"O{row}:S{row}", [data.get(k, "") for k in DEV_KEYS]))
    ops.write(ranges)
    print(f"추가: No {no} (시트 {row}행)")


def cmd_reply(ops: Ops, a):
    data = _load(a.json)
    ops.check_choices(data)
    row = ops.row_of(a.no)
    cols = dict(zip(DEV_KEYS, "OPQRS"))
    ranges = [(f"{cols[k]}{row}", [data[k]]) for k in DEV_KEYS if k in data]
    if not ranges:
        sys.exit(f"갱신할 값이 없습니다. 키: {DEV_KEYS}")
    ops.write(ranges)
    print(f"회신 갱신: No {a.no} — {', '.join(k for k in DEV_KEYS if k in data)}")


def cmd_shots(ops: Ops, a):
    row = ops.row_of(a.no)
    cur = ops.values.get(spreadsheetId=ops.sid, range=f"'{SHEET}'!M{row}",
                         valueRenderOption="FORMULA").execute().get("values", [])
    cur = cur[0][0] if cur and cur[0] else ""
    if cur and "drive.google.com" not in cur and not a.force:
        sys.exit(f"스크린샷 칸에 이미 다른 값이 있습니다: {cur[:60]!r} (덮어쓰려면 --force)")
    url, cnt = ops.upload_shots(a.no, a.files)
    ops.write([(f"M{row}", [_link_formula(url, cnt)])])
    print(f"스크린샷 링크 기록: No {a.no} → {url} ({cnt}장)")


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="운영 개선 요청서 시트 도구")
    p.add_argument("--id", default=DEFAULT_SID, help="스프레드시트 ID")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    s = sub.add_parser("add"); s.add_argument("json")
    s = sub.add_parser("reply"); s.add_argument("no", type=int); s.add_argument("json")
    s = sub.add_parser("shots"); s.add_argument("no", type=int); s.add_argument("files", nargs="+")
    s.add_argument("--force", action="store_true")
    a = p.parse_args()
    try:
        ops = Ops(a.id)
        {"show": cmd_show, "add": cmd_add, "reply": cmd_reply, "shots": cmd_shots}[a.cmd](ops, a)
    except Exception as e:  # noqa: BLE001 — API 오류를 사람이 읽을 수 있게
        from googleapiclient.errors import HttpError

        if isinstance(e, HttpError):
            msg = str(e)
            if "accessNotConfigured" in msg or "has not been used" in msg:
                sys.exit("Google Drive API 가 꺼져 있습니다. Cloud Console > API 및 서비스 > 라이브러리에서 "
                         "'Google Drive API' 를 사용 설정하세요.\n" + msg)
            sys.exit(f"Google API 오류: {msg}")
        raise


if __name__ == "__main__":
    main()
