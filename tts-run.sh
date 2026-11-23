#!/usr/bin/env bash
clear
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODE="${1:-}"
ACTION="${2:-plan}"

case "$MODE" in
    omnivoice|xtts|chatterbox|piper)
        COMPOSE="$ROOT/compose.engines.proxmox.yaml"
        SERVICES=("$MODE")
        ;;
    all)
        COMPOSE="$ROOT/compose.engines.profiles.yaml"
        SERVICES=(omnivoice xtts chatterbox piper)
        ;;
    *)
        echo "Uzycie: $0 {omnivoice|xtts|chatterbox|piper|all} [plan|start]"
        exit 2
        ;;
esac

case "$ACTION" in
    plan)
        echo "=== PLAN: $MODE ==="
        docker compose -f "$COMPOSE" \
            --profile "$MODE" config --services
        echo "Bez uruchamiania kontenerow."
        exit 0
        ;;
    start)
        ;;
    *)
        echo "Nieznana operacja: $ACTION"
        exit 2
        ;;
esac

# Nie pozwalamy na start na aktywnym serwerze TASK.
if [[ "$(hostname -s)" == "ksmvm1" ]]; then
    echo "STOP: uruchamianie zabronione na ksmvm1."
    exit 1
fi

# Bramka: budowanie i synteza musza byc
# zweryfikowane osobnym testem przed startem.
if [[ ! -f "$ROOT/BUILD-AND-SYNTHESIS-VERIFIED" ]]; then
    echo "STOP: kandydat nie przeszedl jeszcze testu odtworzenia."
    exit 1
fi

if [[ "$MODE" != "piper" ]]; then
    command -v nvidia-smi >/dev/null || {
        echo "STOP: brak nvidia-smi"
        exit 1
    }

    nvidia-smi -L >/dev/null || {
        echo "STOP: GPU NVIDIA niedostepne"
        exit 1
    }

    if [[ "$MODE" == "all" ]]; then
        GPU_RAM="$(nvidia-smi \
            --query-gpu=memory.total \
            --format=csv,noheader,nounits | head -n1 | tr -d ' ')"

        [[ "$GPU_RAM" =~ ^[0-9]+$ ]] || exit 1

        if (( GPU_RAM < 40960 )); then
            echo "STOP: profil all wymaga osobnej walidacji na duzym GPU."
            exit 1
        fi
    fi

    # Odmawiamy startu GPU, gdy inny dzialajacy
    # kontener Docker deklaruje dostep do GPU.
    python3 - <<'PY'
import json
import subprocess

ids = subprocess.check_output(
    ["docker", "ps", "-q"], text=True
).split()

if ids:
    containers = json.loads(
        subprocess.check_output(
            ["docker", "inspect", *ids], text=True
        )
    )
else:
    containers = []

busy = []

for c in containers:
    requests = (
        c.get("HostConfig", {}).get("DeviceRequests") or []
    )
    for request in requests:
        caps = request.get("Capabilities") or []
        if any("gpu" in group for group in caps):
            busy.append(c["Name"].lstrip("/"))
            break

if busy:
    raise SystemExit(
        "STOP: aktywne kontenery GPU: "
        + ", ".join(busy)
    )

print("Kontrola innych kontenerow GPU: PASS")
PY
fi

echo "=== START: $MODE ==="

docker compose -f "$COMPOSE" \
    --profile "$MODE" up -d --no-build "${SERVICES[@]}"
