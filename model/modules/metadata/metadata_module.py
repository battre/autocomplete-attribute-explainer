from renderer import Renderer
from modules.abstract_module import AbstractModule
from pathlib import Path
from typing import Any, Optional
from schema import Schema
import schema
import re
from renderer import Renderer
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os


class MetadataModule(AbstractModule):

  def schema(self):
    return Schema({
        # The country name as a two letter code
        "country":
            str,
        # A flag as a UTF-8 symbol
        schema.Optional("flag"):
            str,
        # HTML code to be rendered as the overview of a country
        schema.Optional("overview"):
            str
    })

  def observe_file(self, path: Path, renderer: Renderer):
    match = re.fullmatch(r'(?P<country>..|global)-metadata\.yaml', path.name)
    if not match:
      return

    country = match.groupdict()['country']
    yaml = self.read_yaml(path)
    renderer.country_data[country][self.name()] = yaml
    renderer.add_country(country)

  def render_preamble(self, country: str, renderer: Renderer) -> Optional[str]:
    env = Environment(
        extensions=['jinja2.ext.do'],
        loader=FileSystemLoader(os.path.join(os.path.dirname(__file__))),
        autoescape=select_autoescape())
    template = env.get_template("template.html")
    return template.render(yaml=renderer.country_data[country][self.name()])