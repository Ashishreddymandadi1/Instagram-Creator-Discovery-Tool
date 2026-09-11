#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/frontend"
[ -d node_modules ] || npm install
exec npm run dev
