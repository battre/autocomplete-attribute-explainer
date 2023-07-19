from renderer import Renderer
from modules.abstract_module import AbstractModule
from pathlib import Path
from typing import Any, Optional, Dict, Union
from schema import Schema
import schema
import re2 as re
from renderer import Renderer
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os
import pprint
import copy
from .parsing import (RegexFragment, RegexReference, RegexConcat, ParsingEngine,
                      RegexComponent, CaptureOptions, CaptureReference,
                      CaptureComponent, CaptureTypeWithPattern,
                      CaptureTypeWithPatternCascade)


class ParsingModule(AbstractModule):

  def schema(self):
    # Definitions for regular expressions.
    regex_fragment = {'regex_fragment': str}
    regex_reference = {'regex_reference': str}
    regex_concat = {
        'regex_concat': {
            schema.Optional('options'): {
                schema.Optional('wrap_non_capture'): bool
            }
        }
    }
    regex_concat['regex_concat']['parts'] = [
        schema.Or(regex_fragment, regex_reference, regex_concat)
    ]

    regex_component = schema.Or(regex_fragment, regex_reference, regex_concat)

    # Definitions for capture components
    capture_options = {
        schema.Optional('quantifier'):
        schema.Or('MATCH_REQUIRED', 'MATCH_OPTIONAL', 'MATCH_LAZY_OPTIONAL'),
        schema.Optional('separator'):
        regex_component
    }

    capture_reference = {'capture_reference': str}

    no_capture_pattern = {
        'no_capture_pattern': {
            # 'parts' are added below due to recursion
            schema.Optional('options'):
            capture_options
        }
    }

    capture_type_with_pattern = {
        'capture_type_with_pattern': {
            'output':
            str,  # type name, e.g. 'given-name'
            # 'parts' are added below due to recursion
            schema.Optional('options'):
            capture_options,
        }
    }
    capture_type_with_pattern['capture_type_with_pattern']['parts'] = [
        schema.Or(regex_fragment, regex_reference, regex_concat,
                  capture_reference, no_capture_pattern,
                  capture_type_with_pattern)
    ]

    no_capture_pattern['no_capture_pattern']['parts'] = [
        schema.Or(regex_fragment, regex_reference, regex_concat,
                  capture_reference, no_capture_pattern,
                  capture_type_with_pattern)
    ]

    capture_type_with_pattern_cascade = {
        'capture_type_with_pattern_cascade': {
            'output':
            str,  # type name, e.g. 'given-name'
            # Only evaluate the patters if the condition matches.
            schema.Optional('condition'):
            regex_component,
            # 'patters' are added below due to recursion
        }
    }
    capture_type_with_pattern_cascade['capture_type_with_pattern_cascade'][
        'patterns'] = [
            # Reference needs to point to a capture_type_with_pattern
            schema.Or(capture_reference, capture_type_with_pattern,
                      capture_type_with_pattern_cascade)
        ]

    test_regex_constants = {
        'id': str,
        'regex_constant': str,
        'input': str,
        'match_groups': [str],
    }

    test_capture_pattern_constants = {
        'id': str,
        'capture_pattern_constant': str,
        'input': str,
        'output': {
            schema.Optional(str): str
        }
    }

    test_capture_patterns = {
        'id': str,
        'type': str,
        'input': str,
        'output': {
            str: str
        },
    }

    return Schema({
        schema.Optional("regex_constants"): {
            # Constant name -> regular expression
            str: regex_component
        },
        schema.Optional("capture_pattern_constants"): {
            # Constant name -> capture pattern expression
            str:
            schema.Or(capture_reference, no_capture_pattern,
                      capture_type_with_pattern)
        },
        schema.Optional("capture_patterns"): {
            # field type -> pattern to use
            str:
            schema.Or(capture_reference, capture_type_with_pattern,
                      capture_type_with_pattern_cascade)
        },
        schema.Optional("test_regex_constants"): [test_regex_constants],
        schema.Optional("test_capture_pattern_constants"):
        [test_capture_pattern_constants],
        schema.Optional("test_capture_patterns"): [test_capture_patterns],
    })

  def parse_regex_component(self, definition: Dict) -> RegexComponent:
    if 'regex_fragment' in definition:
      fragment_string = definition['regex_fragment']
      # Strip all new lines and trailing whitespaces
      fragment_string = "".join(re.split(r'\s*\n', fragment_string))
      fragment_string = fragment_string.rstrip()
      return RegexFragment(fragment_string)

    if 'regex_reference' in definition:
      return RegexReference(definition['regex_reference'])

    if 'regex_concat' in definition:
      wrap_non_capture = definition['regex_concat'].get('options', {}).get(
          'wrap_non_capture', True)
      parts = [
          self.parse_regex_component(p)
          for p in definition['regex_concat'].get('parts', [])
      ]
      return RegexConcat(parts, wrap_non_capture)

    assert False, f"Invalid component definition {definition}"

  def import_regex_constants(self, yaml, engine: ParsingEngine):
    for key, definition in yaml.get('regex_constants', {}).items():
      engine.regexes[key] = self.parse_regex_component(definition)

  def parse_capture_options(self, yaml) -> CaptureOptions:
    kwargs = {}
    if 'quantifier' in yaml:
      quantifier = yaml['quantifier']
      assert quantifier in ('MATCH_REQUIRED', 'MATCH_OPTIONAL',
                            'MATCH_LAZY_OPTIONAL')
      kwargs['quantifier'] = quantifier
    if 'separator' in yaml:
      pattern = self.parse_regex_component(yaml['separator'])
      kwargs['separator'] = pattern
    return CaptureOptions(**kwargs)

  def parse_capture_pattern_constant(
      self, yaml) -> Union[CaptureComponent, RegexComponent]:
    if ('regex_fragment' in yaml or 'regex_reference' in yaml
        or 'regex_concat' in yaml):
      return self.parse_regex_component(yaml)

    if 'capture_reference' in yaml:
      return CaptureReference(yaml['capture_reference'])

    if 'no_capture_pattern' in yaml:
      yaml = yaml['no_capture_pattern']
      parts = [
          self.parse_capture_pattern_constant(part) for part in yaml['parts']
      ]
      options = self.parse_capture_options(yaml.get('options', {}))
      return CaptureTypeWithPattern(output=None, parts=parts, options=options)

    if 'capture_type_with_pattern' in yaml:
      yaml = yaml['capture_type_with_pattern']
      output = yaml['output']
      parts = [
          self.parse_capture_pattern_constant(part) for part in yaml['parts']
      ]
      options = self.parse_capture_options(yaml.get('options', {}))
      return CaptureTypeWithPattern(output=output, parts=parts, options=options)

    assert False, f"Invalid component definition {yaml}"

  def import_capture_pattern_constants(self, yaml, engine: ParsingEngine):
    for key, definition in yaml.get('capture_pattern_constants', {}).items():
      engine.capture_patterns_constants[
          key] = self.parse_capture_pattern_constant(definition)

  def parse_capture_pattern(self, yaml) -> RegexComponent:
    if 'capture_reference' in yaml:
      return CaptureReference(yaml['capture_reference'])

    if 'capture_type_with_pattern' in yaml:
      yaml = yaml['capture_type_with_pattern']
      output = yaml['output']
      options = self.parse_capture_options(yaml.get('options', {}))
      parts = [
          self.parse_capture_pattern_constant(part) for part in yaml['parts']
      ]
      return CaptureTypeWithPattern(output=output, parts=parts, options=options)

    if 'capture_type_with_pattern_cascade' in yaml:
      yaml = yaml['capture_type_with_pattern_cascade']
      output = yaml['output']
      patterns = [
          self.parse_capture_pattern(pattern) for pattern in yaml['patterns']
      ]
      condition = None
      if 'condition' in yaml:
        condition = self.parse_regex_component(yaml['condition'])
      return CaptureTypeWithPatternCascade(output=output,
                                           condition=condition,
                                           patterns=patterns)

    assert False, f"Invalid component definition {yaml}"

  def import_capture_patterns(self, yaml, engine: ParsingEngine):
    for key, definition in yaml.get('capture_patterns', {}).items():
      engine.capture_patterns[key] = self.parse_capture_pattern(definition)

  def test_regex_constants(self, yaml, engine: ParsingEngine):
    for test in yaml:
      if not test['regex_constant'] in engine.regexes:
        print(f"Failed test '{test.id}': Invalid regex_constant: " +
              test['regex_constant'])
        return
      regex = "(" + engine.regexes[test['regex_constant']].to_regex(engine) + \
          ")"
      result = re.match(regex, test['input'])
      if result:
        result = [s.__str__() for s in result.groups()]
      if test['match_groups'] != result:
        print(f"Test failed: {test}")
        print(f"{result} was actual output")
        print(f"{test['match_groups']} was expected output")
        break

  def test_capture_pattern_constants(self, yaml, engine: ParsingEngine):
    for test in yaml:
      if not test[
          'capture_pattern_constant'] in engine.capture_patterns_constants:
        print(f"Failed test '{test.id}': Invalid capture_pattern_constant: " +
              test['capture_pattern_constant'])
        return
      pattern = engine.capture_patterns_constants[
          test['capture_pattern_constant']]
      result = pattern.evaluate(test['input'], engine)
      if test['output'] != result:
        print(f"Test failed: {test}")
        print(f"{result} was actual output")
        print(f"{test['output']} was expected output")
        break

  def test_capture_patterns(self, yaml, engine: ParsingEngine):
    for test in yaml:
      token_type = test['type']
      pattern = engine.capture_patterns[token_type]
      result = pattern.evaluate(test['input'], engine)
      result = {k: v for k, v in result.items() if v}
      expected = {k: v for k, v in test['output'].items() if v != ""}
      expected[token_type] = test['input']
      if expected != result:
        print(f"Test failed: {test}")
        print(f"{pprint.saferepr(result)} was actual output")
        print(f"{pprint.saferepr(expected)} was expected output")
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
    self.import_regex_constants(yaml, engine)
    self.import_capture_pattern_constants(yaml, engine)
    self.import_capture_patterns(yaml, engine)

    all_removed_tokens = renderer.country_data[country].get(
        'all-removed-tokens', {})
    engine.prune_output_types(all_removed_tokens)

    model = renderer.get_model(country)
    if not engine.validate(model):
      return

    if 'test_regex_constants' in yaml:
      self.test_regex_constants(yaml['test_regex_constants'], engine)

    if 'test_capture_pattern_constants' in yaml:
      self.test_capture_pattern_constants(
          yaml['test_capture_pattern_constants'], engine)

    if 'test_capture_patterns' in yaml:
      self.test_capture_patterns(yaml['test_capture_patterns'], engine)

  def render_token_details(self, country: str, token_id: str,
                           renderer: Renderer) -> Optional[str]:
    env = Environment(extensions=['jinja2.ext.do'],
                      loader=FileSystemLoader(
                          os.path.join(os.path.dirname(__file__))),
                      autoescape=select_autoescape())
    if "ParsingEngine" not in renderer.country_data[country]:
      return None

    engine = renderer.country_data[country]["ParsingEngine"]
    template = env.get_template("parsing_template.html")
    return template.render(
        engine=engine,
        token_id=token_id,
        CaptureTypeWithPattern=CaptureTypeWithPattern,
        CaptureTypeWithPatternCascade=CaptureTypeWithPatternCascade)

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
