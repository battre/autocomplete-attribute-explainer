from abc import ABC
from pathlib import Path
from ruamel.yaml import YAML
from typing import Any, Optional
from schema import Schema, SchemaError
from renderer import Renderer


class AbstractModule(ABC):
  def name(self) -> str:
    """Returns the name of the """
    return self.__class__.__name__

  def observe_file(self, path: Path, renderer: Renderer):
    """Allows the module to read a file if it's relevant for the module."""
    pass

  def schema(self) -> Optional[Schema]:
    return None

  def read_yaml(self, file: Path) -> Any:
    yaml = YAML(typ='safe').load(open(file, "rb").read())

    schema = self.schema()
    if schema:
      try:
        schema.validate(yaml)
      except SchemaError as se:
        print(f"Failed verifying schema of {file} with content:\n{yaml}")
        raise se

    return yaml

  def css(self) -> Optional[str]:
    """Returns any module specific CSS style code that should be included.

    The value should be a string of the form "<style>...</style>".
    """
    return None

  def javascript(self) -> Optional[str]:
    """Returns any module specific JavaScript code that should be included.

    The value should be a string of the form "<script>...</script>".
    """
    return None

  def render_preamble(self, country: str, renderer: Renderer) -> Optional[str]:
    return None

  def render_token_index(self, country: str,
                         renderer: Renderer) -> Optional[str]:
    return None

  def render_token_details(self, country: str, token_id: str,
                           renderer: Renderer) -> Optional[str]:
    return None

  def render_epilogue(self, country: str, renderer: Renderer) -> Optional[str]:
    return None
