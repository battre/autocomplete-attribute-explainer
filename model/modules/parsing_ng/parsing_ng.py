import re2
from dataclasses import dataclass, field
from typing import Dict, List, Union, Optional, cast
import schema
from enum import auto, Enum
from modules.model.model import Model

#### The following are low-level tools to create simple regular expressions.
"""A part of a compound regex."""
RegexComponent = Union["RegexFragment", "RegexReference", "RegexConcat"]
# Elements RegexFragment, RegexReference and RegexConcat are added below.
REGEX_COMPONENT_SCHEMA = schema.Or()


def parse_regex_component_from_yaml_dict(yaml) -> Optional[RegexComponent]:
  return (RegexFragment.from_yaml_dict(yaml)
          or RegexReference.from_yaml_dict(yaml)
          or RegexConcat.from_yaml_dict(yaml))


@dataclass
class RegexFragment:
  """A full regular expression or a substring of a regular expression.

  This can exist for example in the context of named regular expression or
  can be a component of a larger regex (see below).

  ```
  regex_fragment: {regex_fragment}
  ```

  where regex_fragment could be '(?:[^\s,]+)'.

  The ParsingEngine is responsible for storing the mapping of regex consant
  names to the RegexFragments.

  Use raw strings if you don't need ` #` or `: ` in your regex:
  ```
  regex_fragment: single line where you can use \. without escaping the \.
  ```
  or
  ```
  regex_fragment:
    single line where you can use \. without escaping the backslash.
  ```

  For multi-lines, use the following yaml syntax if you don't need '#' or ':'
  in your regex.
  ```
  regex_fragment: |-
    this is my very very ver
    y long string
  ```
  This will generate "this is my very very long string" due the internal
  post-processing of multi-line regex strings (note the concatenation
  of "ver" and "y").

  For other cases, you can fall back to quotes:
  ```
  regex_fragment:
    "This is a \"very\"\
    long line with\\nescaped characters,\
    which does not need escaping for ' #' and ': ' though."
  ```

  https://stackoverflow.com/questions/3790454/how-do-i-break-a-string-in-yaml-over-multiple-lines
  and
  https://yaml-multiline.info/
  are good references.
  """
  value: str

  @classmethod
  def from_yaml_dict(cls, yaml) -> Optional["RegexFragment"]:
    if 'regex_fragment' not in yaml:
      return None
    fragment_string = yaml['regex_fragment']
    # Strip all new lines and trailing whitespaces
    fragment_string = "".join(re2.split(r'\s*\n', fragment_string))
    fragment_string = fragment_string.rstrip()
    return RegexFragment(fragment_string)

  @classmethod
  def schema(cls):
    return {'regex_fragment': str}

  def resolve(self, engine: "ParsingEngine") -> "RegexComponent":
    return self

  def to_regex(self, engine: "ParsingEngine", temp_output_mapping: Dict) -> str:
    return self.value

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    try:
      re2.compile(self.to_regex(engine, {}))
    except Exception as e:
      errors.append(e.__str__())


@dataclass
class RegexReference:
  """Lookup of regular expression by name.

  Name/Value pairs are stored in the ParsingEngine.

  ```
  regex_reference: {other_constant_name}
  ```
  """
  name: str

  @classmethod
  def from_yaml_dict(cls, yaml) -> Optional["RegexReference"]:
    if 'regex_reference' not in yaml:
      return None
    yaml = yaml['regex_reference']
    return RegexReference(yaml)

  @classmethod
  def schema(cls):
    return {'regex_reference': str}

  def to_regex(self, engine: "ParsingEngine", temp_output_mapping: Dict) -> str:
    return self.resolve(engine).to_regex(engine, temp_output_mapping)

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    if self.name not in engine.regex_definitions:
      errors.append(f"Undefined reference {self.name}")
      return
    engine.regex_definitions[self.name].validate(engine, model, errors)

  def resolve(self, engine: "ParsingEngine") -> "RegexComponent":
    what = self
    while type(what) == RegexReference:
      what = engine.regex_definitions[what.name]
    return what


