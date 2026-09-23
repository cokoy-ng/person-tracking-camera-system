param([string]$Port, [int]$HttpPort = 8000)
$ErrorActionPreference = "Stop"
if ($Port) { $env:ARDUINO_PORT = $Port }
$python = "C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe"
if (!(Test-Path $python)) { throw "No se encontró Python de Windows en $python." }
& $python -m uvicorn main:app --host 0.0.0.0 --port $HttpPort --app-dir $PSScriptRoot
exit $LASTEXITCODE
