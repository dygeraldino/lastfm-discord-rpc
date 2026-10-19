from abc import ABC, abstractmethod
from typing import Optional

from src.domain.entities.song_override import SongOverride


class SongOverrideRepository(ABC):
    @abstractmethod
    def get(self, artist: str, title: str) -> Optional[SongOverride]:
        pass

    @abstractmethod
    def all(self) -> list[SongOverride]:
        pass

    @abstractmethod
    def save(self, override: SongOverride) -> None:
        pass

    @abstractmethod
    def remove(self, artist: str, title: str) -> bool:
        pass
