from abc import ABC, abstractmethod
from typing import List


class BaseLock(ABC):
    @abstractmethod
    def acquire(self, key: str, tests: List[str], groups: List[str], timeout: float) -> bool:
        pass

    @abstractmethod
    def release(self, key: str) -> None:
        pass

    # @abstractmethod
    # def is_locked(self, key: str) -> list:
    #     pass