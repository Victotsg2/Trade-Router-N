@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHONUTF8=1"
set "PYTHONNOUSERSITE=1"
if defined NAVAL_TRADE_RUNTIME_HOME (
  set "APP_RUNTIME=%NAVAL_TRADE_RUNTIME_HOME%"
) else (
  set "APP_RUNTIME=%LOCALAPPDATA%\NavalTradeManager\Runtime312"
)

set "PY_HOME=%APP_RUNTIME%\py"
set "PYTHON_EXE=%PY_HOME%\python.exe"
set "EMBED_ZIP=%~dp0setup\python-3.12.10-embed-amd64.zip"
set "GET_PIP=%~dp0setup\get-pip.py"
set "PTH_TEMPLATE=%~dp0setup\python312._pth"
set "READY_MARKER=%PY_HOME%\.naval_trade_ready_v10"

if not exist "%PYTHON_EXE%" call :expand_private_python
if not exist "%PYTHON_EXE%" goto runtime_failed

copy /y "%PTH_TEMPLATE%" "%PY_HOME%\python312._pth" >nul
if not exist "%PY_HOME%\Lib\site-packages" mkdir "%PY_HOME%\Lib\site-packages"
> "%PY_HOME%\Lib\site-packages\naval_trade_app.pth" echo %~dp0

"%PYTHON_EXE%" -m pip --version >nul 2>nul
if errorlevel 1 (
  echo Installing the Python package manager...
  "%PYTHON_EXE%" "%GET_PIP%" --disable-pip-version-check --no-warn-script-location
  if errorlevel 1 goto package_install_failed
)

if not exist "%READY_MARKER%" (
  echo Installing the app packages. This is required only once...
  "%PYTHON_EXE%" -m pip install --disable-pip-version-check --no-warn-script-location --prefer-binary --only-binary=numpy,pandas,scipy,pillow,pyarrow -r requirements.txt
  if errorlevel 1 goto package_install_failed

  "%PYTHON_EXE%" -c "import streamlit, numpy, PIL, scipy, pandas, plotly, routing, economy, wind, diplomacy" >nul 2>nul
  if errorlevel 1 goto package_install_failed
  > "%READY_MARKER%" echo ready
)

if /i "%~1"=="--setup-only" (
  "%PYTHON_EXE%" -c "import sys, pandas; print('Setup ready:', sys.version.split()[0], '| pandas', pandas.__version__)"
  exit /b %ERRORLEVEL%
)

echo Starting Victor's Trade Router v5.2...
"%PYTHON_EXE%" -m streamlit run app.py
set "APP_EXIT=%ERRORLEVEL%"
if not "%APP_EXIT%"=="0" (
  echo.
  echo The app stopped with exit code %APP_EXIT%.
  pause
)
exit /b %APP_EXIT%

:expand_private_python
echo.
echo Preparing the compact private Python runtime...
call :verify_hash "%EMBED_ZIP%" MD5 fe8ef205f2e9c3ba44d0cf9954e1abd3
if errorlevel 1 exit /b 1
call :verify_hash "%GET_PIP%" SHA256 fb24e693bab954209a063d90953621412ccad4a500905a726286e038f508ddf6
if errorlevel 1 exit /b 1
if not exist "%APP_RUNTIME%" mkdir "%APP_RUNTIME%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath $env:EMBED_ZIP -DestinationPath $env:PY_HOME -Force"
if errorlevel 1 exit /b 1
copy /y "%PTH_TEMPLATE%" "%PY_HOME%\python312._pth" >nul
exit /b 0

:verify_hash
if not exist "%~1" exit /b 1
set "HASH_RESULT="
for /f "skip=1 tokens=*" %%H in ('certutil.exe -hashfile "%~1" %~2') do if not defined HASH_RESULT set "HASH_RESULT=%%H"
if /i "%HASH_RESULT%"=="%~3" exit /b 0
exit /b 1

:runtime_failed
echo.
echo The compact private runtime could not be prepared.
echo Extract a fresh copy of the ZIP to a short path such as C:\NavalTrade.
pause
exit /b 1

:package_install_failed
echo.
echo The app packages could not be installed.
echo Check the internet connection, then run this file again.
echo The launcher requires binary packages and will never compile pandas.
pause
exit /b 1
