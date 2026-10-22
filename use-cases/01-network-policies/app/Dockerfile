FROM python:3.12-slim
# curl is here only so the demo's kubectl exec probes read cleanly.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY app.py .
COPY static ./static
# ROLE and PORT are set per deployment. Defaults serve the frontend.
ENV ROLE=frontend PORT=8080
EXPOSE 8080 8081 5432
ENTRYPOINT ["python", "app.py"]
