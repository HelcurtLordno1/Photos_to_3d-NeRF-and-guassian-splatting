"""Separate presentation settings without weakening immutable experiment identity."""

from __future__ import annotations

import re

from topic16.contracts import digest_json

UI_FIELDS = {
    "SchemaVersion",
    "NodeVersion",
    "Port",
    "MaxPort",
    "CacheBytes",
    "LeaseSeconds",
    "HeartbeatSeconds",
    "MaxPixels",
    "DecodeLimitBytes",
    "MaxVertices",
    "Packages",
    "DevPackages",
    "Selection",
    "DevPort",
}
UI_PACKAGES = {
    "react",
    "react-dom",
    "three",
    "@sparkjsdev/spark",
    "lucide-react",
    "mermaid",
    "vite",
    "typescript",
    "@vitejs/plugin-react",
    "@types/react",
    "@types/react-dom",
    "@types/node",
    "@types/three",
    "vitest",
    "@playwright/test",
    "@axe-core/playwright",
    "prettier",
}


def validate_ui_settings(ui: dict) -> None:
    if not isinstance(ui, dict) or set(ui) - UI_FIELDS:
        raise ValueError("Ui contains unknown or experiment-related settings")
    if ui.get("SchemaVersion", 1) != 1:
        raise ValueError("Unsupported UI settings schema")
    for key, value in ui.items():
        if key in ("Packages", "DevPackages"):
            if not isinstance(value, dict) or set(value) - UI_PACKAGES:
                raise ValueError("Unknown UI dependency")
            if any(
                not isinstance(v, str)
                or not re.fullmatch(r"\d+\.\d+\.\d+(?:-[\w.]+)?", v)
                for v in value.values()
            ):
                raise ValueError("UI dependencies must use exact version pins")
        elif key in ("NodeVersion", "Selection"):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Invalid UI {key}")
        elif isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"Invalid UI numeric setting {key}")


def experiment_settings(settings: dict) -> dict:
    if "Ui" in settings:
        validate_ui_settings(settings["Ui"])
    return {key: value for key, value in settings.items() if key != "Ui"}


def experiment_settings_hash(settings: dict) -> str:
    return digest_json(experiment_settings(settings))


def ui_settings_hash(settings: dict) -> str:
    validate_ui_settings(settings.get("Ui", {}))
    return digest_json(settings.get("Ui", {}))


def assert_experiment_compatible(
    current: dict, recorded: dict, expected: str | None = None
) -> dict:
    """Only a validated Ui section may differ; no experiment field is ignored."""
    recorded_hash = experiment_settings_hash(recorded)
    if expected is not None and recorded_hash != expected:
        raise ValueError("Recorded experiment snapshot checksum differs")
    if experiment_settings_hash(current) != recorded_hash:
        raise ValueError(
            "Training/data/runtime/safety settings differ from the recorded experiment"
        )
    return {
        "schema_version": "ui-settings-compatibility-1",
        "experiment_settings_hash": recorded_hash,
        "recorded_registry_hash": digest_json(recorded),
        "current_registry_hash": digest_json(current),
        "ui_settings_hash": ui_settings_hash(current),
        "accepted_delta": "Ui only",
    }
