# 일일 업무일지

`gtrack git link`로 연결한 저장소들(bx-store, bx-api, bx-company …)에서 **내가 한 커밋**을 날짜별로 모아 업무일지를 만듭니다.
따로 적지 않아도 커밋할 때마다 기록됩니다.

## 처음 한 번

```powershell
gtrack worklog init                 # "업무일지" 스프레드시트 파일 생성 (.gtrack.json 의 worklog.spreadsheet_id 에 저장)
gtrack worklog sync --days 30       # 지난 30일 기록 채우기 (선택)
```
- 기존 파일에 시트로 넣으려면 `gtrack worklog init --existing <스프레드시트ID>`를 씁니다.

## 자동 기록

- 연결된 저장소에서 커밋하거나 푸시하면 hook이 `gtrack git sync`를 실행합니다. 이때 업무일지도 함께 갱신됩니다.
  - 최근 3일 줄을 git 기록에서 다시 만들어 씁니다. 자정을 넘긴 커밋이나 밀린 반영도 맞춰집니다.
  - 결과는 각 저장소의 `.git/gtrack-sync.log`에 `업무일지: …` 줄로 남습니다.
- 여러 저장소의 hook이 동시에 돌아도 잠금 파일(`.gtrack-worklog.lock`) 덕분에 같은 날짜 줄이 두 번 생기지 않습니다.
- 로그인 토큰이 만료되어 반영이 밀렸다면, 다시 로그인한 뒤 `gtrack worklog sync --days 14`처럼 기간을 주어 채웁니다.

## 시트 구성 (하루 한 줄, 최신 날짜가 위)

| 칸 | 내용 |
|---|---|
| 날짜·요일 | 커밋 작성일 기준 (주말은 회색) |
| 커밋 | 그날 커밋 수 |
| 저장소·프로젝트 | 그날 작업한 저장소와 연결된 프로젝트 |
| 관련작업 | 커밋에서 찾은 작업 ID (`git_sync`의 paths/scopes 규칙과 메시지의 `T-xxx`) |
| 작업 내용 | `[저장소] 커밋 메시지 (작업ID)` 한 줄씩, 시간 순 |
| **메모** | 직접 적는 칸입니다. 회의·리뷰·문의 대응처럼 커밋이 없는 일을 적으세요. **자동 갱신 때 덮어쓰지 않습니다.** |

## 터미널에서 보기

`show`는 git 기록을 바로 읽습니다. 구글 로그인이 필요 없고, `worklog init`을 하지 않아도 됩니다.

```powershell
gtrack worklog show                         # 오늘
gtrack worklog show --date 2026-10-17       # 그날
gtrack worklog show --week                  # 이번 주 (월요일~오늘)
gtrack worklog show --days 7                # 최근 7일
gtrack worklog show --from 2026-10-01 --to 2026-10-15 --out 10월상반기.md   # 마크다운 파일로 저장
```
Claude Code에서는 "오늘 뭐 했지", "이번 주 업무 정리해줘"라고 말해도 됩니다.

## 어떤 커밋이 들어가나

- **대상 저장소**: `.gtrack.json`의 `git_sync`에 있는 저장소 전부입니다. 업무일지에 넣을 저장소를 늘리려면 `gtrack git link`로 연결하세요.
- **작성자**: 저장소마다 `git config user.email`이 같은 커밋만 넣습니다.
  - 다른 기준을 쓰려면 `.gtrack.json`에 `"worklog": {"spreadsheet_id": "...", "author": "rubinjang"}`처럼 적습니다. 이름이나 이메일 일부면 됩니다.
  - 한 번만 바꾸려면 `--author`를 줍니다.
- **브랜치**: 모든 브랜치(원격 포함)를 읽습니다. 아직 병합하지 않은 작업 브랜치의 커밋도 들어갑니다.
- **cherry-pick**: 같은 날 같은 저장소에 같은 메시지 커밋이 여러 브랜치에 있으면 한 줄로 합칩니다. 터미널 출력에는 브랜치 이름이 함께 나옵니다.
- 병합 커밋(merge)은 넣지 않습니다.
