#!/usr/bin/env python3
"""Check whether a stored SimDB IMAS checksum is reproducible from a directory.

The IMAS checksum (``simdb/imas/checksum.py``) streams the *contents* of the
selected ``.h5`` files into a single SHA1.  Two things therefore change the
result without any file content changing:

  * the file selection, driven by the IDS list passed by the caller, and
  * the iteration order, which is whatever ``Path.glob()`` returns -- i.e. the
    filesystem's readdir order, which follows directory insertion order on
    btrfs and so differs between machines and after any re-write.

This script takes the selection out of the equation by enumerating *every*
possible file selection (``master`` and IDS-occurrence files are always
included, matching the filter in ``checksum()``) in the directory's own glob
order, and reporting whether any of them reproduces the expected checksum.

If none does, the expected checksum cannot be regenerated from this directory
as it currently stands -- the data it was computed over, or the order it was
computed in, no longer exists.

Only stdlib is used, so it can be run anywhere the data lives.

Usage:
    python check_imas_checksum.py <imas-dir> <expected-sha1> [--max-omit K]
                                  [--jobs N] [--quiet]

Example:
    python check_imas_checksum.py /work/imas/shared/imasdb/ITER/3/105083/1 \
        a64ac215a930996e343970d9cc3271be6055e3b7
"""

import argparse
import hashlib
import mmap
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from math import comb
from pathlib import Path


def is_optional(path: Path) -> bool:
    """Whether checksum() includes this file only when its IDS is listed.

    Mirrors the filter in ``simdb.imas.checksum.checksum``: ``master.h5`` and
    files that are not a plain ``<ids>.h5`` (e.g. the ``<ids>.<occurrence>.h5``
    of a multi-occurrence IDS) are always hashed.
    """
    parts = path.name.split(".")
    return len(parts) > 1 and parts[1] == "h5" and parts[0] != "master"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("directory", type=Path, help="IMAS hdf5 directory to check")
    ap.add_argument("expected", help="the stored SHA1 checksum to reproduce")
    ap.add_argument("--max-omit", type=int, default=None, metavar="K",
                    help="only try selections omitting at most K optional IDSs "
                         "(default: try all subsets)")
    ap.add_argument("--jobs", type=int, default=8, metavar="N",
                    help="parallel hashing threads (default: 8)")
    ap.add_argument("--quiet", action="store_true", help="suppress progress output")
    args = ap.parse_args()

    files = list(args.directory.glob("*.h5"))
    if not files:
        print(f"no .h5 files found in {args.directory}", file=sys.stderr)
        return 2

    optional = [p for p in files if is_optional(p)]
    limit = len(optional) if args.max_omit is None else min(args.max_omit, len(optional))
    total = sum(comb(len(optional), k) for k in range(limit + 1))

    print(f"directory : {args.directory}")
    print(f"glob order: {', '.join(p.name for p in files)}")
    print(f"always in : {', '.join(p.name for p in files if not is_optional(p)) or '(none)'}")
    print(f"selections: {total} (omitting up to {limit} of {len(optional)} optional IDSs)")
    print(f"expected  : {args.expected}\n")

    with ExitStack() as stack, ThreadPoolExecutor(args.jobs) as pool:
        start = time.time()
        # Each state is (set-of-omitted-names, sha1 of the bytes hashed so far).
        # Walking the files in glob order lets all selections sharing a prefix
        # share that prefix's hashing work.
        states = [(frozenset(), hashlib.sha1())]
        for path in files:
            fh = stack.enter_context(path.open("rb"))
            data = stack.enter_context(mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ))

            def hashed(state, _data=data, _name=path.name):
                omitted, digest = state
                fork = digest.copy()
                fork.update(_data)
                return omitted, fork

            if is_optional(path):
                skipped = [(o | {path.name}, d) for o, d in states if len(o) < limit]
                states = list(pool.map(hashed, states)) + skipped
            else:
                states = list(pool.map(hashed, states))

            if not args.quiet:
                print(f"  {path.name:<34} {len(states):>7} selections "
                      f"[{time.time() - start:6.1f}s]", flush=True)

        matches = sorted((o for o, d in states if d.hexdigest() == args.expected), key=len)

    print()
    if matches:
        for omitted in matches:
            print("REPRODUCED by omitting:", ", ".join(sorted(omitted)) or "(nothing)")
        return 0

    print(f"NOT REPRODUCIBLE: none of the {len(states)} selections gives {args.expected}.")
    print("The stored checksum does not correspond to this directory's current")
    print("contents in its current glob order, under any IDS selection.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
