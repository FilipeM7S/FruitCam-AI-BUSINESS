param([switch]$Seed)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not $env:DJANGO_SECRET_KEY) { throw "Defina antes: `$env:DJANGO_SECRET_KEY = '<um texto longo seu>'" }
if (-not $env:DJANGO_HTTPS) { $env:DJANGO_HTTPS = "0" }
python manage.py migrate
if ($Seed) { python manage.py seed_showcase }
$line = Start-Process python -ArgumentList "manage.py", "run_line" -WindowStyle Minimized -PassThru
Write-Host "Supervisor ligado: ele mantém as câmeras simuladas linha-1 e linha-2 no ar. Abra http://127.0.0.1:8000 e pare com Ctrl+C."
try { python manage.py runserver } finally {
    python manage.py run_line --stop
    if (-not $line.WaitForExit(45000)) { $line | Stop-Process -Force }
}
