@echo off
setlocal
cd /d "%~dp0"

echo ===============================================
echo Virtual Computer Control v8 - Setup
echo ===============================================
echo.
py --version
if errorlevel 1 (
 echo Python Launcher not found. Run: py --version
 pause
 exit /b 1
)

if exist ".venv" (
 echo Removing previous virtual environment...
 rmdir /s /q ".venv"
)

echo Creating clean virtual environment...
py -3.13 -m venv .venv
if errorlevel 1 (
 echo Could not create Python 3.13 virtual environment.
 pause
 exit /b 1
)

echo Upgrading pip without cache...
.venv\Scripts\python.exe -m pip install --upgrade pip --no-cache-dir

echo Installing camera, gesture, audio and automation packages...
.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt
if errorlevel 1 (
 echo.
 echo SETUP FAILED. Copy the complete error above and send it to ChatGPT.
 pause
 exit /b 1
)

if not exist "models" mkdir models
if not exist "models\hand_landmarker.task" (
 echo Downloading MediaPipe hand model...
 powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task' -OutFile 'models\hand_landmarker.task'"
 if errorlevel 1 (
  echo.
  echo Could not download the hand model. Check internet access and run setup.bat again.
  pause
  exit /b 1
 )
)

echo.
echo ===============================================
echo SETUP COMPLETED SUCCESSFULLY
echo ===============================================
echo Run run.bat
pause
