# SmartKefu 一键开发启动脚本（Windows）
# 用法：
#   powershell -ExecutionPolicy Bypass -File .\start-dev.ps1        启动 MySQL(若停)+后端+前端，就绪后打开浏览器
#   powershell -ExecutionPolicy Bypass -File .\start-dev.ps1 -Stop  停止前后端进程（MySQL 服务保持运行）
# 特性：幂等——端口已被占用则跳过对应服务，重复执行无副作用。
param(
    [switch]$Stop
)

$ErrorActionPreference = 'SilentlyContinue'
$Root = $PSScriptRoot
$NodeDir = 'C:\Program Files\nodejs'

function Get-PortPids([int]$Port) {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($conns) { $conns | Select-Object -ExpandProperty OwningProcess -Unique }
}

# 先杀根进程、再递归杀子进程，保证 uvicorn --reload 的 reloader 不会重新拉起 worker
function Stop-Tree([int]$ProcId) {
    if (-not $ProcId) { return }
    Stop-Process -Id $ProcId -Force -ErrorAction SilentlyContinue
    Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcId" -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Tree $_.ProcessId
    }
}

if ($Stop) {
    Write-Host '=== 停止 SmartKefu 开发服务 ===' -ForegroundColor Yellow

    # 1) 后端：按命令行匹配 uvicorn（含 --reload 的 reloader 根优先杀，防止 worker 被重启）
    $backProcs = Get-CimInstance Win32_Process -Filter "Name like 'python%'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'app\.main:app' }
    $backProcs | Sort-Object -Property @{ Expression = { $_.CommandLine -notmatch '--reload' } } | ForEach-Object {
        Write-Host ('  停止后端 {0} (PID {1})' -f $_.Name, $_.ProcessId)
        Stop-Tree $_.ProcessId
    }

    # 2) 前端：按命令行匹配 vite / 本项目前端的 npm
    Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'vite|smart-kefu[\\/]+frontend' } | ForEach-Object {
        Write-Host ('  停止前端 {0} (PID {1})' -f $_.Name, $_.ProcessId)
        Stop-Tree $_.ProcessId
    }

    # 3) 端口兜底
    foreach ($port in 8000, 5173, 5174) {
        foreach ($procId in (Get-PortPids $port)) {
            $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($p) {
                Write-Host ('  停止端口 {0} 占用 {1} (PID {2})' -f $port, $p.ProcessName, $procId)
                Stop-Tree $procId
            }
        }
    }

    Start-Sleep -Seconds 2
    $left = @(foreach ($port in 8000, 5173, 5174) { Get-PortPids $port })
    if ($left) {
        Write-Warning '仍有端口被占用，可能是其他程序或需要管理员权限。'
    } else {
        Write-Host '已停止前后端（MySQL 服务保持运行）。' -ForegroundColor Green
    }
    return
}

Write-Host '=== SmartKefu 一键启动 ===' -ForegroundColor Cyan

# ---- 1) MySQL ----
$svc = Get-Service -Name 'MySQL' -ErrorAction SilentlyContinue
if ($svc -and $svc.Status -ne 'Running') {
    Write-Host 'MySQL 未运行，尝试启动...'
    try {
        Start-Service -Name 'MySQL'
        Write-Host 'MySQL 已启动' -ForegroundColor Green
    } catch {
        Write-Warning '无法启动 MySQL（可能需管理员权限）。可在 services.msc 手动启动 MySQL'
    }
} elseif ($svc) {
    Write-Host 'MySQL 已在运行' -ForegroundColor Green
} else {
    Write-Warning '未找到名为 MySQL 的服务，跳过检查（若后端报连接错误请先启动 MySQL）'
}

# ---- 2) 后端 (uvicorn, 8000) ----
if (Get-PortPids 8000) {
    Write-Host '后端已在 8000 端口运行，跳过' -ForegroundColor Green
} else {
    $venvPy = Join-Path $Root '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvPy)) {
        Write-Error '未找到项目根目录 .venv 虚拟环境，请先按 README 创建后端环境'
        return
    }
    $backendCmd = "Set-Location '$Root\backend'; & '$venvPy' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $backendCmd
    Write-Host '后端启动中（uvicorn --reload, 8000，新窗口）' -ForegroundColor Green
}

# ---- 3) 前端 (vite, 5173) ----
if ((Get-PortPids 5173) -or (Get-PortPids 5174)) {
    Write-Host '前端已在运行，跳过' -ForegroundColor Green
} else {
    if (-not (Test-Path (Join-Path $Root 'frontend\node_modules'))) {
        Write-Host '首次运行：安装前端依赖（可能需要一两分钟）...'
        Push-Location (Join-Path $Root 'frontend')
        $env:Path = $NodeDir + ';' + $env:Path
        npm install
        Pop-Location
    }
    $frontendCmd = "Set-Location '$Root\frontend'; `$env:Path = '$NodeDir;' + `$env:Path; npm run dev"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $frontendCmd
    Write-Host '前端启动中（vite, 5173，新窗口）' -ForegroundColor Green
}

# ---- 4) 等待就绪 + 打开浏览器 ----
Write-Host '等待服务就绪（最多 40 秒）...'
$ready = $false
$fePort = $null
foreach ($i in 1..40) {
    $be = Get-PortPids 8000
    if (Get-PortPids 5173) { $fePort = 5173 } elseif (Get-PortPids 5174) { $fePort = 5174 }
    if ($be -and $fePort) { $ready = $true; break }
    Start-Sleep -Seconds 1
}

if ($ready) {
    Write-Host ('全部就绪：后端 http://127.0.0.1:8000 （接口文档 /docs） 前端 http://localhost:' + $fePort) -ForegroundColor Green
    Start-Process ('http://localhost:' + $fePort)
} else {
    Write-Warning '40 秒内未检测到前后端就绪，请查看新弹出的两个窗口里的报错信息'
}
