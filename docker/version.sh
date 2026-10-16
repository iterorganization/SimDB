#!/bin/sh
# Derive the version from git tags, in the forms the build needs.
#
# Shared by the Makefile and .github/workflows/docker_image.yml so that the
# local build and CI cannot drift.
#
# Usage:
#   docker/version.sh [gitdescribe|pep440|dockertag]
#
# Modes (default: pep440):
#   gitdescribe  raw `git describe --tags --always`, e.g. 0.15.2-347-g23a0424
#   pep440       PEP 440,                                e.g. 0.15.2.dev347+g23a0424
#   dockertag    PEP 440 with the "+<local>" segment removed,
#                                                        e.g. 0.15.2.dev347
#                (a Docker tag allows only [A-Za-z0-9_.-])
#
# A commit on a tag describes as "<tag>"; a commit between tags as
# "<tag>-<n>-g<sha>". The "+<local>" segment is dropped inside the image too
# (SETUPTOOLS_SCM_OVERRIDES_FOR_IMAS_SIMDB, local_scheme = no-local-version-strict),
# so the image tag and `simdb --version` agree.
#
# Examples:
#
#   on a tag (HEAD == 0.15.2):
#     gitdescribe  0.15.2
#     pep440       0.15.2
#     dockertag    0.15.2            # git tag, image tag and `simdb --version` agree
#
#   347 commits after 0.15.2:
#     gitdescribe  0.15.2-347-g23a0424
#     pep440       0.15.2.dev347+g23a0424
#     dockertag    0.15.2.dev347
#
#   Notes:
#     * If several tags point at the same commit, git describe picks one
#       (annotated first, then most recent) -- not necessarily the one you have
#       in mind.
#     * A non-PEP-440 tag name (e.g. v0.15.2) is passed through verbatim.
#     * A dirty working tree is not reported; the script does not use --dirty.

set -eu

mode=${1:-pep440}

gitdescribe=$(git describe --tags --always 2>/dev/null) || gitdescribe=

# "0.15.2-347-g23a0424" -> "0.15.2.dev347+g23a0424"
pep440=$(printf '%s\n' "$gitdescribe" \
    | sed -r 's/-([0-9]+)-g([0-9a-f]+)$/.dev\1+g\2/')

# An empty version (no git, or a tagless shallow checkout) is not valid PEP 440.
if [ -z "$pep440" ]; then
    pep440=0.0.0
fi

case "$mode" in
    gitdescribe) printf '%s\n' "$gitdescribe" ;;
    pep440)      printf '%s\n' "$pep440" ;;
    dockertag)   printf '%s\n' "${pep440%%+*}" ;;
    *)           printf 'usage: %s [gitdescribe|pep440|dockertag]\n' "$0" >&2; exit 2 ;;
esac