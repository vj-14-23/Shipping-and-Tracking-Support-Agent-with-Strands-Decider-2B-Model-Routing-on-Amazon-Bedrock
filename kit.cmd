@echo off
rem The kit commands on Windows: .\kit help   (macOS and Linux: ./kit help)
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto venv
where uv >nul 2>nul && goto uvpath
if exist "%USERPROFILE%\.local\bin\uv.exe" goto uvhome
where py >nul 2>nul && goto pylauncher
echo Python 3.10 to 3.13 is needed. Run the install command from docs\GETTING-STARTED.md first.
exit /b 1
:venv
".venv\Scripts\python.exe" scripts\kit.py %*
exit /b %ERRORLEVEL%
:uvpath
uv run --no-project --python 3.12 python scripts\kit.py %*
exit /b %ERRORLEVEL%
:uvhome
"%USERPROFILE%\.local\bin\uv.exe" run --no-project --python 3.12 python scripts\kit.py %*
exit /b %ERRORLEVEL%
:pylauncher
py -3 scripts\kit.py %*
exit /b %ERRORLEVEL%
