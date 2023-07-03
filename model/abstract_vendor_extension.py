from abc import ABC, abstractmethod
from modules.abstract_module import AbstractModule
from pathlib import Path


class AbstractVendorExtension(ABC):

  @abstractmethod
  def modify_modules_list(self, modules: list[AbstractModule]
                         ) -> list[AbstractModule]:
    pass

  @abstractmethod
  def modify_global_files_list(self, files: list[Path]) -> list[Path]:
    pass

  @abstractmethod
  def modify_other_files_list(self, files: list[Path]) -> list[Path]:
    pass