# 일일 업무일지 자동 작성

지정한 저장소들에서 **내가 한 커밋**을 모아 날짜별 업무일지(Markdown)를 만듭니다.
구글 로그인이 필요 없고, 시트를 바꾸지 않습니다. git 기록만 읽습니다.

## 1. 대상 저장소 정하기

```powershell
gtrack worklog add D:/work --match bx      # D:/work 아래(2단계까지) 이름에 bx 가 들어간 저장소 모두
gtrack worklog add D:/work/bx-admin        # 저장소 하나만
gtrack worklog repos                       # 지금 대상이 되는 저장소와 작성자 확인
gtrack worklog remove D:/work              # 빼기
```
- `--match`는 대소문자를 가리지 않습니다. 폴더는 **실행할 때마다 다시 찾으므로** 나중에 clone 한 bx 저장소도 자동으로 포함됩니다.
- 작성자는 각 저장소의 `git config user.email`로 거릅니다. 회사·개인 메일을 섞어 쓴다면 `.gtrack.json`의 `worklog.author`에 정규식으로 적습니다. 예: `"me@company.com\\|me@gmail.com"`

## 2. 작성하기

```powershell
gtrack worklog write                              # 오늘
gtrack worklog write --date 2026-10-17            # 특정 날
gtrack worklog write --from 2026-10-01 --to 2026-10-19   # 기간 (커밋 없는 날은 파일을 만들지 않음)
gtrack worklog write --catch-up                   # 마지막으로 작성한 날부터 오늘까지 (예약 작업용)
```
- 모든 **로컬 브랜치**의 커밋을 봅니다. 아직 push 하지 않은 커밋도 포함됩니다.
- 날짜는 커밋 **작성 시각** 기준입니다. rebase 해도 원래 작업한 날에 남습니다.
- 같은 날을 다시 작성하면 그날 일지를 새로 만듭니다. **`## 메모` 아래에 직접 적은 내용은 그대로 유지**됩니다.

## 3. 자동으로 매일 작성 (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-worklog.ps1            # 매일 18:50 + 로그인할 때
powershell -ExecutionPolicy Bypass -File scripts\install-worklog.ps1 -At 19:30  # 시각 바꾸기
powershell -ExecutionPolicy Bypass -File scripts\install-worklog.ps1 -Uninstall # 해제
```
- 작업 스케줄러에 `gtrack-worklog`로 등록되고 창 없이(`pythonw`) 실행됩니다.
- PC가 꺼져 있어 거른 날은 다음 로그인 때 `--catch-up`이 채웁니다(최대 31일).
- 실행 결과는 업무일지 폴더의 `worklog.log`에 남습니다.
- macOS/Linux는 crontab에 `50 18 * * * cd <설치 폴더> && python -m gtrack worklog write --catch-up --quiet`를 추가합니다.

## 4. 확인하기

```powershell
gtrack worklog show                     # 오늘
gtrack worklog show --date 2026-10-17   # 특정 날
gtrack worklog show --week              # 이번 주 (월~일)
gtrack worklog show --list              # 작성된 일지 파일 목록
```
파일은 `<설치 폴더>/worklog/YYYY-MM/YYYY-MM-DD.md`에 있습니다. 다른 곳(예: OneDrive, Obsidian 폴더)에 두려면 `.gtrack.json`의 `worklog.dir`을 바꿉니다.
`worklog/` 폴더는 개인 기록이라 git에 올라가지 않습니다(`.gitignore`).

## 일지 내용

```markdown
# 업무일지 2026-10-19 (월)

> 저장소 2곳 · 커밋 4건 · 변경 파일 4개 · 관련 작업 T-018

## bx-api

프로젝트: BX 리뉴얼 · 브랜치: main, feat/cart · 09:10 ~ 16:00

### 기능 개발

- 09:10 검색 필터 `(search)` [T-018] — `2df14859` (파일 1개)

### 버그 수정

- 14:30 로그인 오류 — `6f471b0b` (파일 1개)

## 메모
<!-- 이 아래에 적은 내용은 업무일지를 다시 만들어도 그대로 남습니다. -->
```
- 커밋 제목의 `feat:`, `fix:` 같은 접두어로 **기능 개발·버그 수정·성능 개선·리팩터링·테스트·문서·스타일·빌드·설정·기타**로 나눕니다.
- `gtrack git link`로 프로젝트에 연결한 저장소면 프로젝트 이름과, 커밋에 연결된 작업 ID(경로·scope 규칙 포함)를 함께 적습니다.

## `.gtrack.json` 형식

```json
{
  "worklog": {
    "sources": [{"path": "D:/work", "match": "bx"}, {"path": "D:/work/bx-admin"}],
    "author": "me@company.com",
    "dir": "D:/OneDrive/업무일지",
    "last": "2026-10-19"
  }
}
```
`author`, `dir`은 생략할 수 있습니다. `last`는 `--catch-up`이 기록합니다.
