# Settings shared by the emulator scripts (sourced, not run).
#
# The emulator (granny-smith's gs-headless), first found of:
#   $GS_HEADLESS
#   build/gs/gs-headless                (a granny-smith release binary)
#   gs-headless on the PATH
#   ../granny-smith/build/headless/gs-headless   (a checkout next to lisa-c)
#
# Your own copies of the Apple software (never part of this repository):
#   LISA_ROM        Lisa 2 boot ROM, rev H       default media/lisa.rom
#   LOS_IMAGE       Office System 3.1 installed on a ProFile
#                                                default media/los31.image
#   WORKSHOP_IMAGE  Workshop 3.0 installed on a ProFile (DiskCopy or raw)
#                                                default media/workshop.image
LISA_C="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -z "${GS_HEADLESS:-}" ]; then
    for c in "$LISA_C/build/gs/gs-headless" "$(command -v gs-headless || true)" \
             "$LISA_C/../granny-smith/build/headless/gs-headless"; do
        if [ -n "$c" ] && [ -x "$c" ]; then GS_HEADLESS="$c"; break; fi
    done
fi
LISA_ROM="${LISA_ROM:-$LISA_C/media/lisa.rom}"
LOS_IMAGE="${LOS_IMAGE:-$LISA_C/media/los31.image}"
WORKSHOP_IMAGE="${WORKSHOP_IMAGE:-$LISA_C/media/workshop.image}"

need() {    # need FILE WHAT
    if [ ! -e "$1" ]; then
        echo "error: $2 not found: $1" >&2
        exit 1
    fi
}
need_emulator() {
    if [ -z "${GS_HEADLESS:-}" ]; then
        echo "error: no gs-headless: set GS_HEADLESS, put it on the PATH or in build/gs/" >&2
        exit 1
    fi
}