@dataclass
class RegexConcat:
  """Concatenates a series of regular expressions in a non-capture group.

  ```
    regex_concat:
      parts:
      - regex_fragment: {regex_fragment}
      - regex_reference: {constant_name}
      # even a regex_concat could appear here if that's useful
      options:
        wrap_non_capture: false  # defaults to true.
  ```
  """
  parts: List[RegexComponent]
  wrap_non_capture: bool = True

  @classmethod
  def from_yaml_dict(cls, yaml) -> Optional["RegexConcat"]:
    if 'regex_concat' not in yaml:
      return None
    yaml = yaml['regex_concat']
    parts = [
        parse_regex_component_from_yaml_dict(part) for part in yaml['parts']
    ]
    wrap_non_capture = yaml.get('wrap_non_capture', True)
    return RegexConcat(parts=parts, wrap_non_capture=wrap_non_capture)

  @classmethod
  def schema(cls):
    regex_concat_schema = {
        'regex_concat': {
            schema.Optional('wrap_non_capture'): bool  # defaults to true
            # The following is added below due to recursion
            # 'parts': schema.Or(RegexFragment.schema(), RegexReference.schema(),
            #                    RegexConcat.schema())
        }
    }
    regex_concat_schema['regex_concat']['parts'] = [
        schema.Or(RegexFragment.schema(), RegexReference.schema(),
                  regex_concat_schema)
    ]
    return regex_concat_schema

  def resolve(self, engine: "ParsingEngine") -> "RegexComponent":
    return self

  def to_regex(self, engine: "ParsingEngine", temp_output_mapping: Dict) -> str:
    # The components and the final string are wrapped in non-capture groups
    # to reduce the risk of side-effects between the components. Imagine
    # the RegexFragments A = "a|b" and B="c". Concatenating them as "a|bc" would
    # probably be unexpected.
    result = "".join(
        [p.to_regex(engine, temp_output_mapping) for p in self.parts])
    if self.wrap_non_capture:
      return "(?:" + result + ")"
    return result

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    try:
      re2.compile(self.to_regex(engine, {}))
    except Exception as e:
      errors.append(e.__str__())


REGEX_COMPONENT_SCHEMA._args = [
    RegexFragment.schema(),
    RegexReference.schema(),
    RegexConcat.schema()
]

#### Captures components: higher-level, more powerful regex

CaptureComponent = Union["Capture", "CaptureReference", "Separator"]
# Elements capture_reference, capture, no_capture and separator are added below.
CAPTURE_COMPONENT_SCHEMA = schema.Or()


def parse_capture_component_from_yaml_dict(yaml) -> Optional[CaptureComponent]:
  return (CaptureReference.from_yaml_dict(yaml) or Capture.from_yaml_dict(yaml)
          or Separator.from_yaml_dict(yaml))


CaptureOrRegexComponent = Union[RegexComponent, CaptureComponent]
_capture_or_regex_component = schema.Or(REGEX_COMPONENT_SCHEMA,
                                        CAPTURE_COMPONENT_SCHEMA)


def _parse_capture_or_regex_component(
    yaml) -> Optional[CaptureOrRegexComponent]:
  return parse_regex_component_from_yaml_dict(yaml) or \
      parse_capture_component_from_yaml_dict(yaml)


@dataclass
class CaptureReference:
  name: str

  @classmethod
  def from_yaml_dict(cls, yaml) -> Optional["CaptureReference"]:
    if 'capture_reference' not in yaml:
      return None
    yaml = yaml['capture_reference']
    return CaptureReference(yaml)

  @classmethod
  def schema(cls):
    return {'capture_reference': str}

  def to_regex(self, engine: "ParsingEngine", temp_output_mapping: Dict) -> str:
    return self.resolve(engine).to_regex(engine, temp_output_mapping)

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    if (self.name not in engine.regex_definitions
        and self.name not in engine.capture_definitions):
      errors.append(f"Undefined reference {self.name}")

  def resolve(self, engine: "ParsingEngine") -> CaptureOrRegexComponent:
    what = self
    while type(what) in (RegexReference, CaptureReference):
      if type(what) == RegexReference:
        what = cast(RegexReference, what).resolve(engine)
      elif type(what) == CaptureReference:
        what = engine.capture_definitions[cast(CaptureReference, what).name]
    return what

  def evaluate(self, data: str, engine: "ParsingEngine",
               temp_output_mapping: Dict) -> Dict:
    resolved = self.resolve(engine)
    if type(resolved) == Capture:
      return cast(Capture, resolved).evaluate(data, engine, temp_output_mapping)
    return {}


