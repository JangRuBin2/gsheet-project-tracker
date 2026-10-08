"""gtrack 명령줄 도구.

예)
  python -m gtrack init --title "프로젝트 관리"
  python -m gtrack project add "웹사이트 개편" --owner 홍길동 --start 2026-10-01 --end 2026-12-31
  python -m gtrack task add "웹사이트 개편" "요구사항 정리" --owner 김철수 --start 2026-10-01 --end 2026-10-10
  python -m gtrack task update "웹사이트 개편" T-001 --progress 60
  python -m gtrack task list "웹사이트 개편"
  python -m gtrack project list
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
from pathlib import Path

from .layout import STATUSES
from .tracker import Tracker, TrackerError

CONFIG_FILE = Path(".gtrack.json")


def _load_config() -> dict:
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8")) if CONFIG_FILE.exists() else {}


def _save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _spreadsheet_id(args) -> str:
    sid = args.id or os.environ.get("GTRACK_SPREADSHEET_ID") or _load_config().get("spreadsheet_id")
    if not sid:
        raise TrackerError("스프레드시트가 지정되지 않았습니다. 먼저 'init' 을 실행하거나 --id 를 주세요.")
    return sid


def _width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def print_table(headers: list[str], rows: list[list]) -> None:
    rows = [[str(c) for c in r] for r in rows]
    widths = [max([_width(h)] + [_width(r[i]) for r in rows]) for i, h in enumerate(headers)]
    line = lambda cells: "  ".join(c + " " * (w - _width(c)) for c, w in zip(cells, widths)).rstrip()
    print(line(headers))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print(line(r))


def _task_fields(p: argparse.ArgumentParser) -> None:
    p.add_argument("--owner", help="담당자")
    p.add_argument("--start", help="시작일 YYYY-MM-DD")
    p.add_argument("--end", help="종료일 YYYY-MM-DD")
    p.add_argument("--progress", help="진척률 0~100")
    p.add_argument("--status", choices=STATUSES, help="상태")
    p.add_argument("--note", help="비고")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gtrack", description="Google Sheets 프로젝트 일정·진척 관리")
    parser.add_argument("--credentials", help="credentials.json 경로 (기본: ./credentials.json)")
    parser.add_argument("--token", default="token.json", help="OAuth 토큰 저장 경로")
    parser.add_argument("--id", help="스프레드시트 ID (기본: .gtrack.json)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="관리용 스프레드시트 생성 또는 기존 시트 연결")
    p.add_argument("--title", default="프로젝트 관리", help="새로 만들 스프레드시트 제목")
    p.add_argument("--existing", metavar="SPREADSHEET_ID", help="새로 만들지 않고 기존 스프레드시트 사용")

    sub.add_parser("open", help="스프레드시트 URL 출력")

    proj = sub.add_parser("project", help="프로젝트 관리").add_subparsers(dest="action", required=True)
    p = proj.add_parser("add", help="프로젝트(시트) 추가")
    p.add_argument("name")
    p.add_argument("--owner", help="PM")
    p.add_argument("--start", help="시작일 YYYY-MM-DD (기본: 오늘)")
    p.add_argument("--end", help="종료일 YYYY-MM-DD (기본: 시작일+12주)")
    proj.add_parser("list", help="프로젝트 현황")
    p = proj.add_parser("remove", help="프로젝트 시트 삭제")
    p.add_argument("name")
    p.add_argument("--yes", action="store_true", help="확인 없이 삭제")

    task = sub.add_parser("task", help="작업 관리").add_subparsers(dest="action", required=True)
    p = task.add_parser("add", help="작업 추가")
    p.add_argument("project")
    p.add_argument("name")
    _task_fields(p)
    p = task.add_parser("update", help="작업 수정 (진척률·상태·일정 등)")
    p.add_argument("project")
    p.add_argument("task_id", help="예: T-001")
    p.add_argument("--name", help="작업명")
    _task_fields(p)
    p = task.add_parser("list", help="작업 목록")
    p.add_argument("project")
    return parser


def run(args, service_factory) -> None:
    if args.cmd == "init":
        service = service_factory()
        if args.existing:
            tracker = Tracker(service, args.existing)
            created = tracker.ensure_dashboard()
            print("대시보드 시트를 만들었습니다." if created else "기존 대시보드를 사용합니다.")
        else:
            tracker = Tracker.create(service, args.title)
            print(f"스프레드시트를 만들었습니다: {args.title}")
        _save_config({**_load_config(), "spreadsheet_id": tracker.spreadsheet_id})
        print(tracker.url)
        return

    tracker = Tracker(None, _spreadsheet_id(args))
    if args.cmd == "open":
        print(tracker.url)
        return
    tracker.service = service_factory()

    if args.cmd == "project":
        if args.action == "add":
            p = tracker.add_project(args.name, owner=args.owner, start=args.start, end=args.end)
            print(f"프로젝트 추가: {p['name']} ({p['start']} ~ {p['end']})")
            print(f"{tracker.url}#gid={p['sheet_id']}")
        elif args.action == "list":
            projects = tracker.list_projects()
            if not projects:
                print("프로젝트가 없습니다.")
                return
            print_table(["프로젝트", "PM", "시작일", "종료일", "작업", "완료", "진척률", "지연", "상태"],
                        [[p["name"], p["owner"], p["start"], p["end"], p["tasks"], p["done"], p["progress"],
                          p["late"], p["status"]] for p in projects])
        elif args.action == "remove":
            if not args.yes:
                answer = input(f"'{args.name}' 시트와 모든 작업을 삭제합니다. 계속할까요? [y/N] ")
                if answer.strip().lower() != "y":
                    print("취소했습니다.")
                    return
            tracker.remove_project(args.name)
            print(f"삭제했습니다: {args.name}")

    elif args.cmd == "task":
        if args.action == "add":
            t = tracker.add_task(args.project, args.name, owner=args.owner, start=args.start, end=args.end,
                                 progress=args.progress, status=args.status, note=args.note)
            print(f"작업 추가: {t['id']} {t['name']} [{t['status']}]")
        elif args.action == "update":
            t = tracker.update_task(args.project, args.task_id, name=args.name, owner=args.owner,
                                    start=args.start, end=args.end, progress=args.progress,
                                    status=args.status, note=args.note)
            print(f"수정 완료: {t['id']} {t['name']} 진척률 {t['progress']} [{t['status']}]")
        elif args.action == "list":
            tasks = tracker.list_tasks(args.project)
            if not tasks:
                print("작업이 없습니다.")
                return
            print_table(["ID", "작업명", "담당자", "시작일", "종료일", "진척률", "상태", "남은일수", "비고"],
                        [[t["id"], t["name"], t["owner"], t["start"], t["end"], t["progress"], t["status"],
                          t["remaining"], t["note"]] for t in tasks])


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)

    def service_factory():
        from .auth import build_service

        return build_service(args.credentials, args.token)

    try:
        run(args, service_factory)
    except (TrackerError, ValueError, FileNotFoundError) as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # googleapiclient.errors.HttpError 등
        if type(e).__name__ == "HttpError":
            print(f"Google API 오류: {e}", file=sys.stderr)
            return 1
        raise
    return 0
