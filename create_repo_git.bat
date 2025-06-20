@echo off
title Setup Docker Project with Local GitHub CI/CD

:: Initialize variables
set "repo_owner=rameshiy"

REM === Step 1: Get User Input ===
echo Enter the following details:
set /p repo_name=GitHub repo name: 
set /p image_name=Docker image name: 
set /p container_name=Docker container name: 
set /p port=Port to expose: 

if "%repo_name%"=="" set "repo_name=my-app"
if "%image_name%"=="" set "image_name=my-app"
if "%container_name%"=="" set "container_name=my-app-container"
if "%port%"=="" set "port=8000"

REM === Step 2: Create Starter Files if Missing ===
if not exist app.py (
    echo print("Hello from %repo_name%") > app.py
    echo Created app.py
)

if not exist requirements.txt (
    (
        echo requests==2.32.3
        echo python-dotenv==1.0.1
        echo pandas==2.2.2
        echo gspread==6.1.2
        echo oauth2client==4.1.3
        echo mysql-connector-python==9.0.0
    ) > requirements.txt
    echo Created requirements.txt
)

REM === Step 3: Initialize Git Repository ===
echo Initializing local Git repository...
if not exist ".git" (
    git init || (
        echo Error: Failed to initialize Git repository.
        pause
        exit /b 1
    )
)

:: Ensure main branch exists
git rev-parse --verify main >nul 2>&1
if %ERRORLEVEL% neq 0 (
    git rev-parse --verify master >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo Renaming master branch to main...
        git branch -m master main || (
            echo Error: Failed to rename master to main.
            pause
            exit /b 1
        )
    ) else (
        echo Creating main branch...
        git checkout -b main || (
            echo Error: Failed to create main branch.
            pause
            exit /b 1
        )
    )
)

:: Add all files and commit
git add . || (
    echo Error: Failed to stage files for commit.
    pause
    exit /b 1
)
git commit -m "Initial commit with requirements.txt and Dockerfile" >nul 2>&1 || (
    echo Warning: No changes to commit or commit failed. Proceeding...
)

REM === Step 4: Check and Configure GitHub Repo ===
echo Checking if GitHub repo %repo_name% exists...
gh repo view %repo_owner%/%repo_name% >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Repo %repo_name% already exists. Configuring remote...
    git remote remove origin >nul 2>&1
    git remote add origin https://github.com/%repo_owner%/%repo_name%.git || (
        echo Error: Failed to add GitHub remote.
        pause
        exit /b 1
    )
    echo Pushing to GitHub...
    git push -u origin main || (
        echo Error: Failed to push to GitHub. Check GitHub CLI authentication or network.
        echo Run `gh auth login` if not authenticated.
        pause
        exit /b 1
    )
) else (
    echo Creating GitHub repo %repo_name%...
    gh repo create %repo_owner%/%repo_name% --public --source=. --remote=origin --push || (
        echo Error: Failed to create GitHub repo. Check repo name, network, or GitHub CLI authentication.
        echo Run `gh auth login` if not authenticated.
        pause
        exit /b 1
    )
)

REM === Step 5: Create Dockerfile ===
echo Creating Dockerfile...
(
    echo FROM python:3.10.14-slim
    echo.
    echo WORKDIR /app
    echo.
    echo # Install system dependencies for mysql-connector-python
    echo RUN apt-get update && apt-get install -y --no-install-recommends \
    echo     gcc \
    echo     libc-dev \
    echo     && rm -rf /var/lib/apt/lists/*
    echo.
    echo # Copy only requirements first to leverage Docker cache
    echo COPY requirements.txt /app/
    echo.
    echo # Create virtual environment and install dependencies
    echo RUN python -m venv /app/venv && \
    echo     /app/venv/bin/pip install --no-cache-dir --upgrade pip && \
    echo     /app/venv/bin/pip install --no-cache-dir -r requirements.txt && \
    echo     /app/venv/bin/pip list
    echo.
    echo # Copy the rest of the application
    echo COPY . /app
    echo.
    echo # Set proper permissions
    echo RUN chown -R nobody:nogroup /app && \
    echo     chmod -R 755 /app
    echo.
    echo # Use virtual environment's Python
    echo ENV PATH="/app/venv/bin:$PATH"
    echo.
    echo # Run as non-root user for security
    echo USER nobody
    echo.
    echo # Healthcheck (adjust port/endpoint if needed)
    echo HEALTHCHECK --interval=30s --timeout=3s \
    echo     CMD curl -f http://localhost:%port%/health || exit 1
    echo.
    echo CMD ["python", "app.py"]
) > Dockerfile

REM === Step 6: Create GitHub Actions Workflow ===
echo Setting up GitHub Actions workflow for local build validation...
mkdir .github\workflows 2>nul

(
    echo name: Build Docker Image
    echo.
    echo on:
    echo   push:
    echo     branches: [main]
    echo.
    echo jobs:
    echo   build:
    echo     runs-on: ubuntu-latest
    echo.
    echo     steps:
    echo     - name: Checkout code
    echo       uses: actions/checkout@v4
    echo.
    echo     - name: Build Docker image
    echo       run: docker build -t %image_name%:latest .
) > .github\workflows/docker.yml

REM === Step 7: Build Docker Image ===
echo Building Docker image...
docker build -t %image_name%:latest . || (
    echo Error: Docker build failed. Check Dockerfile or dependencies.
    pause
    exit /b 1
)

REM === Step 8: Stop and Remove Old Container (if exists) ===
echo Stopping and removing existing container (if any)...
docker stop %container_name% >nul 2>&1
docker rm %container_name% >nul 2>&1

REM === Step 9: Run Docker Container ===
echo Running Docker container...
docker run -d -p %port%:%port% --name %container_name% %image_name%:latest || (
    echo Error: Failed to start Docker container. Check logs with `docker logs %container_name%`.
    pause
    exit /b 1
)

echo.
echo ✅ Done! Project synced with GitHub, Docker image built, and container running locally on port %port%.
echo Notes:
echo 1. Ensure app.py exposes port %port% (e.g., Streamlit on %port%).
echo 2. If no /health endpoint, remove or update HEALTHCHECK in Dockerfile.
echo 3. GitHub Actions will validate builds on push.
echo 4. Check container logs if needed: `docker logs %container_name%`
echo 5. If Git push issues persist, verify authentication with `gh auth status`.
echo 6. If ModuleNotFoundError persists, check build logs for `pip list` output.
pause