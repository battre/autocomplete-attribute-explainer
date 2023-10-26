from modules.abstract_module import AbstractModule
from modules.model.model import Model
from pathlib import Path
import re
from renderer import Renderer
from schema import Schema
import schema
from typing import Optional, List
import copy
import difflib


class ComparisonStopwordsModule(AbstractModule):
  """Defines stopwords for comparing tokens.

  Formatting can add tokens to a string. E.g. the formatting rule
  ```
  in-building-location:
  - prefix: "Apt. "
  - unit
  - separator: ", "
  - prefix: "Floor "
  - floor
  ```
  adds the strings "Apt. " and "Floor ".

  Stop words are tokens that should be ignored when comparing tokens. So the
  stop words for 'in-building-location' could be defined as
  ```
  in-building-location: Apt\.|Floor
  ```
  """

  def schema(self):
    return Schema({str: str})

  def observe_file(self, path: Path, renderer: Renderer):
    match = re.fullmatch(r'(?P<country>..|global)-comparison-stopwords\.yaml',
                         path.name)
    if not match:
      return
    country = match.groupdict()['country']
    renderer.add_country(country)

    yaml = self.read_yaml(path) or {}

    stop_words = renderer.country_data['global'].get('comparison-stopwords', {})
    stop_words = stop_words | yaml
    renderer.country_data[country]['comparison-stopwords'] = stop_words

  def render_token_details(self, country: str, token_id: str,
                           renderer: Renderer) -> Optional[str]:
    stop_words = renderer.country_data[country].get('comparison-stopwords', {})
    template = ComparisonStopwordsModule.get_template(
        __file__, "comparison_stopwords_template.html")
    kwargs = {
        'comparison_stopwords': stop_words,
        'token_id': token_id,
    }
    return template.render(**kwargs)
