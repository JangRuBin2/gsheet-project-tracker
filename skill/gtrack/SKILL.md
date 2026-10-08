---
name: gtrack
description: 구글 시트 프로젝트 일정·진척 관리 (전역 스킬, 어느 폴더에서나 사용). 프로젝트(시트) 추가·삭제, 작업 추가·일괄 등록, 진척률·상태·일정·선행작업 수정, 리스크·이슈(RAID) 기록, git 커밋 자동 반영, 프로젝트 현황·건강도 조회를 gtrack CLI로 처리한다. "프로젝트 추가해줘", "작업 넣어줘", "진척률 60%로", "T-003 완료 처리", "지연된 작업 보여줘", "프로젝트 현황", "일정 바꿔줘", "리스크 등록해줘", "이슈 해결 처리", "시트 업데이트해줘" 같은 요청이나 /gtrack 호출 시 사용.
---

# gtrack — 구글 시트 프로젝트 관리

`gtrack` CLI로 구글 스프레드시트의 프로젝트·작업·RAID를 관리한다.
**어느 폴더에서 실행해도** 같은 스프레드시트와 인증 파일을 쓴다. 이 파일들은 gtrack 설치 폴더에 있다.

이 스킬 폴더의 `references/`에 문서가 있다. 필요할 때 읽는다.
| 문서 | 내용 |
|---|---|
| `references/PM_GUIDE.md` | 양식의 각 열 의미, 건강도 기준, 주간 운영 루틴 |
| `references/GIT_SYNC.md` | 커밋 자동 반영 규칙과 `.gtrack.json`의 `git_sync` 형식 |
| `references/SETUP.md` | Google 인증 설정(JSON 파일, 테스트 사용자 추가), 자주 나는 오류 |
| `references/SECURITY.md` | 비밀 파일 관리, 유출 시 대처 |

## 실행 방법

```
gtrack <명령>
```
- `gtrack`을 찾지 못하면(PATH가 갱신되기 전에 연 셸) `& "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts\gtrack.exe" <명령>`을 쓴다.
- 설치 폴더는 `gtrack --help`의 `--credentials` 기본값 경로로 알 수 있다. 설정 파일 `.gtrack.json`도 그 폴더에 있다.

## 명령어

| 하려는 일 | 명령 |
|---|---|
| 프로젝트 현황(대시보드) | `gtrack project list` |
| 프로젝트 추가 | `gtrack project add "<이름>" [--owner PM] [--start YYYY-MM-DD] [--end YYYY-MM-DD]` |
| 프로젝트 삭제 | `gtrack project remove "<이름>" --yes` |
| 작업 목록 | `gtrack task list "<프로젝트>" [--open]` |
| 작업 추가 | `gtrack task add "<프로젝트>" "<작업명>" [--phase] [--owner] [--priority 높음/보통/낮음] [--start] [--end] [--progress 0-100] [--status] [--after T-001,T-002] [--note]` |
| 작업 수정 | `gtrack task update "<프로젝트>" T-001 [--name] [위와 같은 옵션]` |
| 작업 일괄 추가 | `gtrack task import "<프로젝트>" <파일.csv>` |
| RAID 추가 | `gtrack raid add "<프로젝트>" <리스크/가정/이슈/의존성/결정> "<내용>" [--impact 높음/보통/낮음] [--owner] [--action 대응방안] [--due] [--related T-001]` |
| RAID 수정 | `gtrack raid update R-001 [--status 열림/대응중/해결/종료] [--action] [--impact] [--owner] [--due] [--related] [--text] [--type]` |
| RAID 목록 | `gtrack raid list ["<프로젝트>"] [--open]` |
| git 저장소 연결 (커밋 자동 반영) | `gtrack git link --repo <경로> --project "<프로젝트>"` |
| 커밋 지금 반영 / 미리보기 | `gtrack git sync [--repo <경로>] [--dry-run]` |
| 연결 목록 / 해제 | `gtrack git list` / `gtrack git unlink --repo <경로>` |
| 시트 주소 | `gtrack open` |
| 시트 새로 만들기/연결 | `gtrack init --title "<제목>"` / `gtrack init --existing <ID>` |

- 상태 값은 `대기`, `진행중`, `차단`, `완료`, `보류` 중 하나다. '지연'은 입력하는 값이 아니다. 종료일이 지났는데 끝나지 않으면 자동으로 지연으로 표시된다.
- 진척률을 100으로 하면 상태가 자동으로 `완료`가 되고 완료일이 기록된다. `--status 완료`만 주면 진척률도 100%가 된다.
- 종료일을 바꿔도 **기준종료일**은 그대로 남는다. 차이는 '일정변경(일)'에 자동으로 표시된다. 일정이 밀리면 종료일만 바꾼다.
- 프로젝트의 `--start`를 생략하면 오늘, `--end`를 생략하면 시작일+12주가 된다.
- 날짜는 항상 `YYYY-MM-DD`로 쓴다. "다음 주 금요일"처럼 상대적인 날짜는 오늘 날짜를 기준으로 계산해서 넣는다.
- 날짜를 모르는 작업은 날짜를 지어내지 말고 비워 둔다. 사용자에게 일정을 받아 나중에 채운다.
- 작업이 5건 이상이면 `task add`를 반복하지 말고 CSV를 만들어 `task import`로 넣는다.
  - CSV는 UTF-8이고 헤더는 `단계,작업명,담당자,우선순위,상태,진척률,시작일,종료일,선행작업,비고`다.
  - 선행작업 ID는 시트에 이미 있는 마지막 ID 다음 번호부터 순서대로 매겨지는 것을 계산해서 적는다.
  - CSV는 현재 작업 중인 저장소가 아니라 임시 폴더(scratchpad)에 만든다.
