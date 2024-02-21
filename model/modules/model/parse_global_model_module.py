from renderer import Renderer
from modules.abstract_module import AbstractModule
from pathlib import Path
from typing import Any, List
from schema import Schema
import sys
import re
from renderer import Renderer
from jinja2 import Environment, FileSystemLoader, select_autoescape
from modules.model.model import AtomicOrCompoundToken, AtomicToken, CompoundToken, Model


class ParseGlobalModelModule(AbstractModule):

  def schema(self):
    return Schema({
        # Recursive structure of concepts.
        #
        # Each concept has a name.
        # Atomic concepts are represented as strings (leafs of the tree).
        # Compound concepts are represented as a dictionary with a single entry:
        # The key represents the name of the concept, the value is a list of
        # concepts.
        "concepts": list,
    })

  def _parse_atomic_token_and_insert_to_model(self, yaml: str,
                                              model: Model) -> str:
    id = yaml
    model.add_token(AtomicToken(model, id))
    return id

  def _parse_compound_token_and_insert_to_model(self, yaml: dict,
                                                model: Model) -> str:
    keys = list(yaml)
    assert len(keys) == 1
    id = keys[0]
    children: List[str] = [
        self._parse_token_and_insert_to_model(child, model)
        for child in yaml[id]
    ]
    model.add_token(CompoundToken(model, id, children))
    return id

  def _parse_token_and_insert_to_model(self, yaml: Any, model: Model) -> str:
    if type(yaml) == dict:
      return self._parse_compound_token_and_insert_to_model(yaml, model)
    elif type(yaml) == str:
      return self._parse_atomic_token_and_insert_to_model(yaml, model)
    else:
      sys.exit(f"Unexpected typed {type(yaml)}: {yaml}")

  def observe_file(self, path: Path, renderer: Renderer):
    match = re.fullmatch(r'(?P<country>global)-model\.yaml', path.name)
    if not match:
      return
    country = match.groupdict()['country']
    renderer.add_country(country)

    model = Model()

    yaml = self.read_yaml(path)
    for yaml_token in yaml['concepts']:
      id = self._parse_token_and_insert_to_model(yaml_token, model)
      model.root_concepts.append(id)

    renderer.set_model(country, model)
