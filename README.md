# gsheet-project-tracker

Google Sheets API로 **프로젝트마다 시트를 만들고 일정과 진척 상황을 관리**하는 명령줄 도구입니다.

## 만들어지는 시트

| 시트 | 내용 |
|---|---|
| **대시보드** | 프로젝트당 한 줄입니다. 작업수·완료·진척률·기간경과·일정차이·지연·차단·열린 RAID·다음 마감·**건강도(정상/주의/위험)**를 모두 수식으로 자동 집계합니다. |
| **프로젝트 시트** | 프로젝트마다 하나입니다. **입력 칸**(ID·단계·작업명·담당자·우선순위·상태·진척률·시작일·종료일·선행작업·비고)과 **자동 칸**(계획진척률·일정차이·남은일수·기준종료일·일정변경·완료일·기간), 주간 **간트 차트**로 구성됩니다. |
| **RAID** | 모든 프로젝트가 함께 쓰는 리스크·가정·이슈·의존성·결정 기록입니다. |

- 지연(빨강), 차단(주황), 완료(초록)를 색으로 구분합니다. 일정이 계획보다 5% 넘게 늦거나 기준일보다 밀리면 그 칸이 강조됩니다.
- 상태·우선순위는 드롭다운으로, 진척률·날짜는 입력 검증으로 잘못된 값을 막습니다.
- 양식을 이렇게 설계한 근거와 건강도 기준, 주간 운영 루틴은 **[docs/PM_GUIDE.md](docs/PM_GUIDE.md)**에 정리했습니다.

## 설치

```powershell
python -m pip install -r requirements.txt
```

## Google 인증 설정 (최초 1회)

👉 **[docs/SETUP.md](docs/SETUP.md)** 를 따라 하세요. 단계는 다음과 같습니다.
- Sheets API 사용 설정
- OAuth 동의 화면 설정
- **테스트 사용자 추가**
- 데스크톱 앱 클라이언트 JSON 받기 → `credentials.json`으로 저장
- 첫 로그인

자주 나는 오류(403 access_denied, 7일 후 재로그인 등)와 다른 사람과 함께 쓰는 방법도 같은 문서에 있습니다.

🔒 `credentials.json`, `token.json` 등 비밀 파일 관리와 유출 시 대처는 **[docs/SECURITY.md](docs/SECURITY.md)** 를 참고하세요.

## Claude Code 스킬

`.claude/skills/gtrack/SKILL.md`에 스킬이 들어 있습니다. 이 폴더에서 Claude Code를 실행하고 다음처럼 말로 요청하면 알맞은 명령을 대신 실행합니다.
- "웹사이트 개편에 디자인 작업 추가해줘, 10/20까지"
- "T-003 완료 처리해줘"
- "프로젝트 현황 보여줘"

`/gtrack`으로 직접 부를 수도 있습니다.

## 사용법

```powershell
# 1) 관리용 스프레드시트 만들기 (ID는 .gtrack.json 에 저장됨)
python -m gtrack init --title "2026 프로젝트 관리"
#    또는 기존 스프레드시트 연결 (URL의 /d/ 와 /edit 사이 문자열)
python -m gtrack init --existing 1AbC...xyz

# 2) 프로젝트 추가 → 시트가 생성되고 대시보드에 한 줄 추가됨
#    --start 생략 시 오늘, --end 생략 시 시작일+12주
python -m gtrack project add "웹사이트 개편" --owner 홍길동 --start 2026-10-01 --end 2026-12-31

# 3) 작업 추가 (ID는 T-001, T-002 … 자동 부여)
python -m gtrack task add "웹사이트 개편" "요구사항 정리" --phase 1.기획 --owner 김철수 --priority 높음 --start 2026-10-01 --end 2026-10-10
python -m gtrack task add "웹사이트 개편" "디자인 시안" --phase 2.디자인 --owner 이영희 --start 2026-10-08 --end 2026-10-24 --after T-001
#    여러 건은 CSV로 한 번에 (UTF-8, 헤더: 단계,작업명,담당자,우선순위,상태,진척률,시작일,종료일,선행작업,비고)
python -m gtrack task import "웹사이트 개편" tasks.csv

# 4) 진척 갱신
python -m gtrack task update "웹사이트 개편" T-001 --progress 60
python -m gtrack task update "웹사이트 개편" T-001 --progress 100    # 자동으로 '완료' + 완료일 기록
python -m gtrack task update "웹사이트 개편" T-002 --status 차단 --end 2026-10-31   # 기준종료일은 유지됨

# 5) 리스크·이슈 (RAID)
python -m gtrack raid add "웹사이트 개편" 리스크 "결제 모듈 교체 지연 가능" --impact 높음 --action "대체 PG 검토" --related T-002
python -m gtrack raid update R-001 --status 해결

# 6) 조회
python -m gtrack project list                       # 대시보드 (건강도 포함)
python -m gtrack task list "웹사이트 개편" --open    # 미완료 작업만
python -m gtrack raid list --open                    # 열린 RAID
python -m gtrack open                                # 스프레드시트 주소

# 프로젝트 삭제 (시트와 대시보드 행 모두 삭제)
python -m gtrack project remove "웹사이트 개편"
```

