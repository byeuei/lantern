# Runs the CSE documents collector with the correct working directory
# (DB_PATH/STORAGE_ROOT in cse_documents_collector.py are relative to data/).
# Scheduled daily via Windows Task Scheduler -- see docs/README for setup.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $root "data"
$logDir = Join-Path $dataDir "collector_logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$logFile = Join-Path $logDir "$stamp.log"

Set-Location $dataDir
& py "$root\collector\cse_documents_collector.py" *>&1 | Tee-Object -FilePath $logFile
