@echo off
node "%~dp0server\start-preview.mjs"
if errorlevel 1 (
  echo Preview failed to start. Read the message above.
  pause
  exit /b 1
)
echo Preview ready: http://127.0.0.1:8918/
echo You can close this window; the preview runs in the background.
