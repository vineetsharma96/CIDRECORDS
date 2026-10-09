$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot 'venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $pythonPath)) { throw 'Create venv and install backend/requirements.txt first.' }
if (!(Test-Path -LiteralPath (Join-Path $projectRoot '.env'))) { throw 'Copy .env.example to .env and configure local Neo4j first.' }
$logDirectory = Join-Path $projectRoot 'backend/data/logs'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$apiProcess = Start-Process -FilePath $pythonPath -ArgumentList '-m','uvicorn','app.main:app','--app-dir','backend','--host','127.0.0.1','--port','8000' -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory 'api.log') -RedirectStandardError (Join-Path $logDirectory 'api-error.log') -PassThru
$webProcess = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run','dev' -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory 'web.log') -RedirectStandardError (Join-Path $logDirectory 'web-error.log') -PassThru
Write-Output "API process $($apiProcess.Id); frontend process $($webProcess.Id). Open http://localhost:3000. Logs: $logDirectory"
