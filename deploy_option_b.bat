@echo off
title Option B — 24/7 Cloud Deploy via GitHub + Render / Railway
echo ============================================================================
echo   OPTION B: 1-CLICK GITHUB + RENDER / RAILWAY 24/7 CLOUD DEPLOY
echo ============================================================================
echo.

echo [Step 1/3] Checking GitHub CLI Authentication...
gh auth status >nul 2>&1
if %errorlevel% neq 0 (
    echo Opening browser to sign in to GitHub...
    gh auth login --git-protocol https --web
) else (
    echo Already signed in to GitHub!
)

echo.
echo [Step 2/3] Creating Private GitHub Repository and Pushing Code...
gh repo create discord-owner-engine --private --source=. --remote=origin --push
if %errorlevel% neq 0 (
    echo Repository already exists, pushing latest commit to main...
    git push -u origin main
)

echo.
echo [Step 3/3] Opening Render.com Blueprint Deploy in your Browser...
start https://dashboard.render.com/blueprints

echo.
echo ============================================================================
echo   ALMOST DONE! In the browser window that just opened:
echo   1. Click "New Blueprint Instance" (or "New Web Service" on Render/Railway)
echo   2. Select your "discord-owner-engine" repository
echo   3. Click "Apply" / "Deploy" — Render reads render.yaml automatically!
echo   Your panel will stay hosted 24/7 in the cloud with your PC turned off.
echo ============================================================================
pause
