FROM python:3.12-slim
# The app itself uses the Python standard library only. curl is installed so the
# demo's "kubectl exec ... curl" checks use curl, the natural tool for a lab.
# hadolint ignore=DL3008
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
