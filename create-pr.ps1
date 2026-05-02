# create-pr.ps1 (ASCII only)

Write-Host "Create Pull Request: feat/macos-ui-refactor -> main" -ForegroundColor Green
Write-Host ""

# PR parameters
$owner = "drsapaev"
$repo = "final"
$title = "fix: improve CI/CD integration tests and error handling"
$head = "feat/macos-ui-refactor"
$base = "main"

# Open PR compare page
$url = "https://github.com/$owner/$repo/compare/$base...$head"
Write-Host "Opening browser: $url" -ForegroundColor Yellow
Start-Process $url

# Try to copy PR template to clipboard (if exists)
$templatePath = Join-Path (Get-Location) "PR_TEMPLATE.txt"
if (Test-Path $templatePath) {
  try {
    Get-Content $templatePath | Set-Clipboard
    Write-Host "Template copied to clipboard. Paste into Description (Ctrl+V)." -ForegroundColor Cyan
  } catch {
    Write-Host "Could not copy template to clipboard. Open PR_TEMPLATE.txt and copy manually." -ForegroundColor Red
  }
} else {
  Write-Host "PR_TEMPLATE.txt not found. Fill description manually." -ForegroundColor Red
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Green
Write-Host "1) Ensure Title: $title"
Write-Host "2) Click into Description and paste (Ctrl+V)"
Write-Host "3) Click 'Create pull request'"
Write-Host ""