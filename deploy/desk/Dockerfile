FROM python:3.12-slim
WORKDIR /opt/fivewhys
COPY pyproject.toml README.md ./
COPY src/ src/
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi && \
    python -m pip install --no-cache-dir ".[desk-cache]" && \
    mkdir /data && chown 10001:10001 /data
COPY --chown=10001:10001 desk-demo/ desk-demo/
ENV DESK_ASSETS=/opt/fivewhys/desk-demo DESK_DB=/data/jobs.db PYTHONUNBUFFERED=1 HOME=/tmp
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "fivewhys.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
