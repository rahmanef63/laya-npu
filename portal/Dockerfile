# Portal container. Holds the device registry and serves the landing page.
FROM python:3.12-slim

WORKDIR /app
# Build context is the portal/ directory itself.
COPY . /app/portal/
RUN mkdir -p /data
ENV PORTAL_DB=/data/portal.sqlite \
    PORTAL_PORT=8650 \
    PORTAL_BIND=0.0.0.0 \
    PYTHONUNBUFFERED=1

EXPOSE 8650
CMD ["python", "portal/app.py"]
