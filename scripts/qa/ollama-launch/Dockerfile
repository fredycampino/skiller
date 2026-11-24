FROM ubuntu:26.04

ARG QA_UID=1000

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl pipx python3 python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --non-unique --uid "$QA_UID" --create-home --shell /bin/bash tester

COPY --chown=tester:tester *.whl /tmp/wheels/
USER tester
ENV HOME=/home/tester \
    PATH=/home/tester/.local/bin:$PATH \
    SKILLER_RUNTIME_CONFIG_FILE=/data/config.json \
    SKILLER_AGENT_PROVIDERS_FILE=/data/providers.json \
    TERM=xterm-256color \
    COLORTERM=truecolor
RUN pipx install /tmp/wheels/*.whl && rm -rf /tmp/wheels
RUN mkdir -p /home/tester/.skiller/settings
WORKDIR /home/tester
CMD ["sleep", "infinity"]
