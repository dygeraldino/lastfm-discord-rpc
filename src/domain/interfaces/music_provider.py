from abc import ABC, abstractmethod
from typing import Optional
from src.domain.entities.track import Track


class MusicProvider(ABC):
    @abstractmethod
    async def get_current_track(self) -> Optional[Track]:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass