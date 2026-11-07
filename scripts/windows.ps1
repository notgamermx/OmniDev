# Source installation: Python 3.12 and Node.js 24 must already be installed.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments)
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Command exited with $LASTEXITCODE" }
}
Invoke-Checked -Command 'py' -Arguments @('-3.12', '-m', 'venv', '.venv')
$Python = Join-Path $PWD '.venv\Scripts\python.exe'
Invoke-Checked -Command $Python -Arguments @('-m', 'pip', 'install', '-e', '.[dev]')
if (!(Test-Path '.env')) { Copy-Item '.env.example' '.env' }
Invoke-Checked -Command 'npm.cmd' -Arguments @('ci', '--prefix', 'apps/desktop/renderer')
Invoke-Checked -Command 'npm.cmd' -Arguments @('--prefix', 'apps/desktop/renderer', 'run', 'build')
Write-Host 'Starting OmniDev. Open http://127.0.0.1:8000/app/ . Press Ctrl+C to stop.'
Invoke-Checked -Command $Python -Arguments @('-m', 'app.cli', 'serve')
