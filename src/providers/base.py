from abc import ABC, abstractmethod

class BaseProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, system: str = "") -> str:
        """Send a prompt, return the text response."""
        pass