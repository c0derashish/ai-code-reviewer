from abc import ABC, abstractmethod


class BaseValidator(ABC):

    @abstractmethod
    def validate(self, code: str) -> dict:
        pass