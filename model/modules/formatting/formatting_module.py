from modules.abstract_module import AbstractModule
from pathlib import Path
import re
from renderer import Renderer
from schema import Schema
import schema
from typing import Optional
import os
from renderer import Renderer
from jinja2 import Environment, FileSystemLoader, select_autoescape
from collections import defaultdict


class FormattingModule(AbstractModule):

  def schema(self):
    formatting_rule = {
        #
        str: [
            schema.Or(
                str,  # reference to a token
                {"separator": str},  # separator string
                {"prefix": str},
                {"suffix": str},
                {"reference": str},  # Reference to a rule
            )
        ]
    }

    return Schema({
        schema.Optional("named-formatting-rules"): {
            str: formatting_rule
        },
        schema.Optional("formatting-rules"): formatting_rule
    })

  def css(self) -> str:
    return """
    <style>
    .formatting_token {
      border: 1px solid #00bcd4;
      padding: 2px;
      margin-left: 2px;
      margin-right: 2px;
      display: inline-block;
    }
    .formatting_token_separator, .formatting_token_prefix, .formatting_token_suffix {
      font-family: 'Courier New', Courier, monospace;
      padding: 2px;
      margin: 1px;
    }
    .formatting_token_separator {
      background-color: azure;
    }
    .formatting_token_prefix, .formatting_token_suffix {
      background-color: beige;
    }
    </style>
    """

  def observe_file(self, path: Path, renderer: Renderer):
    match = re.fullmatch(r'(?P<country>..|global)-formatting-rules\.yaml',
                         path.name)
    if not match:
      return
    country = match.groupdict()['country']
    renderer.add_country(country)

    yaml = self.read_yaml(path)

    named_formatting_rules = yaml.get('named-formatting-rules', {})
    formatting_rules = yaml.get('formatting-rules', {})

    # Rewrite for easier internal handling.
    for _, input in formatting_rules.items():
      for i in range(len(input)):
        if type(input[i]) == str:
          input[i] = {'token': input[i]}

    for name, rule in named_formatting_rules.items():
      for _, input in rule.items():
        for i in range(len(input)):
          if type(input[i]) == str:
            input[i] = {'token': input[i]}

    renderer.country_data[country]['named-formatting-rules'] = (
        named_formatting_rules)
    renderer.country_data[country]['formatting-rules'] = formatting_rules

  def render_token_details(self, country: str, token_id: str,
                           renderer: Renderer) -> Optional[str]:
    env = Environment(
        extensions=['jinja2.ext.do'],
        loader=FileSystemLoader(os.path.join(os.path.dirname(__file__))),
        autoescape=select_autoescape())
    template = env.get_template("formatting_template.html")
    model = renderer.country_data[country]["model"]

    token = model.find_token(token_id)
    if not token or token.is_atomic_token():
      return

    named_formatting_rules = (
        renderer.country_data[country].get('named-formatting-rules', {}))
    formatting_rules = (
        renderer.country_data[country].get('formatting-rules', {}))

    inputs = formatting_rules.get(token_id, None)
    if not inputs:
      return None

    if len(inputs) == 1 and 'reference' in inputs[0]:
      rule = named_formatting_rules.get(inputs[0]['reference'], [])
      inputs = rule.get(token_id, None)

    return template.render(model=model, token_id=token_id, inputs=inputs)