class MatchQuantifier(Enum):
  # The capture group is required.
  MATCH_REQUIRED = auto()
  # The capture group is optional.
  MATCH_OPTIONAL = auto()
  # The capture group is lazy optional meaning that it is avoided if an overall
  # match is possible.
  MATCH_LAZY_OPTIONAL = auto()

  @classmethod
  def from_yaml_dict(cls, yaml) -> Optional["MatchQuantifier"]:
    if not yaml:
      return None
    if yaml == "MATCH_REQUIRED":
      return MatchQuantifier.MATCH_REQUIRED
    elif yaml == "MATCH_OPTIONAL":
      return MatchQuantifier.MATCH_OPTIONAL
    elif yaml == "MATCH_LAZY_OPTIONAL":
      return MatchQuantifier.MATCH_LAZY_OPTIONAL
    else:
      raise ValueError(f"Invalid quantifier: {yaml}")

  @classmethod
  def schema(cls):
    return schema.Or('MATCH_REQUIRED', 'MATCH_OPTIONAL', 'MATCH_LAZY_OPTIONAL')

  def to_regex_suffix(self) -> str:
    if (self == MatchQuantifier.MATCH_REQUIRED):
      return ""
    elif (self == MatchQuantifier.MATCH_OPTIONAL):
      return "?"
    elif (self == MatchQuantifier.MATCH_LAZY_OPTIONAL):
      return "??"
    else:
      raise ValueError(f"Invalid quantifier: {self}")

  def __str__(self) -> str:
    if self == MatchQuantifier.MATCH_REQUIRED:
      return "MATCH_REQUIRED"
    elif self == MatchQuantifier.MATCH_OPTIONAL:
      return "MATCH_OPTIONAL"
    elif self == MatchQuantifier.MATCH_LAZY_OPTIONAL:
      return "MATCH_LAZY_OPTIONAL"
    else:
      raise ValueError(f"Invalid quantifier: {self}")


@dataclass
class Separator:
  # A separator that must be matched after a capture group.
  # By default, a group must be either followed by a space-like character (\s)
  # or it must be the last group in the line. The separator is allowed to be
  # empty.
  value: RegexComponent

  @classmethod
  def from_yaml_dict(cls, yaml) -> Optional["Separator"]:
    if 'separator' not in yaml:
      return None
    yaml = yaml['separator']
    value = parse_regex_component_from_yaml_dict(yaml)
    assert (value)
    return Separator(value)

  @classmethod
  def schema(cls):
    global REGEX_COMPONENT_SCHEMA
    return {'separator': REGEX_COMPONENT_SCHEMA}

  def resolve(self, engine: "ParsingEngine") -> CaptureOrRegexComponent:
    return self

  def to_regex(self, engine: "ParsingEngine", temp_output_mapping: Dict) -> str:
    return "(?:" + self.value.to_regex(engine, {}) + ")"

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    self.value.validate(engine, model, errors)

  def evaluate(self, data: str, engine: "ParsingEngine") -> Dict:
    return {}


