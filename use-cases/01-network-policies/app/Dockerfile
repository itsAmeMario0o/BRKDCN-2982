FROM python:3.12-slim
# The app uses the Python standard library only, so it installs no packages.
# The demo's probes call the app's /check endpoint, not curl.
WORKDIR /app
COPY app.py .
COPY static ./static
# ROLE and PORT are set per deployment. Defaults serve the frontend.
ENV ROLE=frontend PORT=8080
EXPOSE 8080 8081 5432
ENTRYPOINT ["python", "app.py"]