- 리스크·이슈·외부 의존성·중요한 결정이 대화에 나오면 RAID 등록을 제안한다.
- 공통 옵션(`--id`, `--credentials`)은 하위 명령 **앞에** 쓴다. 예: `gtrack --id <ID> project list`

## git 커밋 연동

- 연결된 저장소(`gtrack git list`)의 커밋은 hook이 자동으로 반영한다.
  - 커밋 로그 시트에 기록된다.
  - 대기→진행중, 비어 있는 시작일, 완료 표시(`T-018 완료`)가 반영된다.
  - 진척률은 자동으로 바뀌지 않는다.
- 연결된 저장소에서 일하다가 "시트 업데이트해줘"나 "작업 상태 맞춰줘"를 요청받으면:
  1. `gtrack git sync`를 실행한다.
  2. `gtrack task list "<프로젝트>" --open`과 최근 커밋을 보고 진척률·상태 갱신을 **제안**한다.
  3. 사용자가 동의하면 반영한다.
- 연결된 저장소에서 커밋할 때 해당 작업 ID를 알면 커밋 메시지에 `T-xxx`를 넣는다. 작업을 끝낸 커밋이면 `T-xxx 완료`를 넣는다. 그 저장소의 커밋 메시지 규칙이 우선이다.
- 커밋과 작업을 연결하는 규칙(paths/scopes)은 설치 폴더 `.gtrack.json`의 `git_sync`에 있다. 새 작업을 추가하면 해당 경로·scope 규칙도 추가한다. 형식은 `references/GIT_SYNC.md`에 있다.

## 작업 절차

1. 요청한 일을 명령으로 바꾼다. 작업 ID(T-xxx)를 모르면 먼저 `task list`로 확인한다. 작업명만으로 추측하지 않는다.
2. 여러 건이면 명령을 이어서 실행한다. PowerShell에서는 `;`로 연결한다.
3. 마지막에 `task list`나 `project list`로 결과를 확인하고, 바뀐 내용을 짧게 요약해서 알린다.
4. **`project remove`는 되돌릴 수 없다.** 사용자가 이번 대화에서 그 프로젝트의 삭제를 분명히 요청했을 때만 `--yes`를 붙여 실행한다.
5. 프로젝트 이름에는 `[ ] * ? : / \ '`를 쓸 수 없다. 들어 있으면 사용자에게 다른 이름을 제안한다.

## 보안 규칙 (반드시 지킬 것)

- `credentials.json`, `client_secret*.json`, `token.json`, 서비스 계정 키 파일의 **내용을 읽거나 출력하거나 대화에 붙이지 않는다.** 필요하면 존재 여부(`Test-Path`)나 JSON 최상위 키 이름만 확인한다.
- 이 파일들을 어떤 저장소에도 `git add`하지 않는다. `git add -f`도 쓰지 않는다.
- gtrack 저장소에 커밋하기 전에는 `python -m pytest`로 `tests/test_secrets.py`를 통과시킨다.
- 토큰이나 secret을 명령줄 인자나 환경변수로 넘기는 방식을 새로 만들지 않는다.

## 오류가 날 때

| 메시지 | 조치 |
|---|---|
| `인증 파일이 없습니다` / `데스크톱 앱 유형이 아닙니다` | `references/SETUP.md`의 4단계를 안내한다. |
| `403 access_denied`, "인증 절차를 완료하지 않았습니다" | 로그인 계정을 테스트 사용자로 추가해야 한다. `references/SETUP.md`의 3단계를 안내한다. |
| 브라우저 로그인이 필요함 (첫 실행, 7일 후 토큰 만료) | 명령을 백그라운드로 실행하고 `$env:PYTHONUNBUFFERED=1`로 출력 버퍼링을 끈다. 출력된 인증 URL을 사용자에게 전달하고, 로그인을 마칠 때까지 기다린다. 로그인 후 `gtrack git sync`로 밀린 커밋을 반영한다. |
| `스프레드시트가 지정되지 않았습니다` | `init`을 먼저 실행하거나 `--id`를 준다. |
| `Google API 오류: 403 ... permission` | 로그인 계정에 그 시트의 편집 권한이 없다. 사용자에게 공유 설정을 확인하게 한다. |
