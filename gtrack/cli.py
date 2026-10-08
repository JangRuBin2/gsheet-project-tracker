"""gtrack 명령줄 도구.

예)
  python -m gtrack init --title "프로젝트 관리"
  python -m gtrack project add "웹사이트 개편" --owner 홍길동 --start 2026-10-01 --end 2026-12-31
  python -m gtrack task add "웹사이트 개편" "요구사항 정리" --phase 기획 --owner 김철수 --start 2026-10-01 --end 2026-10-10
  python -m gtrack task update "웹사이트 개편" T-001 --progress 60
  python -m gtrack task import "웹사이트 개편" tasks.csv
  python -m gtrack raid add "웹사이트 개편" 리스크 "결제 모듈 교체 지연 가능" --impact 높음
  python -m gtrack project list
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import unicodedata
from pathlib import Path

from .layout import PRIORITIES, RAID_STATUSES, RAID_TYPES, STATUSES
from .tracker import Tracker, TrackerError

# 설정·인증 파일을 두는 폴더. 어느 폴더에서 실행해도 같은 파일을 쓴다.
# 기본은 이 저장소 루트(gtrack 패키지의 상위 폴더), GTRACK_HOME 환경변수로 바꿀 수 있다.
HOME = Path(os.environ.get("GTRACK_HOME") or Path(__file__).resolve().parent.parent)
CONFIG_FILE = HOME / ".gtrack.json"
IMPORT_FIELDS = ["phase", "name", "owner", "priority", "status", "progress", "start", "end", "after", "note"]
IMPORT_HEADER_ALIASES = {
    "단계": "phase", "작업명": "name", "담당자": "owner", "우선순위": "priority", "상태": "status",
    "진척률": "progress", "시작일": "start", "종료일": "end", "선행작업": "after", "비고": "note",
}


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


def _clip(s: str, n: int) -> str:
    out = ""
    for ch in s:
        if _width(out + ch) > n - 1:
            return out + "…"
        out += ch
    return out


def print_table(headers: list[str], rows: list[list], max_width: int = 40) -> None:
    rows = [[_clip(str(c), max_width) for c in r] for r in rows]
    widths = [max([_width(h)] + [_width(r[i]) for r in rows]) for i, h in enumerate(headers)]
    line = lambda cells: "  ".join(c + " " * (w - _width(c)) for c, w in zip(cells, widths)).rstrip()
    print(line(headers))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print(line(r))


def read_task_file(path: str) -> list[dict]:
    """CSV(UTF-8, 헤더 필수)에서 작업 목록을 읽는다. 헤더는 영문 키 또는 시트의 한글 헤더."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        tasks = []
        for raw in reader:
            t = {}
            for k, v in raw.items():
                key = IMPORT_HEADER_ALIASES.get((k or "").strip(), (k or "").strip())
                if key in IMPORT_FIELDS and v is not None and v.strip() != "":
                    t[key] = v.strip()
            if t:
                tasks.append(t)
    return tasks


