$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "terminal")
npm run dev -- --hostname 127.0.0.1
