from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app_config import load_config
from env_loader import load_env_files
from pipeline import run_pipeline


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a minimal BRIDGR extraction flow.")
    parser.add_argument("--file", type=Path, help="Path to a BPMN file to process.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.json"),
        help="Path to the application config file.",
    )
    return parser


def main() -> int:
    load_env_files()
    args = build_argument_parser().parse_args()
    config = load_config(args.config)

    if args.file is None:
        run_result = run_pipeline(config)
        print(json.dumps({"documents": [asdict(document) for document in run_result.documents]}, indent=2, ensure_ascii=False))
        return 0

    run_result = run_pipeline(config, [args.file])
    print(json.dumps({"documents": [asdict(document) for document in run_result.documents]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
