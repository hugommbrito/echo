class AIError(Exception):
    """Provider call failed after the SDK's own retries (network, 5xx, malformed output)."""


class AIRefusal(AIError):
    """The model declined to answer (stop_reason == "refusal")."""


class AIAuthError(AIError):
    """The provider rejected the API key (HTTP 401/403): invalid, revoked or lacking permission."""


class AIConfigurationError(AIError):
    """No usable API key for the provider this call needs (neither the user's nor a global one)."""


class TranscriptionError(AIError):
    pass


class SpeechSynthesisError(AIError):
    """Text-to-speech failed; the card stays usable without audio."""


class AudioProbeError(Exception):
    """ffprobe could not read the file (corrupt, empty or unsupported container)."""
