from abc import ABC, abstractmethod
from src.domain.entities.track import Track


class PresencePublisher(ABC):
    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    async def update(self, track: Track) -> None:
        pass

    @abstractmethod
    async def clear(self) -> None:
        pass