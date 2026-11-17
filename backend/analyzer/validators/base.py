from abc import ABC, abstractmethod


class BaseValidator(ABC):

    @abstractmethod
    def validate(self, code: str, file_path: str = "<unknown>") -> dict:
        pass