ARG BASE_IMAGE=task-ttscompare-rlhf-base:v06-2a32c18a8b04
FROM ${BASE_IMAGE}

WORKDIR /poc

COPY --chmod=0644 \
    app.py \
    real_omnivoice.py \
    real_xtts.py \
    real_chatterbox.py \
    real_piper.py \
    /poc/

ENV PYTHONDONTWRITEBYTECODE=1