@dataclass
class Capture:
  """A capturing regex pattern

  If the "output" is specified, the regex contains a capture group for the
  specified name. Otherwise, this describes a "no_capture_pattern".

  Sometimes we want to apply multiple alternative Captures. Eg to match
  'andar \d+' and '\d andar' we would like to have two different regular
  expressions, each with a capture group (?P<floor>), but capture groups
  need to be named uniquely. temp_output enables seeting such a unique
  identifier and is followed by a rename operation.
  """
  output: Optional[str]  # Field-type e.g. given-name
  temp_output: Optional[str]
  prefix: Optional[Union[RegexFragment, RegexReference, RegexConcat]]
  suffix: Optional[Union[RegexFragment, RegexReference, RegexConcat]]
  parts: List[Union[CaptureReference, "Capture", RegexFragment, RegexReference,
                    RegexConcat]]
  quantifier: MatchQuantifier

  @classmethod
  def from_yaml_dict(cls, yaml) -> Optional["Capture"]:
    output = None
    temp_output = None
    prefix = None
    suffix = None
    if 'capture' in yaml:
      yaml = yaml['capture']
      output = yaml['output']
      if 'temp_output' in yaml:
        temp_output = yaml['temp_output']
      prefix = parse_regex_component_from_yaml_dict(yaml.get('prefix', {}))
      suffix = parse_regex_component_from_yaml_dict(yaml.get('suffix', {}))
    elif 'no_capture' in yaml:
      yaml = yaml['no_capture']
    else:
      return None
    parts = [_parse_capture_or_regex_component(part) for part in yaml['parts']]
    quantifier = (MatchQuantifier.from_yaml_dict(yaml.get('quantifier'))
                  or MatchQuantifier.MATCH_REQUIRED)

    return Capture(output=output,
                   temp_output=temp_output,
                   prefix=prefix,
                   parts=parts,
                   suffix=suffix,
                   quantifier=quantifier)

  @classmethod
  def schema_capture(cls):
    global REGEX_COMPONENT_SCHEMA, CAPTURE_COMPONENT_SCHEMA
    return {
        'capture': {
            'output': str,
            schema.Optional('temp_output'): str,
            schema.Optional('prefix'): REGEX_COMPONENT_SCHEMA,
            'parts': [_capture_or_regex_component],
            schema.Optional('suffix'): REGEX_COMPONENT_SCHEMA,
            schema.Optional('quantifier'): MatchQuantifier.schema()
        }
    }

  @classmethod
  def schema_no_capture(cls):
    global CAPTURE_COMPONENT_SCHEMA
    return {
        'no_capture': {
            'parts': [_capture_or_regex_component],
            schema.Optional('quantifier'): MatchQuantifier.schema()
        }
    }

  def resolve(self, engine: "ParsingEngine") -> CaptureOrRegexComponent:
    return self

  def to_regex(self, preceding_separator: Optional[RegexComponent],
               engine: "ParsingEngine", temp_output_mapping: Dict) -> str:
    separator = (preceding_separator.to_regex(engine, {})
                 if preceding_separator else "")
    prefix = (self.prefix.to_regex(engine, {}) if self.prefix else "")
    suffix = (self.suffix.to_regex(engine, {}) if self.suffix else "")

    pattern_regex = ""
    i = 0
    while i < len(self.parts):
      part_i = self.parts[i].resolve(engine)
      if (type(part_i) == Separator and i + 1 < len(self.parts)
          and type(self.parts[i + 1].resolve(engine)) == Capture):
        next_capture = self.parts[i + 1].resolve(engine)
        pattern_regex += next_capture.to_regex(part_i, engine,
                                               temp_output_mapping)
        i += 1
      elif type(part_i) == Capture:
        pattern_regex += part_i.to_regex(None, engine, temp_output_mapping)
      else:
        pattern_regex += part_i.to_regex(engine, temp_output_mapping)
      i += 1

    quantifier = MatchQuantifier.to_regex_suffix(self.quantifier)
    if self.output:
      # RE2 does not allow '-' in capture groups, so we replace it with an
      # underscore and do the inverse in evaluate().
      output = self.output.replace('-', '_')
      if self.temp_output:
        normalized_temp_output = self.temp_output.replace('-', '_')
        temp_output_mapping[normalized_temp_output] = output
        output = normalized_temp_output
      return f"(?i:{separator}{prefix}(?P<{output}>{pattern_regex})" + \
            f"{suffix}){quantifier}"
    else:
      return f"(?i:{separator}{prefix}{pattern_regex}{suffix}){quantifier}"

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    if self.output and self.output not in model.concepts:
      errors.append(f"Undefined output type '{self.output}'")
    if self.prefix:
      self.prefix.validate(engine, model, errors)
    if self.suffix:
      self.suffix.validate(engine, model, errors)
    for part in self.parts:
      part.validate(engine, model, errors)

  def evaluate(self, data: str, engine: "ParsingEngine",
               temp_output_mapping: Dict) -> Dict:
    """Evaluates the `CaptureTypeWithPattern` on `data`."""
    regex = self.to_regex(None, engine, temp_output_mapping)
    result = {}
    if regex_result := re2.search(regex, data):
      for k, v in regex_result.groupdict().items():
        if k in temp_output_mapping:
          k = temp_output_mapping[k]
        k = k.replace('_', '-')
        result[k] = v
    return result


