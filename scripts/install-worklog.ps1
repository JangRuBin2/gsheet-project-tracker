# 일일 업무일지를 자동으로 작성하도록 Windows 작업 스케줄러에 등록한다.
# 매일 지정한 시각과 로그인할 때 'gtrack worklog write --catch-up' 을 실행한다.
# (PC 가 꺼져 있어 거른 날은 다음 로그인 때 한꺼번에 채운다.)
#   등록:  powershell -ExecutionPolicy Bypass -File scripts\install-worklog.ps1 [-At 18:50]
#   해제:  powershell -ExecutionPolicy Bypass -File scripts\install-worklog.ps1 -Uninstall
# 먼저 대상 저장소를 추가해 두어야 한다: gtrack worklog add D:\work --match bx
param(
    [string]$At = '18:50',
    [switch]$Uninstall
)

$name = 'gtrack-worklog'

if ($Uninstall) {
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
        Write-Host "해제했습니다: $name"
    } else { Write-Host '등록된 예약 작업이 없습니다.' }
    return
}

$repo = Split-Path -Parent $PSScriptRoot
# 창이 뜨지 않도록 pythonw.exe 를 쓴다. Store 별칭(WindowsApps)은 제외한다.
$python = @(
    Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\pythonw.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -ExpandProperty FullName
    (Get-Command pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike '*WindowsApps*' }).Source
) | Where-Object { $_ } | Select-Object -First 1
if (-not $python) {
    Write-Host 'pythonw.exe 를 찾을 수 없습니다. skill/gtrack/references/SETUP.md 의 0단계를 참고해 Python 을 설치하세요.' -ForegroundColor Red
    return
}

$action = New-ScheduledTaskAction -Execute $python -Argument '-m gtrack worklog write --catch-up --quiet' -WorkingDirectory $repo
$triggers = @(
    New-ScheduledTaskTrigger -Daily -At $At
    New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName $name -Action $action -Trigger $triggers -Settings $settings `
    -Description 'gtrack: git 커밋으로 일일 업무일지 작성' -Force | Out-Null
Write-Host "등록했습니다: $name (매일 $At, 로그인 시)"
Write-Host "업무일지는 'gtrack worklog show' 로 보고, 실행 기록은 업무일지 폴더의 worklog.log 에 남습니다."
