# Open PR creation page

$title = "fix: improve CI/CD integration tests and error handling"
$url = "https://github.com/drsapaev/final/compare/main...feat/macos-ui-refactor"

Write-Host "Creating PR..." -ForegroundColor Green
Write-Host "Title: $title" -ForegroundColor Cyan
Write-Host "URL: $url" -ForegroundColor Cyan
Write-Host ""
Write-Host "Opening browser..." -ForegroundColor Yellow

Start-Process $url

Write-Host ""
Write-Host "Browser opened!" -ForegroundColor Green
Write-Host "Copy the description from PR_TEMPLATE.txt" -ForegroundColor Yellow

