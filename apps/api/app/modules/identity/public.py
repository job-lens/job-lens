from dataclasses import dataclass

from app.core.types import Actor


@dataclass(frozen=True)
class MediaPreferences:
    quiet_mode: bool
    speech_enabled: bool
    vibration_enabled: bool
    volume: float

    @property
    def can_speak(self) -> bool:
        return not self.quiet_mode and self.speech_enabled and self.volume > 0

    @property
    def can_vibrate(self) -> bool:
        return not self.quiet_mode and self.vibration_enabled


__all__ = ["Actor", "MediaPreferences"]
