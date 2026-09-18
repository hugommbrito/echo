class AIError(Exception):
    """Provider call failed after the SDK's own retries (network, 5xx, malformed output)."""


class AIRefusal(AIError):
    """The model declined to answer (stop_reason == "refusal")."""


class TranscriptionError(AIError):
    pass


class AudioProbeError(Exception):
    """ffprobe could not read the file (corrupt, empty or unsupported container)."""
