from renderer import Renderer
from modules.abstract_module import AbstractModule
from pathlib import Path
from typing import Any, Optional, Dict, Union, cast
from schema import Schema
import schema
import re2 as re
from renderer import Renderer
import pprint
import copy
from .parsing import (RegexFragment, RegexReference, RegexConcat, ParsingEngine,
                      RegexComponent, CaptureReference, CaptureComponent,
                      CaptureMapper, REGEX_COMPONENT_SCHEMA,
                      CAPTURE_COMPONENT_SCHEMA, PARSING_COMPONENT_SCHEMA,
                      DecompositionCascade, Decomposition,
                      parse_regex_component_from_yaml_dict,
                      parse_capture_component_from_yaml_dict,
                      parse_parsing_component_from_yaml_dict)


class ParsingModule(AbstractModule):

  def schema(self):
    return Schema({
        schema.Optional("regex_definitions"): {
            # Constant definition name -> regular expression
            str: REGEX_COMPONENT_SCHEMA
        },
        schema.Optional("capture_definitions"): {
            # Constant name -> capture pattern expression
            str: CAPTURE_COMPONENT_SCHEMA
        },
        schema.Optional("parsing_definitions"): {
            # field type -> pattern to use
            str: PARSING_COMPONENT_SCHEMA
        },
        schema.Optional("test_regex_definitions"): [{
            'id': str,
            'regex_name': str,
            'input': str,
            'match_groups': [str],
        }],
        schema.Optional("test_capture_definitions"): [{
            'id': str,
            'capture_name': str,
            'input': str,
            'output': {
                schema.Optional(str): str
            }
        }],
        schema.Optional("test_parsing_definitions"): [{
            'id': str,
            'type': str,
            'input': str,
            'output': {
                str: str
            },
        }],
    })

  def import_regex_definitions(self, yaml, engine: ParsingEngine):
    for key, definition in yaml.get('regex_definitions', {}).items():
      engine.regex_definitions[key] = \
        parse_regex_component_from_yaml_dict(definition)

  def import_capture_definitions(self, yaml, engine: ParsingEngine):
    for key, definition in yaml.get('capture_definitions', {}).items():
      engine.capture_definitions[key] = \
        parse_capture_component_from_yaml_dict(definition)

  def import_parsing_definitions(self, yaml, engine: ParsingEngine):
    for key, definition in yaml.get('parsing_definitions', {}).items():
      engine.parsing_definitions[key] = \
        parse_parsing_component_from_yaml_dict(definition)

  def test_regex_definitions(self, yaml, engine: ParsingEngine):
    for test in yaml:
      if not test['regex_name'] in engine.regex_definitions:
        print(f"Failed test '{test.id}': Invalid regex_definition: " +
              test['regex_name'])
        return
      regex_definition = engine.regex_definitions[test['regex_name']]
      assert regex_definition
      regex = regex_definition.to_regex(engine, CaptureMapper())
      regex = f"((?i:{regex}))"
      result = re.search(regex, test['input'])
      if result:
        result = [s.__str__() for s in result.groups()]
      if test['match_groups'] != result:
        print(f"Test failed: {test}")
        print(f"{result} was actual output")
        print(f"{test['match_groups']} was expected output")
        print(f"Regex used: {regex}")
        break

  def test_capture_definitions(self, yaml, engine: ParsingEngine):
    for test in yaml:
      if not test['capture_name'] in engine.capture_definitions:
        print(f"Failed test '{test.id}': Invalid capture_definition: " +
              test['capture_name'])
        return
      pattern = engine.capture_definitions[test['capture_name']]
      assert pattern
      result, regex_used = pattern.evaluate(test['input'], engine,
                                            CaptureMapper())
      if test['output'] != result:
        print(f"Test failed: {test}")
        print(f"{result} was actual output")
        print(f"{test['output']} was expected output")
        print(f"Regex used: {regex_used}")
        break

  def test_parsing_definitions(self, yaml, engine: ParsingEngine):
    for test in yaml:
      token_type = test['type']
      if token_type not in engine.parsing_definitions:
        print(f"Failed test '{test['id']}': Invalid parsing definitions: " +
              token_type)
        return
      pattern = engine.parsing_definitions[token_type]
      assert pattern
      result, regex_used = pattern.evaluate(test['input'], engine,
                                            CaptureMapper())
      result = {k: v for k, v in result.items() if v}
      expected = {k: v for k, v in test['output'].items() if v != ""}
      # For ExtractParts we don't caputre the actual string.
      if type(pattern) in (Decomposition, DecompositionCascade):
        expected[token_type] = test['input']
      if expected != result:
        print(f"Test failed: {test}")
        print(f"{pprint.saferepr(result)} was actual output")
        print(f"{pprint.saferepr(expected)} was expected output")
        if type(pattern) == Decomposition:
          print(f"Regex used: {regex_used}")
          print(
              "Regex considered: " +
              f"{cast(Decomposition, pattern).to_regex(engine, CaptureMapper())}"
          )
        else:
          print(f"Regex used: {regex_used}")
          print(
              f"Regex considered: " +
              f"{cast(DecompositionCascade, pattern).to_regex_list(engine, CaptureMapper())}"
          )
        break

  def observe_file(self, path: Path, renderer: Renderer):
    match = re.fullmatch(r'(?P<country>..|global)-parsing-rules\.yaml',
                         path.name)
    if not match:
      return

    country = match.groupdict()['country']
    yaml = self.read_yaml(path)
    if not yaml:
      yaml = {}

    renderer.country_data[country][self.name()] = yaml
    renderer.add_country(country)

    if country == 'global':
      renderer.country_data[country]['ParsingEngine'] = ParsingEngine()
    else:
      renderer.country_data[country]['ParsingEngine'] = copy.deepcopy(
          renderer.country_data['global']['ParsingEngine'])

    engine = renderer.country_data[country]["ParsingEngine"]
    self.import_regex_definitions(yaml, engine)
    self.import_capture_definitions(yaml, engine)
    self.import_parsing_definitions(yaml, engine)

    all_removed_tokens = renderer.country_data[country].get(
        'all-removed-tokens', {})
    engine.prune_output_types(all_removed_tokens)

    model = renderer.get_model(country)
    if not engine.validate(model):
      return

    if 'test_regex_definitions' in yaml:
      self.test_regex_definitions(yaml['test_regex_definitions'], engine)

    if 'test_capture_definitions' in yaml:
      self.test_capture_definitions(yaml['test_capture_definitions'], engine)

    if 'test_parsing_definitions' in yaml:
      self.test_parsing_definitions(yaml['test_parsing_definitions'], engine)

  def render_token_details(self, country: str, token_id: str,
                           renderer: Renderer) -> Optional[str]:
    template = ParsingModule.get_template(__file__, "parsing_template.html")

    if "ParsingEngine" not in renderer.country_data[country]:
      return None

    engine = renderer.country_data[country]["ParsingEngine"]
    return template.render(engine=engine, token_id=token_id)

  def css(self) -> str:
    return """
    <style>
    .parsing details {
        border: 1px solid #aaa;
        border-radius: 4px;
        padding: 0.5em 0.5em 0;
    }

    .parsing summary {
        font-weight: bold;
        margin: -0.5em -0.5em 0;
        padding: 0.5em;
    }

    .parsing details[open] {
        padding: 0.5em;
    }

    .parsing details[open].summary {
        border-bottom: 1px solid #aaa;
        margin-bottom: 0.5em;
    }

    .parsing-regexfragment {
        overflow-wrap: anywhere;
        font-family: 'Courier New', Courier, monospace;
        padding: 2px;
        margin: 1px;
        background-color: beige;
    }
    </style>
    """
