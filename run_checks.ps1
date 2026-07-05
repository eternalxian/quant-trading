$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
& $python tests\smoke_test.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Push-Location terminal
npm run lint
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
npm run build
$code = $LASTEXITCODE
Pop-Location
exit $code