def _task_fields(p: argparse.ArgumentParser) -> None:
    p.add_argument("--phase", help="단계 (예: 기획, 설계, 개발, 테스트, 배포)")
    p.add_argument("--owner", help="담당자")
    p.add_argument("--priority", choices=PRIORITIES, help="우선순위")
    p.add_argument("--start", help="시작일 YYYY-MM-DD")
    p.add_argument("--end", help="종료일 YYYY-MM-DD")
    p.add_argument("--progress", help="진척률 0~100")
    p.add_argument("--status", choices=STATUSES, help="상태")
    p.add_argument("--after", help="선행작업 ID (예: T-001,T-003)")
    p.add_argument("--note", help="비고")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gtrack", description="Google Sheets 프로젝트 일정·진척 관리")
    parser.add_argument("--credentials", help=f"인증 파일 경로 (기본: {HOME / 'credentials.json'})")
    parser.add_argument("--token", default=str(HOME / "token.json"), help="OAuth 토큰 저장 경로")
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
    p.add_argument("--open", action="store_true", help="완료되지 않은 작업만")
    p = task.add_parser("import", help="CSV 파일로 작업 일괄 추가")
    p.add_argument("project")
    p.add_argument("file", help="UTF-8 CSV. 헤더: 단계,작업명,담당자,우선순위,상태,진척률,시작일,종료일,선행작업,비고")

    raid = sub.add_parser("raid", help="리스크·가정·이슈·의존성·결정 로그").add_subparsers(dest="action", required=True)
    p = raid.add_parser("add", help="RAID 항목 추가")
    p.add_argument("project")
    p.add_argument("type", choices=RAID_TYPES)
    p.add_argument("text", help="내용")
    p.add_argument("--impact", choices=PRIORITIES, help="영향도 (기본 보통)")
    p.add_argument("--owner", help="담당자")
    p.add_argument("--action", dest="response", help="대응방안")
    p.add_argument("--due", help="기한 YYYY-MM-DD")
    p.add_argument("--related", help="관련 작업 ID (예: T-001,T-002)")
    p.add_argument("--status", choices=RAID_STATUSES, help="상태 (기본 열림)")
    p = raid.add_parser("update", help="RAID 항목 수정")
    p.add_argument("raid_id", help="예: R-001")
    p.add_argument("--type", choices=RAID_TYPES)
    p.add_argument("--text", help="내용")
    p.add_argument("--impact", choices=PRIORITIES)
    p.add_argument("--owner")
    p.add_argument("--action", dest="response", help="대응방안")
    p.add_argument("--due")
    p.add_argument("--related")
    p.add_argument("--status", choices=RAID_STATUSES)
    p = raid.add_parser("list", help="RAID 목록")
    p.add_argument("project", nargs="?")
    p.add_argument("--open", action="store_true", help="해결/종료되지 않은 항목만")

    git = sub.add_parser("git", help="git 저장소 커밋을 시트에 자동 반영").add_subparsers(dest="action", required=True)
    p = git.add_parser("link", help="저장소를 프로젝트에 연결하고 hook 설치")
    p.add_argument("--repo", required=True, help="git 저장소 경로")
    p.add_argument("--project", required=True, help="대상 프로젝트(시트) 이름")
    p.add_argument("--since", help="이 날짜 이후 커밋만 반영 (기본: 오늘)")
    p = git.add_parser("sync", help="새 커밋을 시트에 반영 (hook 이 자동 실행)")
    p.add_argument("--repo", help="저장소 경로 (생략 시 연결된 모든 저장소)")
    p.add_argument("--dry-run", action="store_true", help="시트를 바꾸지 않고 결과만 보기")
    p.add_argument("--quiet", action="store_true", help="hook 용: 브라우저 로그인 없이, 로그 형식으로 출력")
    p = git.add_parser("unlink", help="hook 제거 및 연결 해제")
    p.add_argument("--repo", required=True)
    git.add_parser("list", help="연결된 저장소 목록")
    return parser


def _print_tasks(tasks: list[dict]) -> None:
    print_table(
        ["ID", "단계", "작업명", "담당자", "우선", "상태", "진척", "계획", "차이", "시작일", "종료일", "남은일", "변경", "선행"],
        [[t["id"], t["phase"], t["name"], t["owner"], t["priority"], t["status"], t["progress"], t["planned"],
          t["variance"], t["start"], t["end"], t["remaining"], t["slip"], t["after"]] for t in tasks],
        max_width=36,
    )


def _python_exe() -> str:
    return sys.executable


def run_git(args, tracker: Tracker, service_factory) -> None:
    from datetime import date, datetime

    from . import gitsync

    cfg = _load_config()
    links = cfg.setdefault("git_sync", {})

    if args.action == "list":
        if not links:
            print("연결된 저장소가 없습니다.")
            return
        print_table(["저장소", "프로젝트", "since", "경로 규칙", "scope 규칙"],
                    [[k, v["project"], v.get("since", ""), len(v.get("paths", {})), len(v.get("scopes", {}))]
                     for k, v in links.items()], max_width=60)
        return

    if args.action == "link":
        key = gitsync.normalize_repo(args.repo)
        tracker.service = service_factory()
        tracker.list_tasks(args.project)  # 프로젝트 존재 확인
        tracker.ensure_base_sheets()
        entry = links.get(key, {})
        entry.update({"path": args.repo, "project": args.project,
                      "since": args.since or entry.get("since") or date.today().isoformat()})
        entry.setdefault("paths", {})
        entry.setdefault("scopes", {})
        links[key] = entry
        _save_config(cfg)
        for h in gitsync.install_hooks(args.repo, _python_exe(), str(HOME)):
            print(f"hook 설치: {h}")
        print(f"연결했습니다: {args.repo} → {args.project} (since {entry['since']})")
        print("작업 연결 규칙(paths/scopes)은 .gtrack.json 에서 편집합니다. skill/gtrack/references/GIT_SYNC.md 참고.")
        return

    if args.action == "unlink":
        for h in gitsync.uninstall_hooks(args.repo):
            print(f"hook 제거: {h}")
        if links.pop(gitsync.normalize_repo(args.repo), None) is not None:
            _save_config(cfg)
            print("연결을 해제했습니다.")
        return

    # sync
    targets = {gitsync.normalize_repo(args.repo): links.get(gitsync.normalize_repo(args.repo))} if args.repo else links
    if not targets or None in targets.values():
        raise TrackerError("연결된 저장소가 아닙니다. 먼저 'git link' 를 실행하세요.")
    tracker.service = service_factory(interactive=not args.quiet)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for key, rule in targets.items():
        repo = rule.get("path", key)
        with gitsync.file_lock(gitsync.git_dir(repo) / "gtrack-sync.lock"):
            commits = [gitsync.match_tasks(c, rule) for c in gitsync.read_commits(repo, rule.get("since"))]
            result = tracker.sync_commits(rule["project"], commits, dry_run=args.dry_run)
        prefix = f"[{stamp}] " if args.quiet else ""
        if not result:
            print(f"{prefix}{repo}: 새 커밋 없음")
            continue
        print(f"{prefix}{repo} → {rule['project']}: 커밋 {len(result)}건{' (dry-run)' if args.dry_run else ''}")
        for r in result:
            print(f"{prefix}  {r['commit']} {r['subject'][:60]} | 작업: {', '.join(r['tasks']) or '-'}"
                  f" | 반영: {', '.join(r['applied']) or '-'}")


