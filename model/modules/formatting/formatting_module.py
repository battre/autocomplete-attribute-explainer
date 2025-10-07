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
from .formatting_utils import collect_details_for_formatting, validate


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
        schema.Optional("formatting-rules"): formatting_rule,
        schema.Optional("examples"): [{
            "id": str,
            schema.Optional("comment"): str,
            schema.Optional("attributes"): {
                str: schema.Optional(schema.Or(str, int))
            },
            schema.Optional("inherit-from"): str,  # Reference to an "id"
            schema.Optional("output"): {
                str: {
                    "show": bool,  # Whether to produce the output in the HTML
                    "text": str  # The expected content.
                }
            },
        }]
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

    .formatting_example_textbox {
      border: 1px solid black;
      padding: 6px;
    }
    .formatting_example_overview_table td {
      vertical-align: top;
      padding: 0 10px;
    }
    .formatting_example_overview_table > tbody > tr > td {
      padding: 6px;
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

    yaml = self.read_yaml(path) or {}

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

    renderer.country_data[country]['formatting-examples'] = yaml.get(
        'examples', [])

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

  def render_token_details(self, country: str, token_id: str,
                           renderer: Renderer) -> Optional[str]:
    template = FormattingModule.get_template(__file__,
                                             "formatting_template.html")
    kwargs = collect_details_for_formatting(country, token_id, renderer)
    if kwargs:
      return template.render(**kwargs)
    return None

  def apply_formatting(self, country: str, token_id: str, data: dict,
                       renderer: Renderer, errors: List[str]) -> str:
    if token_id in data and data[token_id]:
      return str(data[token_id])

    model = renderer.get_model(country)
    if model is None:
      return ""

    token = model.find_token(token_id)
    if not token or token.is_atomic_token() or not token.children:
      return ""

    named_formatting_rules = (renderer.country_data[country].get(
        'named-formatting-rules', {}))
    formatting_rules = (renderer.country_data[country].get(
        'formatting-rules', {}))

    inputs = formatting_rules.get(token_id)
    if not inputs:
      errors.append(f"Could not find a rule for {token_id}")
      return ""

    while len(inputs) == 1 and 'reference' in inputs[0]:
      rule = named_formatting_rules.get(inputs[0]['reference'], None)
      if rule:
        inputs = rule.get(token_id, None)
      else:
        errors.append(f"No named-rule {inputs[0]['reference']} found")
        inputs = []

    result = ""
    for i in range(len(inputs)):
      input = inputs[i]
      if 'token' in input:
        separator = ' '
        prefix = ''
        suffix = ''
        # Detect separator, prefix and suffix specifications
        j = i - 1
        while j >= 0 and ('separator' in inputs[j] or 'prefix' in inputs[j]):
          if 'separator' in inputs[j]:
            separator = inputs[j]['separator']
          if 'prefix' in inputs[j]:
            prefix = inputs[j]['prefix']
          j -= 1
        j = i + 1
        value = self.apply_formatting(country, input['token'], data, renderer,
                                      errors)
        while j < len(inputs) and 'suffix' in inputs[j]:
          suffix = inputs[j]['suffix']
          j += 1
        # The separator is not rendered at the beginning of a line.
        if len(result) == 0 or result[-1] == '\n':
          separator = ''
        if value:
          result += separator + prefix + value + suffix
      elif 'separator' in input or 'prefix' in input or 'suffix' in input:
        # These will be handled by the token if the token exists
        pass
      elif 'reference' in input:
        errors.append(f"Unexpected reference in {token_id}")
        pass
      elif 'skip' in input:
        pass
    return result

  def collect_details_for_example_addresses(self, country: str,
                                            renderer: Renderer) -> dict:
    examples = renderer.country_data[country].get('formatting-examples')
    if not examples:
      return {}

    collected_details = []
    for example in examples:
      data = example['attributes']
      output = example['output']
      results = []
      for output_token, expectation in output.items():
        errors = []
        actual_output = self.apply_formatting(country, output_token, data,
                                              renderer, errors)
        if expectation and (expectation['show']
                            or expectation['text'] != actual_output):
          delta = '\n'.join(
              difflib.unified_diff(expectation['text'].splitlines(),
                                   actual_output.splitlines(),
                                   fromfile='expected_output',
                                   tofile='actual_output',
                                   lineterm=''))
          results.append({
              'errors': errors,
              'output_token': output_token,
              'output': actual_output,
              'expected_output': expectation['text'],
              'delta': delta,
          })

      collected_details.append({
          'id': example['id'],
          'comment': example.get('comment'),
          'data': data,
          'results': results
      })
    return {
        'examples': collected_details,
        'model': renderer.country_data[country].get('model')
    }

  def render_after_token_index(self, country: str,
                               renderer: Renderer) -> Optional[str]:
    template = FormattingModule.get_template(
        __file__, "example_formatting_template.html")
    kwargs = self.collect_details_for_example_addresses(country, renderer)
    if kwargs:
      return template.render(**kwargs)
    return None
