"""Audio probing with ffprobe: real duration and container validity (the source of truth)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from django.conf import settings

from apps.ai.clients.base import ProbeResult
from apps.ai.exceptions import AudioProbeError


class FFProbe:
    def probe(self, path: str | Path) -> ProbeResult:
        path = Path(path)
        if not path.exists() or path.stat().st_size == 0:
            raise AudioProbeError("Audio file is empty.")
        cmd = [
            settings.ECHO_FFPROBE_BIN,
            "-v",
            "error",
            "-show_entries",
            "format=duration,format_name",
            "-of",
            "json",
            str(path),
        ]
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        except FileNotFoundError as exc:
            raise AudioProbeError("ffprobe is not installed on this worker.") from exc
        except subprocess.TimeoutExpired as exc:
            raise AudioProbeError("ffprobe timed out.") from exc
        if completed.returncode != 0:
            raise AudioProbeError(f"ffprobe failed: {completed.stderr.strip()[:300]}")
        try:
            fmt = json.loads(completed.stdout or "{}").get("format", {})
            duration = float(fmt.get("duration"))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise AudioProbeError(
                "ffprobe returned no duration (corrupt or unsupported file)."
            ) from exc
        if duration <= 0:
            raise AudioProbeError("Audio has zero duration.")
        return ProbeResult(duration_seconds=duration, format_name=fmt.get("format_name", ""))
