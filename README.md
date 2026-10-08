# gsheet-project-tracker

Google Sheets API로 **프로젝트마다 시트를 만들고 일정과 진척 상황을 관리**하는 명령줄 도구입니다.

## 만들어지는 시트

**대시보드** (맨 앞 시트): 프로젝트당 한 줄
| 프로젝트 | PM | 시작일 | 종료일 | 작업수 | 완료 | 진척률 | 지연 | 상태 | 진행 바 | 시트 |
- 작업수·완료·진척률·지연·상태는 프로젝트 시트를 참조하는 **수식**이라, 시트에서 직접 고쳐도 바로 반영됩니다.
- 상태는 자동으로 계산됩니다: 대기 / 진행중 / 지연 / 완료. 지연은 빨간색, 완료는 초록색으로 표시됩니다.

**프로젝트 시트** (프로젝트마다 하나)
| ID | 작업명 | 담당자 | 시작일 | 종료일 | 기간(일) | 진척률 | 상태 | 남은일수 | 비고 | | 주간 간트 차트 → |
- 상태는 드롭다운(대기·진행중·완료·보류), 진척률은 0~100%, 날짜는 날짜만 입력되도록 검증합니다.
- 종료일이 지났는데 완료되지 않은 작업은 빨간색, 완료된 작업은 초록색으로 표시됩니다.
- 오른쪽 **간트 차트**: 프로젝트 기간을 주 단위로 나눠 각 작업 기간을 막대로 칠하고, 이번 주 열은 노란색으로 강조합니다.

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
python -m gtrack task add "웹사이트 개편" "요구사항 정리" --owner 김철수 --start 2026-10-01 --end 2026-10-10
python -m gtrack task add "웹사이트 개편" "디자인 시안" --owner 이영희 --start 2026-10-08 --end 2026-10-24 --note "2안 이상"

# 4) 진척 갱신
python -m gtrack task update "웹사이트 개편" T-001 --progress 60
python -m gtrack task update "웹사이트 개편" T-001 --progress 100    # 상태가 자동으로 '완료'
python -m gtrack task update "웹사이트 개편" T-002 --status 보류 --end 2026-10-31

# 5) 조회
python -m gtrack task list "웹사이트 개편"
python -m gtrack project list
python -m gtrack open                       # 스프레드시트 주소 출력

# 프로젝트 삭제 (시트와 대시보드 행 모두 삭제)
python -m gtrack project remove "웹사이트 개편"
```

### 상태 자동 변경 규칙
- 진척률 100% → `완료`
- 진척률이 0보다 크고 상태가 `대기`(또는 `완료`였다가 100% 미만으로 내려감) → `진행중`
- `--status 완료`만 주면 진척률도 100%로 맞춤
- `--status`를 직접 주면 그 값이 우선

시트에서 직접 셀을 고쳐도 됩니다. 단, 새 작업 행을 손으로 넣을 때는 기간·남은일수 수식을 위 행에서 복사하세요.

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
  tracker.py  Sheets API 호출 (프로젝트/작업 추가·수정·조회·삭제)
  auth.py     OAuth / 서비스 계정 인증
  cli.py      명령줄 인터페이스
tests/        단위 테스트
```
