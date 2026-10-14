# scripts/host.ps1 - Start RepoScore Platform locally
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Starting RepoScore Evaluation Platform (Local) " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "[*] Web Dashboard:   http://localhost:8000/" -ForegroundColor Green
Write-Host "[*] Interactive Docs: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "[*] Health Probe:    http://localhost:8000/health" -ForegroundColor Green
Write-Host "[*] Readiness Probe: http://localhost:8000/ready" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
python -m backend.main