CAPTURE_COMPONENT_SCHEMA._args = [
    CaptureReference.schema(),
    Capture.schema_capture(),
    Capture.schema_no_capture(),
    Separator.schema()
]

#### ParsingComponents components: What is ultimately executed on the fields for
#### parsing.

ParsingComponent = Union["Decomposition", "DecompositionCascade", "ExtractPart",
                         "ExtractParts"]


@dataclass
class Decomposition:
  capture: Union[Capture, CaptureReference]
  anchor_beginning: bool = True
  anchor_end: bool = True

  @classmethod
  def from_yaml_dict(cls, yaml) -> Optional["Decomposition"]:
    if 'decomposition' not in yaml:
      return None
    yaml = yaml['decomposition']
    if 'capture' in yaml:
      capture = Capture.from_yaml_dict(yaml)
    elif 'capture_reference' in yaml:
      capture = CaptureReference.from_yaml_dict(yaml)
    else:
      raise ValueError(f'Found neither capture nor capture_reference in {yaml}')
    anchor_beginning = yaml.get('anchor_beginning', True)
    anchor_end = yaml.get('anchor_end', True)

    return Decomposition(capture=capture,
                         anchor_beginning=anchor_beginning,
                         anchor_end=anchor_end)

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    self.capture.validate(engine, model, errors)

  @classmethod
  def schema(cls):
    return {
        'decomposition': {
            schema.Optional('capture'): Capture.schema_capture()['capture'],
            schema.Optional('capture_reference'): \
                CaptureReference.schema()['capture_reference'],
            schema.Optional('anchor_beginning'): bool,
            schema.Optional('anchor_end'): bool,
        }
    }

  def to_regex(self, engine: "ParsingEngine", temp_output_mapping: Dict) -> str:
    prefix = "^" if self.anchor_beginning else ""
    suffix = "$" if self.anchor_end else ""
    regex = self.capture.resolve(engine).to_regex(None, engine,
                                                  temp_output_mapping)
    return f"(?:{prefix}{regex}{suffix})"

  def evaluate(self, data: str, engine: "ParsingEngine",
               temp_output_mapping: Dict) -> Dict:
    """Evaluates the `Decomposition` on `data`."""
    regex = self.to_regex(engine, temp_output_mapping)
    result = {}
    if regex_result := re2.search(regex, data):
      for k, v in regex_result.groupdict().items():
        if k in temp_output_mapping:
          k = temp_output_mapping[k]
        k = k.replace('_', '-')
        result[k] = v
    return result


