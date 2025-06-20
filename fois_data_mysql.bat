@echo off
set CONTAINER_NAME=fois_data_app
set IMAGE_NAME=fois_data_app
set PORT=8599

REM Remove existing container if it exists
FOR /F "tokens=1" %%i IN ('docker ps -a -q -f name=%CONTAINER_NAME%') DO docker rm -f %%i

REM Build the Docker image
docker build -t %IMAGE_NAME% .

REM Run the Docker container with port mapping and .env file
docker run --name %CONTAINER_NAME% --env-file .env -p %PORT%:8599 -d %IMAGE_NAME%

REM Start the container if it is not running (in case it was created but not started)
docker start %CONTAINER_NAME%

echo Application is running on port %PORT%
