FROM m492zhan/lpr:latest

ENV LPR_ROOT=/tmp/LPR
WORKDIR /workspace
USER root

COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src

RUN printf '%s\n' \
    '#!/usr/bin/env bash' \
    'export PYTHONPATH="/workspace/src${PYTHONPATH:+:${PYTHONPATH}}"' \
    'exec python3 -m lpr_plus "$@"' \
    > /usr/local/bin/lpr-plus \
    && chmod +x /usr/local/bin/lpr-plus

USER coq
CMD ["lpr-plus", "--help"]