@dataclass
class DecompositionCascade:
  """List of Decompositions sorted by priority in which they are tried."""
  condition: Optional[RegexComponent]
  alternatives: List[Union[Decomposition, "DecompositionCascade"]]

  @classmethod
  def from_yaml_dict(cls, yaml) -> Optional["DecompositionCascade"]:
    if 'decomposition_cascade' not in yaml:
      return None
    yaml = yaml['decomposition_cascade']
    condition = None
    if 'condition' in yaml:
      condition = parse_regex_component_from_yaml_dict(yaml['condition'])
    alternatives = [
        Decomposition.from_yaml_dict(alternative)
        or DecompositionCascade.from_yaml_dict(alternative)
        for alternative in yaml['alternatives']
    ]

    return DecompositionCascade(condition=condition, alternatives=alternatives)

  @classmethod
  def schema(cls):
    decomp_schema = {
        'decomposition_cascade': {
            schema.Optional('condition'): REGEX_COMPONENT_SCHEMA,
            # 'alternatives': [schema.Or(schema, Decomposition.schema() ]
            # is added below
        }
    }
    decomp_schema['decomposition_cascade']['alternatives'] = [
        schema.Or(decomp_schema, Decomposition.schema())
    ]
    return decomp_schema

  def to_regex_list(self, engine: "ParsingEngine",
                    temp_output_mapping: Dict) -> List[str]:
    result = []
    for a in self.alternatives:
      if type(a) == Decomposition:
        result.append(
            cast(Decomposition, a).to_regex(engine, temp_output_mapping))
      elif type(a) == DecompositionCascade:
        result.append(*cast(DecompositionCascade, a).to_regex_list(
            engine, temp_output_mapping))
      else:
        raise ValueError(f"Unexpected type {type(a)}")
    return result

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    if self.condition:
      self.condition.validate(engine, model, errors)
    for alternative in self.alternatives:
      alternative.validate(engine, model, errors)

  def evaluate(self, data: str, engine: "ParsingEngine",
               temp_output_mapping: Dict) -> Dict:
    # If we have a condition but it's not fulfilled, don't return anything.
    if self.condition:
      # Wrap in () to make sure that we have capture something
      regex = self.condition.to_regex(engine, {})
      if not re2.search(regex, data):
        return {}
    for p in self.alternatives:
      if result := p.evaluate(data, engine, temp_output_mapping):
        return result
    return {}


@dataclass
class ExtractPart:
  """Extracts data at an arbitrary position in the input data"""
  condition: Optional[RegexComponent]
  capture: Union[Capture, CaptureReference]

  @classmethod
  def from_yaml_dict(cls, yaml) -> Optional["ExtractPart"]:
    if 'extract_part' not in yaml:
      return None
    yaml = yaml['extract_part']
    condition = None
    if 'condition' in yaml:
      condition = parse_regex_component_from_yaml_dict(yaml['condition'])
    capture = (Capture.from_yaml_dict(yaml)
               or CaptureReference.from_yaml_dict(yaml))

    return ExtractPart(condition=condition, capture=capture)

  @classmethod
  def schema(cls):
    return {
        'extract_part': {
            schema.Optional('condition'): REGEX_COMPONENT_SCHEMA,
            schema.Optional('capture'): Capture.schema_capture()['capture'],
            schema.Optional('capture_reference'): \
                CaptureReference.schema()['capture_reference'],
        }
    }

  def to_regex(self, engine: "ParsingEngine", temp_output_mapping: Dict) -> str:
    resolved = self.capture.resolve(engine)
    return resolved.to_regex(None, engine, temp_output_mapping)

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    if self.condition:
      self.condition.validate(engine, model, errors)
    self.capture.validate(engine, model, errors)

  def evaluate(self, data: str, engine: "ParsingEngine",
               temp_output_mapping: Dict) -> Dict:
    # If we have a condition but it's not fulfilled, don't return anything.
    if self.condition:
      # Wrap in () to make sure that we have capture something
      regex = self.condition.to_regex(engine, {})
      if not re2.search(regex, data):
        return {}
    resolved = self.capture.resolve(engine)
    if type(resolved) == Capture:
      return cast(Capture, resolved).evaluate(data, engine, temp_output_mapping)
    elif type(self.capture) == Separator:
      return {}
    else:
      raise ValueError(f"Unexpected type {type(resolved)}")