def run(args, service_factory) -> None:
    if args.cmd == "init":
        service = service_factory()
        if args.existing:
            tracker = Tracker(service, args.existing)
            created = tracker.ensure_base_sheets()
            print(f"시트를 만들었습니다: {', '.join(created)}" if created else "기존 대시보드·RAID 시트를 사용합니다.")
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
    if args.cmd == "git":
        run_git(args, tracker, service_factory)
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
            print_table(["프로젝트", "PM", "시작일", "종료일", "작업", "완료", "진척", "기간경과", "일정차이", "지연", "차단",
                         "RAID", "다음 마감", "건강도"],
                        [[p["name"], p["owner"], p["start"], p["end"], p["tasks"], p["done"], p["progress"],
                          p["elapsed"], p["variance"], p["late"], p["blocked"], p["raid"], p["next_due"],
                          p["health"]] for p in projects])
        elif args.action == "remove":
            if not args.yes:
                answer = input(f"'{args.name}' 시트와 모든 작업을 삭제합니다. 계속할까요? [y/N] ")
                if answer.strip().lower() != "y":
                    print("취소했습니다.")
                    return
            tracker.remove_project(args.name)
            print(f"삭제했습니다: {args.name}")

    elif args.cmd == "task":
        fields = lambda: dict(owner=args.owner, start=args.start, end=args.end, progress=args.progress,
                              status=args.status, note=args.note, phase=args.phase, priority=args.priority,
                              after=args.after)
        if args.action == "add":
            t = tracker.add_task(args.project, args.name, **fields())
            print(f"작업 추가: {t['id']} {t['name']} [{t['status']}]")
        elif args.action == "update":
            t = tracker.update_task(args.project, args.task_id, name=args.name, **fields())
            print(f"수정 완료: {t['id']} {t['name']} 진척률 {t['progress']} [{t['status']}]")
        elif args.action == "import":
            tasks = tracker.add_tasks(args.project, read_task_file(args.file))
            print(f"작업 {len(tasks)}건 추가: {tasks[0]['id']} ~ {tasks[-1]['id']}" if tasks else "추가할 작업이 없습니다.")
        elif args.action == "list":
            tasks = tracker.list_tasks(args.project)
            if args.open:
                tasks = [t for t in tasks if t["status"] != "완료"]
            if not tasks:
                print("작업이 없습니다.")
                return
            _print_tasks(tasks)

    elif args.cmd == "raid":
        if args.action == "add":
            r = tracker.add_raid(args.project, args.type, args.text, impact=args.impact, owner=args.owner,
                                 action=args.response, due=args.due, related=args.related, status=args.status)
            print(f"RAID 추가: {r['id']} [{r['type']}/{r['impact']}] {r['text']}")
        elif args.action == "update":
            r = tracker.update_raid(args.raid_id, type=args.type, text=args.text, impact=args.impact,
                                    owner=args.owner, action=args.response, due=args.due, related=args.related,
                                    status=args.status)
            print(f"수정 완료: {r['id']} [{r['status']}] {r['text']}")
        elif args.action == "list":
            items = tracker.list_raid(args.project, open_only=args.open)
            if not items:
                print("RAID 항목이 없습니다.")
                return
            print_table(["ID", "프로젝트", "유형", "영향", "상태", "내용", "담당자", "대응방안", "기한", "관련"],
                        [[i["id"], i["project"], i["type"], i["impact"], i["status"], i["text"], i["owner"],
                          i["action"], i["due"], i["related"]] for i in items])


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)

    def service_factory(interactive: bool = True):
        from .auth import build_service

        creds = args.credentials or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or str(HOME / "credentials.json")
        return build_service(creds, args.token, interactive=interactive)

    try:
        run(args, service_factory)
    except (TrackerError, ValueError, FileNotFoundError, RuntimeError, TimeoutError) as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # googleapiclient.errors.HttpError 등
        if type(e).__name__ == "HttpError":
            print(f"Google API 오류: {e}", file=sys.stderr)
            return 1
        raise
    return 0
