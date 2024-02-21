from renderer import Renderer
from modules.abstract_module import AbstractModule
from pathlib import Path
from typing import Any, List
from schema import Schema
import schema
import re
from renderer import Renderer
from modules.model.model import Model, Translation


class ParseDescriptionsModelModule(AbstractModule):

  def schema(self):
    return Schema({
        schema.Optional("short-descriptions"): {
            str: schema.Or(str, {str: str})
        },
    })

  def _parse_short_descriptions(self, model: Model, yaml: Any) -> None:
    short_descriptions = yaml.get('short-descriptions', {})
    for field, translation in short_descriptions.items():
      model.short_descriptions[field] = Translation(translation)

  def observe_file(self, path: Path, renderer: Renderer):
    match = re.fullmatch(r'(?P<country>..|global)-descriptions\.yaml',
                         path.name)
    if not match:
      return
    country = match.groupdict()['country']
    renderer.add_country(country)

    # It's guaranteed that the models have been loaded already.
    model = renderer.get_model(country)
    yaml = self.read_yaml(path)

    self._parse_short_descriptions(model, yaml)
