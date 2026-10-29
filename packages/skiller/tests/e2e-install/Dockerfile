FROM ubuntu:26.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates pipx python3 python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash tester

COPY --chown=tester:tester *.whl /tmp/wheels/
COPY --chown=tester:tester check.sh /opt/check.sh
USER tester
ENV HOME=/home/tester \
    PATH=/home/tester/.local/bin:$PATH \
    TERM=xterm-256color \
    COLORTERM=truecolor
RUN pipx install /tmp/wheels/*.whl
WORKDIR /home/tester
ENTRYPOINT ["bash", "/opt/check.sh"]
