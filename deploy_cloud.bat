@echo off
title Deploy Discord Automation Engine to 24/7 Cloud (Fly.io)
echo ============================================================================
echo   24/7 CLOUD DEPLOYMENT WIZARD — NO PC REQUIRED AFTER DEPLOY
echo ============================================================================
echo.
echo Checking Fly.io authentication...
"C:\Users\regan\.fly\bin\fly.exe" auth whoami >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/4] Opening browser to sign in to Fly.io...
    "C:\Users\regan\.fly\bin\fly.exe" auth login
) else (
    echo [1/4] Already authenticated with Fly.io!
)

echo.
echo [2/4] Initializing cloud application (if not already created)...
"C:\Users\regan\.fly\bin\fly.exe" apps create discord-owner-engine >nul 2>&1

echo.
echo [3/4] Provisioning persistent 1GB database volume (dsp_data)...
"C:\Users\regan\.fly\bin\fly.exe" volumes create dsp_data --size 1 --region ord --yes >nul 2>&1

echo.
echo [4/4] Deploying 24/7 container to Cloud...
"C:\Users\regan\.fly\bin\fly.exe" deploy --ha=false

echo.
echo ============================================================================
echo   DEPLOYMENT COMPLETE! Your panel is now running 24/7 in the cloud.
echo   Even if you shut down your PC, your campaigns and tasks stay active.
echo ============================================================================
"C:\Users\regan\.fly\bin\fly.exe" status
pause
