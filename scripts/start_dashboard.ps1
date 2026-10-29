param([int]$Port=8765)
$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
& .\.venv\Scripts\python.exe -B -m btms.dashboard --port $Port