@dataclass
class ExtractParts:
  """Extracts data at an arbitrary position in the input data"""
  condition: Optional[RegexComponent]
  parts: List[ExtractPart]

  @classmethod
  def from_yaml_dict(cls, yaml) -> Optional["ExtractParts"]:
    if 'extract_parts' not in yaml:
      return None
    yaml = yaml['extract_parts']
    condition = None
    if 'condition' in yaml:
      condition = parse_regex_component_from_yaml_dict(yaml['condition'])
    parts = [ExtractPart.from_yaml_dict(p) for p in yaml['parts']]

    return ExtractParts(condition=condition, parts=parts)

  @classmethod
  def schema(cls):
    return {
        'extract_parts': {
            schema.Optional('condition'): REGEX_COMPONENT_SCHEMA,
            'parts': [ExtractPart.schema()]
        }
    }

  def to_regex_list(self, engine: "ParsingEngine",
                    temp_output_mapping: Dict) -> List[str]:
    return [p.to_regex(engine, temp_output_mapping) for p in self.parts]

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    if self.condition:
      self.condition.validate(engine, model, errors)
    for p in self.parts:
      p.validate(engine, model, errors)

  def evaluate(self, data: str, engine: "ParsingEngine",
               temp_output_mapping: Dict) -> Dict:
    # If we have a condition but it's not fulfilled, don't return anything.
    if self.condition:
      # Wrap in () to make sure that we have capture something
      regex = self.condition.to_regex(engine, {})
      if not re2.search(regex, data):
        return {}

    result = {}
    for p in self.parts:
      result.update(p.evaluate(data, engine, temp_output_mapping))
    return result


PARSING_COMPONENT_SCHEMA = schema.Or(Decomposition.schema(),
                                     DecompositionCascade.schema(),
                                     ExtractPart.schema(),
                                     ExtractParts.schema())


def parse_parsing_component_from_yaml_dict(yaml) -> Optional[ParsingComponent]:
  return (Decomposition.from_yaml_dict(yaml)
          or DecompositionCascade.from_yaml_dict(yaml)
          or ExtractPart.from_yaml_dict(yaml)
          or ExtractParts.from_yaml_dict(yaml))


@dataclass
class ParsingEngine:
  regex_definitions: Dict[str, RegexComponent] = field(default_factory=dict)
  capture_definitions: Dict[str, CaptureComponent] = field(default_factory=dict)
  parsing_definitions: Dict[str, ParsingComponent] = field(default_factory=dict)

  def validate(self, model: Model) -> bool:
    # Returns true if the rules seem valid.

    def _validate(name, container):
      for key, value in container.items():
        errors = []
        value.validate(self, model, errors)
        if errors:
          print(f"Error(s) in {name}['{key}']: {errors}")
          return False
      return True

    return (_validate("regex_definitions", self.regex_definitions)
            and _validate("capture_definitions", self.capture_definitions)
            and _validate("parsing", self.parsing_definitions))

  def prune_output_types(self, types_to_prune):

    def _helper(node):
      if type(node) == Capture:
        capture_node = cast(Capture, node)
        if capture_node.output in types_to_prune:
          capture_node.output = None
        for p in capture_node.parts:
          _helper(p)
      elif type(node) == Decomposition:
        _helper(cast(Decomposition, node).capture)
      elif type(node) == DecompositionCascade:
        for a in cast(DecompositionCascade, node).alternatives:
          _helper(a)
      elif type(node) == ExtractPart:
        _helper(cast(ExtractPart, node).capture)
      elif type(node) == ExtractParts:
        for a in cast(ExtractParts, node).parts:
          _helper(a)
      elif type(node) == CaptureReference:
        _helper(cast(CaptureReference, node).resolve(self))
      elif type(node) in (RegexReference, RegexFragment, RegexConcat,
                          Separator):
        pass
      else:
        raise ValueError(f"Not handled type: {node}")

    for _, p in self.capture_definitions.items():
      _helper(p)
    for _, p in self.parsing_definitions.items():
      _helper(p)
    for t in types_to_prune:
      if t in self.parsing_definitions:
        del self.parsing_definitions[t]
