# Git commit and push script
# Usage: .\git-commit-push.ps1 "Your commit message"

param(
    [string]$CommitMessage = "Update: improvements and fixes"
)

Write-Host "=== Git Status ===" -ForegroundColor Cyan
git status --short

Write-Host "`n=== Adding all changes ===" -ForegroundColor Cyan
git add .

Write-Host "`n=== Creating commit ===" -ForegroundColor Cyan
git commit -m $CommitMessage

Write-Host "`n=== Pushing to remote ===" -ForegroundColor Cyan
git push

Write-Host "`n=== Done! ===" -ForegroundColor Green
