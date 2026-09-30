@echo off
rem Run by the Yomitoki installer after copying files: download Python 3.11 and
rem create the small launcher environment (window, tray, first-run wizard).
rem The translation engine (PyTorch etc., several GB) is installed later by the
rem first-run wizard, so this only takes about a minute.
rem Comments are in English on purpose: cmd.exe reads batch files in the OEM code page.
rem Usage: bootstrap-launcher.cmd <install dir>
setlocal EnableExtensions
rem UTF-8 output, so pyvenv.cfg is written correctly when the path has non-ASCII characters.
chcp 65001 >nul
set "ROOT=%~1"
if "%ROOT%"=="" exit /b 2

set "UV=%ROOT%\bin\uv.exe"
set "UV_PYTHON_INSTALL_DIR=%ROOT%\python"
set "UV_CACHE_DIR=%ROOT%\cache\uv"
rem Corporate networks often intercept HTTPS with their own CA: use the Windows store.
set "UV_SYSTEM_CERTS=1"
set "UV_LINK_MODE=copy"
set "UV_PYTHON_PREFERENCE=only-managed"
set "UV_NO_PROGRESS=1"
set "PYVER=3.11.16"
set "LOG=%ROOT%\logs\install.log"

if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"
echo ==== %DATE% %TIME% bootstrap-launcher >> "%LOG%"

"%UV%" python install %PYVER% --no-registry --no-bin >> "%LOG%" 2>&1
set "PYEXE="
for /d %%D in ("%ROOT%\python\cpython-%PYVER%-*") do if exist "%%D\python.exe" set "PYEXE=%%D\python.exe"
if not defined PYEXE (
  echo Python %PYVER% was not installed >> "%LOG%"
  exit /b 11
)

"%UV%" venv --python "%PYEXE%" --allow-existing "%ROOT%\env\launcher" >> "%LOG%" 2>&1 || exit /b 12

rem uv points the venv at the minor-version junction (cpython-3.11-...). Processes with
rem RedirectionGuard enabled refuse to traverse junctions ("untrusted mount point",
rem os error 448), so point it at the real versioned folder instead. The installer turns
rem RedirectionGuard off (see yomitoki.iss); this keeps the venv working either way.
for %%F in ("%PYEXE%") do set "PYDIR=%%~dpF"
set "PYDIR=%PYDIR:~0,-1%"
set "CFG=%ROOT%\env\launcher\pyvenv.cfg"
> "%CFG%.new" (
  echo home = %PYDIR%
  findstr /v /b /c:"home =" "%CFG%"
)
move /y "%CFG%.new" "%CFG%" >nul || exit /b 15

"%UV%" pip install --python "%ROOT%\env\launcher\Scripts\python.exe" --no-deps -r "%ROOT%\program\requirements\launcher.lock.txt" >> "%LOG%" 2>&1 || exit /b 13
if not exist "%ROOT%\env\launcher\Scripts\pythonw.exe" exit /b 14

rem The download cache is only needed while installing.
rmdir /s /q "%ROOT%\cache" >nul 2>&1
echo ok >> "%LOG%"
exit /b 0
