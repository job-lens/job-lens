from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Marker:
    x: float
    y: float
    text: str
    width: float | None = None
    height: float | None = None

    def validate(self) -> None:
        if not self.text.strip() or len(self.text) > 200:
            raise ValueError("marker text must contain 1..200 characters")
        if not all(isfinite(v) and 0 <= v <= 1 for v in (self.x, self.y)):
            raise ValueError("point lies outside the image")
        if (self.width is None) != (self.height is None):
            raise ValueError("rectangle requires both width and height")
        if self.width is not None and self.height is not None:
            if not all(isfinite(v) and 0 < v <= 1 for v in (self.width, self.height)):
                raise ValueError("rectangle dimensions must be positive")
            if self.x + self.width > 1 or self.y + self.height > 1:
                raise ValueError("rectangle extends beyond image bounds")
