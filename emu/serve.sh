#!/usr/bin/env bash
# Run a lisa-c floppy interactively: serve granny-smith's web build locally
# and print a link that boots a Lisa 2 with the Office System 3.1 ProFile and
# the floppy in the drive.  Open the link in a browser; insert-and-Repair,
# open the diskette and tear off a sheet as on a real Lisa.
#
#   emu/serve.sh floppy.dc42 [port]
#
# The emulator: granny-smith's web build GS_VERSION (a release zip, downloaded
# once into build/gs-web/), or the directory GS_WEB (an unpacked zip).
#
# The Lisa ROM and the Office System ProFile: your own files when present
# (LISA_ROM, LOS_IMAGE, by default media/lisa.rom and media/los31.image; see
# emu/env.sh), served from the same local server; otherwise links to copies on
# archive.org (the two halves of the rev-H ROM and an installed LOS 3.1
# ProFile), which the page fetches itself.  MEDIA=archive forces the links.
#
# Everything is served from one local origin (no CORS, nothing published).
# In a GitHub Codespace, VS Code forwards the port; the script prints both the
# local and the forwarded address.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

FLOPPY="$(realpath "${1:?usage: emu/serve.sh floppy.dc42 [port]}")"
PORT="${2:-${PORT:-8080}}"
GS_VERSION="${GS_VERSION:-v0.9.3}"     # the first release with the Lisa floppy-at-boot fix
GS_REPO="https://github.com/pappadf/granny-smith"
WEB="${GS_WEB:-$LISA_C/build/gs-web/$GS_VERSION}"
STAGE="$LISA_C/build/serve"

# archive.org copies (as on granny-smith's Boot Shelf)
ROM_A="https://ia600103.us.archive.org/view_archive.php?archive=/21/items/lisa-software/Lisa%20Software.zip&file=Lisa%20Software%2Ffirmware%2F341-0175-H.BIN"
ROM_B="https://ia600103.us.archive.org/view_archive.php?archive=/21/items/lisa-software/Lisa%20Software.zip&file=Lisa%20Software%2Ffirmware%2F341-0176-H.BIN"
LOS_URL="https://ia600806.us.archive.org/view_archive.php?archive=/22/items/apple-lisa-profile-hd-disk-images-for-lisaem-and-idle-lisa-office-system-3.1-lis/IDLE_LOS3.1-after1stBoot.zip&file=profile.raw"

# ---- the emulator ----------------------------------------------------------
if [ ! -f "$WEB/web/index.html" ]; then
    [ -z "${GS_WEB:-}" ] || need "$WEB/web/index.html" "granny-smith web build (GS_WEB)"
    echo "Downloading granny-smith $GS_VERSION (web build)..."
    tmp="$WEB.part"
    rm -rf "${tmp:?}" && mkdir -p "$tmp"
    zip="granny-smith-web-$GS_VERSION.zip"
    if ! curl -fsSL --retry 3 -o "$tmp/$zip" "$GS_REPO/releases/download/$GS_VERSION/$zip"; then
        rm -rf "${tmp:?}"
        echo "error: no $zip in $GS_REPO/releases (is $GS_VERSION published?);" >&2
        echo "       set GS_VERSION to another release, or GS_WEB to an unpacked web build" >&2
        exit 1
    fi
    curl -fsSL --retry 3 -o "$tmp/SHA256SUMS" "$GS_REPO/releases/download/$GS_VERSION/SHA256SUMS"
    (cd "$tmp" && grep " $zip\$" SHA256SUMS | sha256sum -c --quiet -)
    unzip -q "$tmp/$zip" -d "$tmp"
    rm -f "$tmp/$zip" "$tmp/SHA256SUMS"
    rm -rf "${WEB:?}" && mv "$tmp" "$WEB"
fi

# ---- what the page loads: the floppy, and the ROM and ProFile ---------------
rm -rf "${STAGE:?}" && mkdir -p "$STAGE/media"
name="$(basename "$FLOPPY")"
ln -s "$FLOPPY" "$STAGE/$name"
if [ "${MEDIA:-}" != archive ] && [ -e "$LISA_ROM" ] && [ -e "$LOS_IMAGE" ]; then
    ln -s "$(realpath "$LISA_ROM")" "$STAGE/media/lisa.rom"
    ln -s "$(realpath "$LOS_IMAGE")" "$STAGE/media/los31.image"
    roms=("/media/lisa.rom"); hd="/media/los31.image"; from="your own files ($LISA_C/media)"
else
    roms=("$ROM_A" "$ROM_B"); hd="$LOS_URL"; from="archive.org"
fi
QS="$(python3 -I - "$name" "$hd" "${roms[@]}" <<'PYEOF'
import sys, urllib.parse
floppy, hd, *roms = sys.argv[1:]
q = [('rom', r) for r in roms] + [('hd0', hd), ('fd0', '/' + floppy)]
print('&'.join(k + '=' + urllib.parse.quote(v, safe='/') for k, v in q))
PYEOF
)"

echo
echo "Lisa 2, Office System 3.1 (ROM and ProFile from $from),"
echo "floppy $name.  Open:"
if [ -n "${CODESPACE_NAME:-}" ]; then
    echo "  https://$CODESPACE_NAME-$PORT.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}/"
    echo "  (or http://localhost:$PORT/ from VS Code desktop)"
else
    echo "  http://localhost:$PORT/"
fi
echo "Rebuild the floppy and reload the page to run the new version.  Ctrl-C stops the server."
echo
exec python3 -I "$(dirname "${BASH_SOURCE[0]}")/serve.py" "$WEB" "$STAGE" "$PORT" "$QS"
