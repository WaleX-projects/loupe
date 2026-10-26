# The APP image: runs the API and the worker. DockerSandbox shells out to `docker exec`,
# so this image needs the Docker CLI (not the daemon). The daemon is the host's, via the mounted socket.
FROM python:3.12-slim

COPY --from=docker:27-cli /usr/local/bin/docker /usr/local/bin/docker

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
