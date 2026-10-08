---
name: gtrack
description: 구글 시트 프로젝트 일정·진척 관리. 프로젝트(시트) 추가·삭제, 작업 추가, 진척률·상태·일정 수정, 프로젝트 현황·작업 목록 조회를 gtrack CLI로 처리한다. "프로젝트 추가해줘", "작업 넣어줘", "진척률 60%로", "T-003 완료 처리", "지연된 작업 보여줘", "프로젝트 현황", "일정 바꿔줘" 같은 요청이나 /gtrack 호출 시 사용.
---

# gtrack — 구글 시트 프로젝트 관리

이 저장소의 `gtrack` CLI로 구글 스프레드시트의 프로젝트/작업을 관리한다.
모든 명령은 **저장소 루트**(README.md가 있는 폴더)에서 실행한다.

## 실행 방법

```
python -m gtrack <명령>
```
`python`을 찾지 못하면(Windows에서 Store 별칭만 있는 경우) `py -m gtrack` 또는
`& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m gtrack`을 쓴다.

## 명령어

| 하려는 일 | 명령 |
|---|---|
| 프로젝트 현황(대시보드) | `python -m gtrack project list` |
| 프로젝트 추가 | `python -m gtrack project add "<이름>" [--owner PM] [--start YYYY-MM-DD] [--end YYYY-MM-DD]` |
| 프로젝트 삭제 | `python -m gtrack project remove "<이름>" --yes` |
| 작업 목록 | `python -m gtrack task list "<프로젝트>"` |
| 작업 추가 | `python -m gtrack task add "<프로젝트>" "<작업명>" [--owner] [--start] [--end] [--progress 0-100] [--status] [--note]` |
| 작업 수정 | `python -m gtrack task update "<프로젝트>" T-001 [--name] [--owner] [--start] [--end] [--progress] [--status] [--note]` |
| 시트 주소 | `python -m gtrack open` |
| 시트 새로 만들기/연결 | `python -m gtrack init --title "<제목>"` / `python -m gtrack init --existing <ID>` |

- 상태 값은 `대기`, `진행중`, `완료`, `보류` 중 하나다. '지연'은 입력하는 값이 아니다. 종료일이 지났는데 끝나지 않으면 자동으로 지연으로 표시된다.
- 진척률을 100으로 하면 상태가 자동으로 `완료`가 된다. `--status 완료`만 주면 진척률도 100%가 된다.
- 프로젝트의 `--start`를 생략하면 오늘, `--end`를 생략하면 시작일+12주가 된다.
- 날짜는 항상 `YYYY-MM-DD`로 쓴다. "다음 주 금요일"처럼 상대적인 날짜는 오늘 날짜를 기준으로 계산해서 넣는다.
- 공통 옵션(`--id`, `--credentials`)은 하위 명령 **앞에** 쓴다. 예: `python -m gtrack --id <ID> project list`

## 작업 절차

1. 요청한 일을 명령으로 바꾼다. 작업 ID(T-xxx)를 모르면 먼저 `task list`로 확인한다. 작업명만으로 추측하지 않는다.
2. 여러 건이면 명령을 이어서 실행한다. PowerShell에서는 `;`로 연결한다.
3. 마지막에 `task list`나 `project list`로 결과를 확인하고, 바뀐 내용을 짧게 요약해서 알린다.
4. **`project remove`는 되돌릴 수 없다.** 사용자가 이번 대화에서 그 프로젝트의 삭제를 분명히 요청했을 때만 `--yes`를 붙여 실행한다.
5. 프로젝트 이름에는 `[ ] * ? : / \ '`를 쓸 수 없다. 들어 있으면 사용자에게 다른 이름을 제안한다.

## 보안 규칙 (반드시 지킬 것)

- `credentials.json`, `client_secret*.json`, `token.json`, 서비스 계정 키 파일의 **내용을 읽거나 출력하거나 대화에 붙이지 않는다.** 필요하면 존재 여부(`Test-Path`)나 JSON 최상위 키 이름만 확인한다.
- 이 파일들을 `git add`하지 않는다. `git add -f`도 쓰지 않는다. 커밋 전에는 `python -m pytest`로 `tests/test_secrets.py`를 통과시킨다.
- 토큰이나 secret을 명령줄 인자나 환경변수로 넘기는 방식을 새로 만들지 않는다.

## 오류가 날 때

| 메시지 | 조치 |
|---|---|
| `인증 파일이 없습니다` / `데스크톱 앱 유형이 아닙니다` | 사용자에게 `docs/SETUP.md`의 4단계를 안내한다. |
| `403 access_denied`, "인증 절차를 완료하지 않았습니다" | 로그인 계정을 테스트 사용자로 추가해야 한다. `docs/SETUP.md`의 3단계를 안내한다. |
| 브라우저 로그인이 필요함 (첫 실행, 7일 후 토큰 만료) | 명령을 백그라운드로 실행하고 `python -u`로 출력 버퍼링을 끈다. 출력된 인증 URL을 사용자에게 전달하고, 로그인을 마칠 때까지 기다린다. |
| `스프레드시트가 지정되지 않았습니다` | `init`을 먼저 실행하거나 `--id`를 준다. |
| `Google API 오류: 403 ... permission` | 로그인 계정에 그 시트의 편집 권한이 없다. 사용자에게 공유 설정을 확인하게 한다. |

자세한 설정은 `docs/SETUP.md`, 보안 관련은 `docs/SECURITY.md`를 참고한다.
