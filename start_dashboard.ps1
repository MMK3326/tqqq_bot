$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendRoot = Join-Path $Root 'frontend'
$FrontendDist = Join-Path $FrontendRoot 'dist'
$LogDir = Join-Path $Root 'logs'
$BrowserProfile = Join-Path $Root '.dashboard-browser'
$Url = 'http://127.0.0.1:5173'

New-Item -ItemType Directory -Force -Path $LogDir, $BrowserProfile | Out-Null

function Stop-DashboardPorts {
    foreach ($port in 5173, 8008) {
        $lines = netstat -ano | Select-String ":$port .*LISTENING"
        foreach ($line in $lines) {
            $parts = ($line.ToString() -split '\s+') | Where-Object { $_ }
            $processId = [int]$parts[-1]
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
}

function Test-HttpOk {
    param(
        [Parameter(Mandatory = $true)]
        [string] $TargetUrl
    )

    try {
        $response = Invoke-WebRequest -UseBasicParsing $TargetUrl -TimeoutSec 2
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    } catch {
        return $false
    }
}

function Wait-ForDashboard {
    $deadline = (Get-Date).AddSeconds(45)
    do {
        $apiOk = Test-HttpOk 'http://127.0.0.1:8008/health'
        $webOk = Test-HttpOk $Url
        if ($apiOk -and $webOk) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)

    return $false
}

function Get-BrowserPath {
    $candidates = @(
        'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
        'C:\Program Files\Google\Chrome\Application\chrome.exe',
        'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

function Get-DashboardBrowserProcesses {
    try {
        $escapedProfile = $BrowserProfile.Replace('\', '\\')
        Get-CimInstance Win32_Process -Filter "Name='msedge.exe' OR Name='chrome.exe'" -ErrorAction Stop |
            Where-Object {
                $_.CommandLine -match [regex]::Escape($BrowserProfile) -or
                $_.CommandLine -match [regex]::Escape($escapedProfile)
            }
    } catch {
        @()
    }
}

function Maximize-DashboardBrowser {
    param(
        [Parameter(Mandatory = $true)]
        [array] $BrowserProcesses
    )

    if (-not ('Win32Window' -as [type])) {
        Add-Type @'
using System;
using System.Runtime.InteropServices;

public static class Win32Window {
    [DllImport("user32.dll")]
    public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
}
'@
    }

    foreach ($item in $BrowserProcesses) {
        try {
            $process = Get-Process -Id $item.ProcessId -ErrorAction Stop
            if ($process.MainWindowHandle -ne 0) {
                [Win32Window]::ShowWindowAsync($process.MainWindowHandle, 3) | Out-Null
            }
        } catch {
        }
    }
}

Stop-DashboardPorts

$backendOut = Join-Path $LogDir 'backend.out.log'
$backendErr = Join-Path $LogDir 'backend.err.log'
$buildOut = Join-Path $LogDir 'frontend-build.out.log'
$buildErr = Join-Path $LogDir 'frontend-build.err.log'
$frontendOut = Join-Path $LogDir 'frontend.out.log'
$frontendErr = Join-Path $LogDir 'frontend.err.log'

$build = Start-Process -WindowStyle Hidden -PassThru -Wait -FilePath 'cmd.exe' `
    -ArgumentList '/c', 'npm.cmd run build' `
    -WorkingDirectory $FrontendRoot `
    -RedirectStandardOutput $buildOut `
    -RedirectStandardError $buildErr

if ($build.ExitCode -ne 0) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "Frontend build failed. Check logs in $LogDir.",
        'MMK Dashboard',
        'OK',
        'Error'
    ) | Out-Null
    exit 1
}

$backend = Start-Process -WindowStyle Hidden -PassThru -FilePath 'cmd.exe' `
    -ArgumentList '/c', 'python -m uvicorn backend.main:app --host 127.0.0.1 --port 8008' `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $backendOut `
    -RedirectStandardError $backendErr

$frontend = Start-Process -WindowStyle Hidden -PassThru -FilePath 'cmd.exe' `
    -ArgumentList '/c', 'python -m http.server 5173 --bind 127.0.0.1' `
    -WorkingDirectory $FrontendDist `
    -RedirectStandardOutput $frontendOut `
    -RedirectStandardError $frontendErr

if (-not (Wait-ForDashboard)) {
    Stop-DashboardPorts
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "Dashboard did not start. Check logs in $LogDir.",
        'MMK Dashboard',
        'OK',
        'Error'
    ) | Out-Null
    exit 1
}

$browserPath = Get-BrowserPath
if ($browserPath) {
    $browser = Start-Process -PassThru -FilePath $browserPath -ArgumentList @(
        "--user-data-dir=$BrowserProfile",
        "--app=$Url",
        '--start-maximized',
        '--window-position=0,0',
        '--window-size=1920,1080',
        '--no-first-run'
    )

    Start-Sleep -Seconds 2
    Maximize-DashboardBrowser -BrowserProcesses @(Get-DashboardBrowserProcesses)
    while ($true) {
        $browserProcesses = @(Get-DashboardBrowserProcesses)
        if ($browser.HasExited -and $browserProcesses.Count -eq 0) {
            break
        }
        if (-not $browser.HasExited -or $browserProcesses.Count -gt 0) {
            Start-Sleep -Seconds 2
            continue
        }
        break
    }
} else {
    Start-Process $Url
}

Stop-DashboardPorts
