from abc import ABC, abstractmethod
from typing import Optional


class ArtworkProvider(ABC):
    @abstractmethod
    async def get_artwork_url(self, artist: str, title: str, album: str = "") -> Optional[str]:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass