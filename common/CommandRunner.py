from __future__ import annotations
from abc import ABC, abstractmethod, abstractproperty
from typing import Tuple

'''
provides an interface for a set of modules responsible for executing 
commands (local, remote, via API, ssh, etc.): 
'''


class ICommandRunner(ABC):

    @abstractmethod
    def exec(self, cmd: str, timeout: int | None = None) -> Tuple[str, int]:
        """
        TODO: Description
        """
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def run_executable(self, cmd: str, timeout: float = 60.0) -> Tuple[str, int]:
        """
        TODO: Description
        """
        raise NotImplementedError("Not implemented")

    @property
    @abstractmethod
    def host(self) -> str:
        """
        TODO: Description
        """
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def upload_file(self, src_file: str, dst_file: str) -> None:
        """
        TODO: Description
        """
        raise NotImplementedError("Not implemented")


