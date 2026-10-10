#!/usr/bin/env bash
# Build a 400K Lisa floppy image (volume "LisaC") holding the given files.
#   tools/mkdisk.sh out.dc42 file.obj [more files...]
# Each file keeps its basename as the Lisa file name.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 -I "$HERE/mklisafs.py" "$@"
