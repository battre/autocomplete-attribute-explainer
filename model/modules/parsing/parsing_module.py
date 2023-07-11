from renderer import Renderer
from modules.abstract_module import AbstractModule
from pathlib import Path
from typing import Any, Optional, Dict, Union
from schema import Schema
import schema
import re
from renderer import Renderer
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os
from .parsing import (RegexFragment, RegexReference, RegexConcat, ParsingEngine,
                      RegexComponent, CaptureOptions, CaptureReference,
                      CaptureComponent, CaptureTypeWithPattern,
                      CaptureTypeWithPatternCascade, NoCapturePattern)


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
            'pattern': regex_component,
            schema.Optional('options'): capture_options
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

    capture_type_with_pattern_cascade = {
        'capture_type_with_pattern_cascade': {
            'output':
            str,  # type name, e.g. 'given-name'
            'patterns': [
                # Reference needs to point to a capture_type_with_pattern
                schema.Or(capture_reference, capture_type_with_pattern)
            ]
        }
    }

    return Schema({
        schema.Optional("regex_constants"): {
            # Constant name -> regular expression
            str: regex_component
        },
        schema.Optional("capture_pattnern_constants"): {
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
        }
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
      pattern = self.parse_regex_component(yaml['pattern'])
      options = self.parse_capture_options(yaml.get('options', {}))
      return NoCapturePattern(pattern=pattern, options=options)

    if 'capture_type_with_pattern' in yaml:
      yaml = yaml['capture_type_with_pattern']
      output = yaml['output']
      options = self.parse_capture_options(yaml.get('options', {}))
      parts = [
          self.parse_capture_pattern_constant(part) for part in yaml['parts']
      ]
      return CaptureTypeWithPattern(output=output, parts=parts, options=options)

    assert False, f"Invalid component definition {yaml}"

  def import_capture_pattern_constants(self, yaml, engine: ParsingEngine):
    for key, definition in yaml.get('capture_pattnern_constants', {}).items():
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
          self.parse_capture_pattern_constant(pattern)
          for pattern in yaml['patterns']
      ]
      return CaptureTypeWithPatternCascade(output=output, patterns=patterns)

    assert False, f"Invalid component definition {yaml}"

  def import_capture_patterns(self, yaml, engine: ParsingEngine):
    for key, definition in yaml.get('capture_patterns', {}).items():
      engine.capture_patterns[key] = self.parse_capture_pattern(definition)

  def observe_file(self, path: Path, renderer: Renderer):
    match = re.fullmatch(r'(?P<country>..|global)-parsing-rules\.yaml',
                         path.name)
    if not match:
      return

    country = match.groupdict()['country']
    yaml = self.read_yaml(path)

    renderer.country_data[country][self.name()] = yaml
    renderer.add_country(country)

    renderer.country_data[country]["ParsingEngine"] = ParsingEngine()

    engine = renderer.country_data[country]["ParsingEngine"]
    self.import_regex_constants(yaml, engine)
    self.import_capture_pattern_constants(yaml, engine)
    self.import_capture_patterns(yaml, engine)

    model = renderer.get_model(country)
    engine.validate(model)

  # def render_preamble(self, country: str, renderer: Renderer) -> Optional[str]:
  #   env = Environment(extensions=['jinja2.ext.do'],
  #                     loader=FileSystemLoader(
  #                         os.path.join(os.path.dirname(__file__))),
  #                     autoescape=select_autoescape())
  #   template = env.get_template("template.html")
  #   return template.render(yaml=renderer.country_data[country][self.name()])
