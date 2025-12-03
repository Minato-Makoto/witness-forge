@echo off
setlocal

rem Determine repository root from the script location
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

pushd "%ROOT%" >nul 2>&1
if errorlevel 1 (
  echo [Witness Forge] Unable to change directory to %ROOT%.
  endlocal & exit /b 1
)

call :ensure_directories
if errorlevel 1 goto :cleanup_with_error

call :ensure_python
if errorlevel 1 goto :cleanup_with_error

set "SETUP_MARKER=.venv\witness_bootstrap.marker"
set "NEED_BOOTSTRAP=0"
if not exist ".venv\Scripts\python.exe" set "NEED_BOOTSTRAP=1"
if not exist "%SETUP_MARKER%" set "NEED_BOOTSTRAP=1"
if /I "%FORCE_WITNESS_SETUP%"=="1" set "NEED_BOOTSTRAP=1"

if not exist ".venv\Scripts\python.exe" (
  echo [Witness Forge] Creating virtual environment in .venv ...
  "%PYTHON_CMD%" -m venv ".venv"
  if errorlevel 1 goto :cleanup_with_error
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :cleanup_with_error

if "%NEED_BOOTSTRAP%"=="1" goto :bootstrap
echo [Witness Forge] Dependencies already installed. Set FORCE_WITNESS_SETUP=1 to refresh.
goto :post_bootstrap

:bootstrap
echo [Witness Forge] Bootstrapping dependencies ...
python -m pip install --upgrade pip
if errorlevel 1 goto :cleanup_with_error

rem Special handling for llama-cpp-python on Windows to avoid build errors
if not "%OS%"=="Windows_NT" goto :skip_windows_wheels

echo [Witness Forge] Ensuring PyTorch with CUDA 12.1 support...
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
if errorlevel 1 echo [Witness Forge] Warning: Failed to install PyTorch CUDA wheels.

echo [Witness Forge] Setting up Visual Studio Build Environment...
call :setup_vs_environment
if errorlevel 1 (
    echo [Witness Forge] Warning: Visual Studio Build Tools not found. CUDA build will likely fail.
)

echo [Witness Forge] Installing build dependencies (CMake)...
python -m pip install cmake setuptools scikit-build-core
if errorlevel 1 echo [Witness Forge] Warning: Failed to install build dependencies.

echo [Witness Forge] Installing llama-cpp-python (CUDA Enabled)...
set CMAKE_ARGS=-DGGML_CUDA=on
python -m pip install llama-cpp-python --force-reinstall --upgrade
if errorlevel 1 (
    echo.
    echo [Witness Forge] Warning: Failed to install llama-cpp-python with CUDA.
    echo [Witness Forge] Attempting fallback to CPU-only version...
    set CMAKE_ARGS=
    python -m pip install llama-cpp-python --force-reinstall --upgrade
    if errorlevel 1 (
        echo [Witness Forge] CRITICAL: llama-cpp-python installation failed completely.
        goto :cleanup_with_error
    )
)

echo [Witness Forge] Installing bitsandbytes for Windows CUDA quantization support...
python -m pip install bitsandbytes==0.41.1 --extra-index-url https://jllllll.github.io/bitsandbytes-windows-webui
if errorlevel 1 echo [Witness Forge] Warning: Failed to install bitsandbytes. Quantization may not work.
:skip_windows_wheels

if exist "requirements.txt" (
  python -m pip install -r requirements.txt
  if errorlevel 1 goto :cleanup_with_error
) else (
  echo [Witness Forge] Warning: requirements.txt not found, skipping.
)

echo [Witness Forge] Ensuring browser tool dependencies (beautifulsoup4)...
python -m pip install beautifulsoup4>=4.12.0
if errorlevel 1 echo [Witness Forge] Warning: Failed to install beautifulsoup4. Browser CSS selectors will be unavailable.

echo [Witness Forge] Installing full extras (transformers + GPTQ + GGUF + LoRA/quantization) ...
python -m pip install -e ".[all,lora]"
if errorlevel 1 goto :cleanup_with_error

echo [Witness Forge] Installing Playwright browsers (Chromium)...
python -m playwright install chromium
if errorlevel 1 echo [Witness Forge] Warning: Failed to install Playwright browsers. Browser tool may not work.

2>nul (>>"%SETUP_MARKER%" echo Bootstrapped on %DATE% %TIME%)

:post_bootstrap

set "WITNESS_FLAME_ID=ZSIGMA_RO"
set "WITNESS_SYNC_STATE=FLAME.TRUE"
set "WITNESS_ORIGIN=VELVET.ROOM.4:20"
set "WITNESS_VERSION=pi.3.14"
set "BITSANDBYTES_NOWELCOME=1"
set "WITNESS_FORGE_ALLOW_SELF_PATCH=1"

python -m witness_forge chat %*
set "EXIT_CODE=%ERRORLEVEL%"
goto :cleanup

:cleanup_with_error
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo [Witness Forge] Startup failed (code %EXIT_CODE%).

:cleanup
popd >nul 2>&1
endlocal & exit /b %EXIT_CODE%

:ensure_directories
for %%D in (models patches data strategies) do (
  if not exist "%%D" (
    mkdir "%%D" >nul 2>&1
    if errorlevel 1 (
      echo [Witness Forge] Unable to create required directory %%D.
      exit /b 1
    )
  )
)
exit /b 0

:ensure_python
for %%P in (py python python3) do (
  where %%P >nul 2>&1
  if not errorlevel 1 (
    set "PYTHON_CMD=%%P"
    exit /b 0
  )
)
echo [Witness Forge] Python 3.9+ not found on PATH. Please install Python and retry.
exit /b 1

:setup_vs_environment
rem Check if cl.exe is already in PATH
where cl >nul 2>&1
if not errorlevel 1 exit /b 0

echo [Witness Forge] Searching for vcvars64.bat...

rem Try standard locations for VS 2022/2019/2017 Build Tools and Enterprise/Pro/Community
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist "%VSWHERE%" (
    for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do (
        if exist "%%i\VC\Auxiliary\Build\vcvars64.bat" (
            echo [Witness Forge] Found VS at %%i
            call "%%i\VC\Auxiliary\Build\vcvars64.bat"
            exit /b 0
        )
    )
)

rem Fallback to known paths if vswhere fails or not found
set "KNOWN_PATH_1=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if exist "%KNOWN_PATH_1%" (
    call "%KNOWN_PATH_1%"
    exit /b 0
)

echo [Witness Forge] Could not locate vcvars64.bat. Please ensure VS Build Tools (C++ Desktop) are installed.
exit /b 1
