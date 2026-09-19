from dataclasses import dataclass
from uuid import UUID

from app.core.types import Actor, Role


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


@dataclass(frozen=True)
class UserView:
    """Identity as other layers may see it; roles are ordered so responses stay stable."""

    id: UUID
    display_name: str
    roles: tuple[Role, ...]


__all__ = ["Actor", "MediaPreferences", "UserView"]
