# gtrack 을 전역으로 설치한다.
#  1) gtrack 명령 설치 (pip install -e .) → 어느 폴더에서나 `gtrack` 실행
#  2) ~/.claude/skills/gtrack 을 이 저장소의 skill/gtrack 에 연결(junction)
#     → 모든 Claude Code 세션에서 /gtrack 사용. 저장소를 수정하면 바로 반영된다.
#   설치: powershell -ExecutionPolicy Bypass -File scripts\install-skill.ps1
#   해제: powershell -ExecutionPolicy Bypass -File scripts\install-skill.ps1 -Uninstall
param([switch]$Uninstall)

$repo = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repo 'skill\gtrack'
$target = Join-Path $env:USERPROFILE '.claude\skills\gtrack'

if ($Uninstall) {
    $item = Get-Item $target -ErrorAction SilentlyContinue
    if ($item -and $item.LinkType -eq 'Junction') {
        # junction 만 지운다 (연결 대상인 저장소 파일은 그대로)
        [IO.Directory]::Delete($target)
        Write-Host "스킬 연결을 해제했습니다: $target"
    } elseif ($item) {
        Write-Host "$target 은 gtrack 이 만든 연결이 아니라서 그대로 둡니다." -ForegroundColor Yellow
    } else {
        Write-Host '설치된 스킬이 없습니다.'
    }
    return
}

$python = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
if (-not $python) { $python = (Get-Command py, python -ErrorAction SilentlyContinue | Select-Object -First 1).Source }
& $python -m pip install --quiet --disable-pip-version-check --no-warn-script-location -e $repo
if ($LASTEXITCODE -ne 0) { throw 'pip install 실패' }
Write-Host "gtrack 명령을 설치했습니다: $(Join-Path (Split-Path $python) 'Scripts\gtrack.exe')"

New-Item -ItemType Directory -Force (Split-Path $target) | Out-Null
$existing = Get-Item $target -ErrorAction SilentlyContinue
if ($existing) {
    if ($existing.LinkType -eq 'Junction' -and $existing.Target -contains $source) {
        Write-Host "스킬이 이미 연결되어 있습니다: $target"
        return
    }
    throw "$target 이 이미 있습니다. 직접 확인 후 지우고 다시 실행하세요."
}
New-Item -ItemType Junction -Path $target -Target $source | Out-Null
Write-Host "전역 스킬을 연결했습니다: $target -> $source"
