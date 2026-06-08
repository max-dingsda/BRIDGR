from __future__ import annotations

from datetime import UTC, datetime
import json

from core.app_config import AppConfig, resolve_runtime_output_path


def write_debug_log(config: AppConfig, event: str, details: dict) -> None:
    if not config.debug_mode:
        return

    try:
        output_dir, _ = resolve_runtime_output_path(config.output_path)
        log_path = output_dir / "debug.log"
        entry = {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "event": event,
            "details": details,
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")
    except OSError:
        return
