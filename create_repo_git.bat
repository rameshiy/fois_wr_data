@echo off
title Setup Docker Project with GitHub CI/CD

REM === Step 1: Get User Input ===
set /p repo_name=Enter the GitHub repo name:
set /p image_name=Enter the Docker image name:
set /p container_name=Enter the Docker container name:
set /p port=Enter the port you want to expose:

REM === Step 2: Create Starter File if Missing ===
IF NOT EXIST app.py (
    echo print("Hello from %repo_name%") > app.py
)

REM === Step 3: Initialize Git repo and make first commit ===
echo Initializing local Git repository...
IF NOT EXIST ".git" (
    git init
)

REM Add all files and commit
git add .
git commit -m "Initial commit" >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Git commit failed. Make sure there is at least one file to commit.
    pause
    exit /b
)

REM === Step 4: Check if GitHub repo exists ===
echo Checking if GitHub repo already exists...
gh repo view %repo_name% >nul 2>&1

IF %ERRORLEVEL% EQU 0 (
    echo Repo %repo_name% already exists. Linking and pushing...
    git remote add origin https://github.com/rameshiy/%repo_name%.git 2>nul
    git push -u origin master
) ELSE (
    echo Creating GitHub repo...
    gh repo create %repo_name% --public --source=. --remote=origin --push || (
        echo Failed to create GitHub repo. Please check repo name or network.
        pause
        exit /b
    )
)

REM === Step 5: Create Dockerfile ===
echo Creating Dockerfile...
echo FROM python:3.10 > Dockerfile
echo WORKDIR /app >> Dockerfile
echo COPY . /app >> Dockerfile
echo CMD ["python", "app.py"] >> Dockerfile

REM === Step 6: Create GitHub Actions Workflow ===
echo Setting up GitHub Actions workflow...
mkdir .github\workflows 2>nul

(
echo name: Build and Push Docker Image
echo on: [push]
echo jobs:
echo.  build:
echo.    runs-on: ubuntu-latest
echo.    steps:
echo.    - uses: actions/checkout@v3
echo.    - name: Build Docker image
echo.      run: docker build -t %image_name% .
) > .github\workflows\docker.yml

REM === Step 7: Build Docker Image ===
echo Building Docker image...
docker build -t %image_name% .

REM === Step 8: Stop and Remove Old Container (if exists) ===
echo Stopping and removing existing container (if any)...
docker stop %container_name% >nul 2>&1
docker rm %container_name% >nul 2>&1

REM === Step 9: Run Docker Container ===
echo Running Docker container...
docker run -d -p %port%:%port% --name %container_name% %image_name%

echo.
echo ✅ Done! Project synced with GitHub, Docker image built, and container running on port %port%.
pause
