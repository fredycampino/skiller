FROM python:3.12-slim

ARG SKILLER_PACKAGE=skiller==0.1.0-beta.4

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN useradd -m -s /bin/bash droid

RUN python -m pip install --upgrade pip \
    && python -m pip install "${SKILLER_PACKAGE}" \
    && python -m pip cache purge

USER droid
WORKDIR /home/droid

ENV AGENT_DB_PATH=/home/droid/runtime.db

CMD ["/bin/bash"]
