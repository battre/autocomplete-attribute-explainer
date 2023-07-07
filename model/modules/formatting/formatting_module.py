from modules.abstract_module import AbstractModule
from modules.model.model import Model
from pathlib import Path
import re
from renderer import Renderer
from schema import Schema
import schema
from typing import Optional, List
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape
import copy


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
                # Item that should be skipped w/o generating an error:
                {"skip": str},
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
    .formatting_errors {
      color: red;
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

    # Inherit global rules.
    if country != 'global':
      renderer.country_data[country]['named-formatting-rules'] = copy.deepcopy(
          renderer.country_data['global']['named-formatting-rules'])
      renderer.country_data[country]['formatting-rules'] = copy.deepcopy(
          renderer.country_data['global']['formatting-rules'])
    else:
      renderer.country_data[country]['named-formatting-rules'] = {}
      renderer.country_data[country]['formatting-rules'] = {}

    # Now copy the new rules to the existing ones.
    for key, value in named_formatting_rules.items():
      renderer.country_data[country]['named-formatting-rules'][key] = value
    for key, value in formatting_rules.items():
      renderer.country_data[country]['formatting-rules'][key] = value

    self._apply_cut_off_children(country, renderer)
    self._apply_cut_off_tokens(country, renderer)

  def _apply_cut_off_children(self, country: str, renderer: Renderer):
    """Removes cut-off-childen token.

    If a token is registered to have it's children removed, we can remove the
    formatting rules.
    """
    cut_off_children = renderer.country_data[country].get(
        'cut-off-children', set())

    for cut_off in cut_off_children:
      del renderer.country_data[country]['formatting-rules'][cut_off]

  def _apply_cut_off_tokens(self, country: str, renderer: Renderer):
    """Removes cut-off-tokens.

    If a token is registered to be removed from the model, we can removed it
    plus preceding separator/prefix and succeding suffix from the formatting
    rules.
    """

    def index_of_first(lst, pred):
      for i, v in enumerate(lst):
        if pred(v):
          return i
      return None

    cut_off_tokens = renderer.country_data[country].get('cut-off-tokens', set())
    for _, input in renderer.country_data[country]['formatting-rules'].items():
      for cut_off in cut_off_tokens:
        index = index_of_first(input, lambda x: x.get('token') == cut_off)
        if index is None:
          continue
        delete_from = index
        delete_to = index
        while delete_from > 0 and (input[delete_from - 1].get('prefix')
                                   or input[delete_from - 1].get('separator')):
          delete_from -= 1
        while delete_to < len(input) - 1 and input[delete_to + 1].get('suffix'):
          delete_to += 1
        input[delete_from:delete_to + 1] = []

  def is_descendant_of(self, descendant_id: str, ancestor_id: str,
                       model: Model):
    """Returns if descendant_id is a descendant of ancestor_id.

    If descendant_id == ancestor_id, that's considered a 'yes'.
    """
    ancestor = model.find_token(ancestor_id)
    return descendant_id in [t.id for t in ancestor.pre_order()]

  def token_id_or_all_children_in_input_tokens(self, token_id: str,
                                               input_token_id: List[str],
                                               model: Model):
    """Returns if token_id is in input_token_id or all children of token_id are.

    input_token_id is a list of token_ids of a formatting expression. This
    function verifies that no token is forgotten in the formatting.
    """
    if token_id in input_token_id:
      return True

    token = model.find_token(token_id)

    if token and not token.is_atomic_token() and token.children:
      for child in token.children:
        if not self.token_id_or_all_children_in_input_tokens(
            child, input_token_id, model):
          return False
      return True

    return False

  def validate(self, token_id: str, inputs: List[dict],
               model: Model) -> List[str]:
    """Returns a list of errors to be shown when validating the formatting rule."""

    # Ignore tokens that don't exist in the model.
    token = model.find_token(token_id)
    if not token:
      return []

    if token.is_atomic_token() and inputs:
      return ["You cannot provide rules for atomic tokens"]

    # Children of the token in the model.
    children_of_token = set(token.children)
    # Tokens that are used during formatting or explicitly skipped.
    input_tokens = set([t['token'] for t in inputs if 'token' in t])
    input_tokens = input_tokens.union(
        set([t['skip'] for t in inputs if 'skip' in t]))

    errors = []
    for t in input_tokens - children_of_token:
      # If an input token is not a direct child, it needs to be a desendant.
      if not self.is_descendant_of(t, token_id, model):
        errors.append(
            f"'{t}' exists in the rule but is not a descendant of '{token_id}' in the model."
        )

    for t in children_of_token - input_tokens:
      # If a child is missing all children of that child need to be in the
      # formatting rule.
      if not self.token_id_or_all_children_in_input_tokens(
          t, input_tokens, model):
        errors.append(
            f"'{t}' is a child of {token_id} but does not get produced.")

    return errors

  def collect_details_for_formatting(self, country: str, token_id: str,
                                     renderer: Renderer) -> Optional[dict]:
    model = renderer.country_data[country]["model"]

    token = model.find_token(token_id)
    if not token or token.is_atomic_token():
      return None

    named_formatting_rules = (renderer.country_data[country].get(
        'named-formatting-rules', {}))
    formatting_rules = (renderer.country_data[country].get(
        'formatting-rules', {}))

    # We think of a formatting rule as `output = function(inputs)`, so the
    # inputs below are the tokens that feed into the formatted output.
    FLAG_MISSING_RULES = False
    if FLAG_MISSING_RULES:
      inputs = formatting_rules.get(token_id, [])
    else:
      inputs = formatting_rules.get(token_id, None)
      if not inputs:
        return None

    errors = []

    # A special case is references to named formatting rules. Only one reference
    # may exist per rule.
    while len(inputs) == 1 and 'reference' in inputs[0]:
      rule = named_formatting_rules.get(inputs[0]['reference'], None)
      if rule:
        inputs = rule.get(token_id, None)
      else:
        errors += [f"No named-rule {inputs[0]['reference']} found"]
        inputs = []

    for input in inputs:
      if 'reference' in input:
        errors += [f"A rule for {token_id} had more than one reference"]
        inputs = []
        break

    if not errors:
      errors += self.validate(token_id, inputs, model)
    if errors:
      print(f"Formatting errors for {token_id}: {errors}")
      print(model.find_token(token_id))

    return {
        "model": model,
        "token_id": token_id,
        "inputs": inputs,
        "errors": errors,
        "named_formatting_rules": named_formatting_rules,
        "formatting_rules": formatting_rules
    }

  def render_token_details(self, country: str, token_id: str,
                           renderer: Renderer) -> Optional[str]:
    env = Environment(extensions=['jinja2.ext.do'],
                      loader=FileSystemLoader(
                          os.path.join(os.path.dirname(__file__))),
                      autoescape=select_autoescape())
    template = env.get_template("formatting_template.html")
    kwargs = self.collect_details_for_formatting(country, token_id, renderer)
    if kwargs:
      return template.render(**kwargs)
    return None
