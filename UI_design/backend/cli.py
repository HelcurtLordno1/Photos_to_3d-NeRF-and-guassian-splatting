from __future__ import annotations
import argparse
from pathlib import Path
from topic16.contracts import read_json
from .catalog import prepare
from .server import serve


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--settings", type=Path, required=True)
    subs = parser.add_subparsers(dest="command", required=True)
    prep = subs.add_parser("prepare")
    prep.add_argument("--extra-matrix", type=Path)
    start = subs.add_parser("serve")
    start.add_argument("--port", type=int)
    start.add_argument(
        "--profile", choices=("auto", "artifacts", "inference"), default="auto"
    )
    args = parser.parse_args()
    settings = read_json(args.settings)
    if args.command == "prepare":
        payload = prepare(args.root, settings, args.extra_matrix)
        print(
            f"Prepared {len(payload['catalog']['scenes'])} scenes, {len(payload['assets'])} verified assets.",
            flush=True,
        )
    else:
        serve(args.root, settings, args.port, args.profile)


if __name__ == "__main__":
    main()
