#!/bin/sh
set -eu
cd "$(dirname "$0")"
export PLATFORMIO_CORE_DIR="$PWD/.platformio"
exec .venv/bin/python -m platformio run "$@"
