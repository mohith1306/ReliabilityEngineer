# Bob Reliability Engineer -- public demo image.
#
# What this image is: the BRE API + dashboard with the DEMO workspace enabled and IBM Bob replaced by its
# labelled replay stand-in. Everything else is real: it needs `git` (checkpoints, branches, rollback) and
# `pytest` (verification) because BRE verifies fixes by actually running the target's tests.
#
# What it is NOT: a live-Bob deployment. Bob Shell (Node 24+, BOB_API_KEY) is deliberately not baked in --
# credentials do not belong in an image. For live Bob, run BRE locally (see docs/DEMO.md).
#
#   docker build -t bre .
#   docker run --rm -p 8000:8000 bre        # then open http://localhost:8000

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Public-demo defaults. The operator key below is PUBLIC ON PURPOSE (it is shown in the UI so a visitor can
# play the approving human); on any real deployment set your own BRE_OPERATOR_KEY and drop BRE_DEMO_SHOW_KEY.
ENV BRE_DEMO=1 \
    BRE_BOB_TRANSPORT=replay \
    BRE_DEMO_SHOW_KEY=1 \
    BRE_OPERATOR_KEY=demo-operator-key \
    BRE_OPERATOR_NAME="Demo operator" \
    BRE_DEMO_DIR=/tmp/bre-demo \
    BRE_TAU=0.30

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:%s/health'%os.environ.get('PORT','8000'))"
CMD ["sh", "-c", "uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