### 상태 자동 변경 규칙
- 진척률 100% → `완료`
- 진척률이 0보다 크고 상태가 `대기`(또는 `완료`였다가 100% 미만으로 내려감) → `진행중`
- `--status 완료`만 주면 진척률도 100%로 맞춤
- `--status`를 직접 주면 그 값이 우선

시트에서 직접 셀을 고쳐도 됩니다. 단, 새 작업 행을 손으로 넣을 때는 회색 헤더(자동) 칸의 수식을 위 행에서 복사하세요.

## PC를 켤 때 자동으로 열기 (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1              # 등록: Claude Code 로 열기 (기본)
powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1 -Mode gtrack # 등록: gtrack 대시보드로 열기
powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1 -Uninstall   # 해제
```
- **claude 모드**: 로그인하면 이 폴더에서 Claude Code가 열립니다. 저장소의 `gtrack` 스킬이 함께 로드되므로 "프로젝트 현황 보여줘"처럼 바로 요청할 수 있습니다.
- **gtrack 모드**: 대시보드와 열린 RAID 목록을 보여줍니다.
- 어느 모드든 열린 창에서는 `python -m gtrack` 대신 **`gtrack`**만 입력해도 됩니다. Claude Code를 종료한 뒤에도 마찬가지입니다.

수동으로 열 때는 `scripts\start-gtrack.ps1`을 dot-source 합니다: `. .\scripts\start-gtrack.ps1 [-Claude]`

## 공통 옵션

| 옵션 | 설명 |
|---|---|
| `--credentials 경로` | 인증 파일 경로 (기본 `credentials.json`, 또는 `GOOGLE_APPLICATION_CREDENTIALS`) |
| `--token 경로` | OAuth 토큰 저장 위치 (기본 `token.json`) |
| `--id 스프레드시트ID` | `.gtrack.json` 대신 사용할 스프레드시트 (또는 `GTRACK_SPREADSHEET_ID`) |

공통 옵션은 명령 앞에 씁니다: `python -m gtrack --id 1AbC... project list`

## 코드에서 직접 사용

```python
from gtrack.auth import build_service
from gtrack import Tracker

t = Tracker(build_service(), "스프레드시트ID")
t.add_project("모바일 앱", owner="박PM", start="2026-11-01", end="2027-02-28")
t.add_task("모바일 앱", "API 설계", owner="최개발", start="2026-11-01", end="2026-11-14")
t.update_task("모바일 앱", "T-001", progress="40")
print(t.list_projects())
```

## 테스트

```powershell
python -m pytest
```
실제 Google 계정 없이 메모리 기반 가짜 Sheets API(`tests/fake_sheets.py`)로 동작을 검증합니다.

## 구조

```
gtrack/
  layout.py   시트 구조·수식·서식 요청을 만드는 순수 함수
  tracker.py  Sheets API 호출 (프로젝트/작업/RAID 추가·수정·조회·삭제)
  auth.py     OAuth / 서비스 계정 인증
  cli.py      명령줄 인터페이스
tests/        단위 테스트
```
