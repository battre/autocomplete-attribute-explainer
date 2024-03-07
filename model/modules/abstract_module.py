from abc import ABC
from pathlib import Path
from ruamel.yaml import YAML
from typing import Any, Optional, Dict
from schema import Schema, SchemaError
from renderer import Renderer, ExtraPage
from jinja2 import Environment, FileSystemLoader, select_autoescape, Template
import os
import re


class AbstractModule(ABC):

  _cls_templates: Dict[str, Template] = {}

  @classmethod
  def get_template(cls, current__file__, template_file):
    base_path = os.path.dirname(current__file__)
    key = os.path.join(base_path, template_file)
    if key not in cls._cls_templates:
      env = Environment(extensions=['jinja2.ext.do'],
                        loader=FileSystemLoader(
                            os.path.dirname(current__file__)),
                        autoescape=select_autoescape())
      env.filters['regex_replace'] = lambda s, find, replace: re.sub(
          find, replace, s)
      cls._cls_templates[key] = env.get_template(template_file)
    return cls._cls_templates[key]

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
    if schema and yaml:
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

  def render_after_token_index(self, country: str,
                               renderer: Renderer) -> Optional[str]:
    return None

  def render_token_details(self, country: str, token_id: str,
                           renderer: Renderer) -> Optional[str]:
    return None

  def render_epilogue(self, country: str, renderer: Renderer) -> Optional[str]:
    return None

  def post_processing(self, renderer: Renderer):
    return None

  # Enables a vendor extension to register extra files that it generates.
  # E.g. if an extension generates "<country>-foo.html" files, it would return
  # this here. By default vendor extensions don't create their own html files
  # and should return the empty list.
  def get_extra_pages(self) -> list[ExtraPage]:
    return []
