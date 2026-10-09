#!/bin/bash
# Run all Nori tests (stdlib only):  tests/run.sh
cd "$(dirname "$0")" && exec python3 -B -m unittest discover -v -s . "$@"
