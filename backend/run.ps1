param([string]$Port, [int]$HttpPort = 8000, [string]$Python)
$ErrorActionPreference = "Stop"
if ($Port) { $env:ARDUINO_PORT = $Port }
if (!$Python) { $Python = "C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe" }
$python = $Python
if (!(Test-Path $python)) { throw "No se encontró Python de Windows en $python." }
& $python -m uvicorn main:app --host 0.0.0.0 --port $HttpPort --app-dir $PSScriptRoot
exit $LASTEXITCODE
