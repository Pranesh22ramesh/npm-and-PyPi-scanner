$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Install dependencies as described in README.md first.' }
Push-Location (Join-Path $projectRoot 'backend')
try { & $pythonExe run.py --port 8011 } finally { Pop-Location }
