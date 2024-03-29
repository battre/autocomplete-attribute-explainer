import re2
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Set, Union, Tuple, Optional, cast
import schema
from enum import auto, Enum
from modules.model.model import Model

#### The following are low-level tools to create simple regular expressions.
"""A part of a compound regex."""
RegexComponent = Union["RegexFragment", "RegexReference", "RegexConcat"]
# Elements RegexFragment, RegexReference and RegexConcat are added below.
REGEX_COMPONENT_SCHEMA = schema.Or()

# The first parameter of the tuple is a dictionary of key-value maps, where
# the key is a type and the value is the matched substring.
# The second parameter of the tuple is a set of regular expressions that led
# to these matches. This can be useful for debugging.
MatchesAndRegexUsed = Tuple[Dict[str, str], Set[str]]

# Invariant about safety: Every to_regex() function should return a regular
# expression that is safe to concatenate (even with "|") to other such regular
# expressions. For RegexFragment, RegexReference and RegexConcat it is the job
# expression author to ensure this. This applies particularly to separators,
# where "|" is common.
# Appending a quantifier (+, *, ?, ??) requires the site that appends the
# quantifier to protect the inner regex.


def parse_regex_component_from_yaml_dict(yaml) -> Optional[RegexComponent]:
  return (RegexFragment.from_yaml_dict(yaml)
          or RegexReference.from_yaml_dict(yaml)
          or RegexConcat.from_yaml_dict(yaml))


@dataclass
class CaptureMapper:
  """Class to deal with mapping duplicate named captures.

  A regex must not contain duplicate capture groups like this
  '(?P<foo>\w+)|(?P<foo>\w+)'

  This CaptureMapper ensures that capture groups get assigned unique names.
  In this case: '(?P<foo>\w+)|(?P<foo-2>\w+)'
  """
  occurrences: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

  def get_and_increment(self, type: str) -> str:
    self.occurrences[type] += 1
    if self.occurrences[type] == 1:
      return type
    # We use two hyphens here because that's a pattern that does not exist in
    # the field names.
    return f"{type}--{self.occurrences[type]}"

  def reverse(self, type: str) -> str:
    for k, _ in self.occurrences.items():
      if match := re2.match(f"({k})--\d+", type):
        return match.group(1)
    return type


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

  def to_regex(self, engine: "ParsingEngine", mapper: CaptureMapper) -> str:
    return self.value

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    try:
      re2.compile(self.to_regex(engine, CaptureMapper()))
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

  def to_regex(self, engine: "ParsingEngine", mapper: CaptureMapper) -> str:
    return self.resolve(engine).to_regex(engine, mapper)

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

  def to_regex(self, engine: "ParsingEngine", mapper: CaptureMapper) -> str:
    # The components and the final string are wrapped in non-capture groups
    # to reduce the risk of side-effects between the components. Imagine
    # the RegexFragments A = "a|b" and B="c". Concatenating them as "a|bc" would
    # probably be unexpected.
    result = "".join([p.to_regex(engine, mapper) for p in self.parts])
    if self.wrap_non_capture:
      return f"(?:{result})"
    return result

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    try:
      re2.compile(self.to_regex(engine, CaptureMapper()))
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

  def to_regex(self, engine: "ParsingEngine", mapper: CaptureMapper) -> str:
    return self.resolve(engine).to_regex(engine, mapper)

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
               mapper: CaptureMapper) -> MatchesAndRegexUsed:
    resolved = self.resolve(engine)
    if type(resolved) == Capture:
      return cast(Capture, resolved).evaluate(data, engine, mapper)
    return {}, set()


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

  def to_regex(self, engine: "ParsingEngine", mapper: CaptureMapper) -> str:
    return self.value.to_regex(engine, mapper)

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    self.value.validate(engine, model, errors)

  def evaluate(self, data: str, engine: "ParsingEngine",
               mapper: CaptureMapper) -> MatchesAndRegexUsed:
    return {}, set()


@dataclass
class Capture:
  """A capturing regex pattern

  If the "output" is specified, the regex contains a capture group for the
  specified name. Otherwise, this describes a "no_capture" pattern.
  """
  output: Optional[str]  # Field-type e.g. given-name
  prefix: Optional[Union[RegexFragment, RegexReference, RegexConcat]]
  suffix: Optional[Union[RegexFragment, RegexReference, RegexConcat]]
  parts: Optional[List[Union[CaptureReference, "Capture", RegexFragment,
                             RegexReference, RegexConcat]]]
  alternatives: Optional[List[Union[CaptureReference, "Capture", RegexFragment,
                                    RegexReference, RegexConcat]]]
  quantifier: MatchQuantifier

  @classmethod
  def from_yaml_dict(cls, yaml) -> Optional["Capture"]:
    output = None
    prefix = None
    suffix = None
    parts = None
    alternatives = None
    if 'capture' in yaml:
      yaml = yaml['capture']
      output = yaml['output']
      prefix = parse_regex_component_from_yaml_dict(yaml.get('prefix', {}))
      suffix = parse_regex_component_from_yaml_dict(yaml.get('suffix', {}))
      parts = [
          _parse_capture_or_regex_component(part) for part in yaml['parts']
      ]
    elif 'no_capture' in yaml:
      yaml = yaml['no_capture']
      if 'parts' in yaml:
        parts = [
            _parse_capture_or_regex_component(part) for part in yaml['parts']
        ]
        assert 'alternatives' not in yaml, \
          f"There should be no alternatives in {yaml}"
      elif 'alternatives' in yaml:
        alternatives = [
            _parse_capture_or_regex_component(alternative)
            for alternative in yaml['alternatives']
        ]
      else:
        assert False, f"no_capture should have 'parts' or 'alternatives': {yaml}"
    else:
      return None
    quantifier = (MatchQuantifier.from_yaml_dict(yaml.get('quantifier'))
                  or MatchQuantifier.MATCH_REQUIRED)

    return Capture(output=output,
                   prefix=prefix,
                   parts=parts,
                   alternatives=alternatives,
                   suffix=suffix,
                   quantifier=quantifier)

  @classmethod
  def schema_capture(cls):
    global REGEX_COMPONENT_SCHEMA, CAPTURE_COMPONENT_SCHEMA
    return {
        'capture': {
            'output': str,
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
            schema.Optional('parts'): [_capture_or_regex_component],
            schema.Optional('alternatives'): [_capture_or_regex_component],
            schema.Optional('quantifier'): MatchQuantifier.schema()
        }
    }

  def resolve(self, engine: "ParsingEngine") -> CaptureOrRegexComponent:
    return self

  def to_regex(self, preceding_separator: Optional[RegexComponent],
               engine: "ParsingEngine", mapper: CaptureMapper) -> str:
    separator = (preceding_separator.to_regex(engine, CaptureMapper())
                 if preceding_separator else "")
    prefix = (self.prefix.to_regex(engine, CaptureMapper())
              if self.prefix else "")
    suffix = (self.suffix.to_regex(engine, CaptureMapper())
              if self.suffix else "")

    pattern_regex = ""
    if self.parts:
      i = 0
      while i < len(self.parts):
        part_i = self.parts[i].resolve(engine)
        if (type(part_i) == Separator and i + 1 < len(self.parts)
            and type(self.parts[i + 1].resolve(engine)) == Capture):
          next_capture = self.parts[i + 1].resolve(engine)
          pattern_regex += next_capture.to_regex(part_i, engine, mapper)
          i += 1
        elif type(part_i) == Capture:
          pattern_regex += part_i.to_regex(None, engine, mapper)
        else:
          pattern_regex += part_i.to_regex(engine, mapper)
        i += 1
    elif self.alternatives:
      pattern_regex = ("(?:" + "|".join([
          a.resolve(engine).to_regex(None, engine, mapper)
          for a in self.alternatives
      ]) + ")")
    else:
      assert False

    quantifier = MatchQuantifier.to_regex_suffix(self.quantifier)
    if self.output:
      # RE2 does not allow '-' in capture groups, so we replace it with an
      # underscore and do the inverse in evaluate().
      output = mapper.get_and_increment(self.output)
      output = output.replace('-', '_')
      if separator or prefix or suffix:
        return f"(?:{separator}{prefix}(?P<{output}>{pattern_regex})" + \
          f"{suffix}){quantifier}"
      else:
        return f"(?P<{output}>{pattern_regex}){quantifier}"
    else:
      if quantifier:
        return f"(?:{separator}{pattern_regex}){quantifier}"
      else:
        return f"{separator}{pattern_regex}"

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    if self.output and self.output not in model.concepts:
      errors.append(f"Undefined output type '{self.output}'")
    if self.prefix:
      self.prefix.validate(engine, model, errors)
    if self.suffix:
      self.suffix.validate(engine, model, errors)
    for part in self.parts or self.alternatives:
      part.validate(engine, model, errors)

  def evaluate(self, data: str, engine: "ParsingEngine",
               mapper: CaptureMapper) -> MatchesAndRegexUsed:
    """Evaluates the `CaptureTypeWithPattern` on `data`."""
    regex = self.to_regex(None, engine, mapper)
    result = {}
    regex_used = set()
    multi_line_prefix = "(?m)"
    if regex_result := re2.search(f"{multi_line_prefix}(?i:{regex})", data):
      for k, v in regex_result.groupdict().items():
        if v:
          k = k.replace('_', '-')
          k = mapper.reverse(k)
          result[k] = v
      regex_used.add(regex)
    return result, regex_used


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

  def to_regex(self, engine: "ParsingEngine", mapper: CaptureMapper) -> str:
    prefix = "^" if self.anchor_beginning else ""
    suffix = "$" if self.anchor_end else ""
    regex = self.capture.resolve(engine).to_regex(None, engine, mapper)
    return f"{prefix}{regex}{suffix}"

  def evaluate(self, data: str, engine: "ParsingEngine",
               mapper: CaptureMapper) -> MatchesAndRegexUsed:
    """Evaluates the `Decomposition` on `data`."""
    regex = self.to_regex(engine, mapper)
    result = {}
    regex_used = set()
    multi_line_prefix = "(?m)"
    if regex_result := re2.search(f"{multi_line_prefix}(?i:{regex})", data):
      for k, v in regex_result.groupdict().items():
        if v:
          k = k.replace('_', '-')
          k = mapper.reverse(k)
          result[k] = v
      regex_used.add(regex)

    return result, regex_used


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
                    mapper: CaptureMapper) -> List[str]:
    result = []
    for a in self.alternatives:
      if type(a) == Decomposition:
        result.append(cast(Decomposition, a).to_regex(engine, mapper))
      elif type(a) == DecompositionCascade:
        result.extend(
            cast(DecompositionCascade, a).to_regex_list(engine, mapper))
      else:
        raise ValueError(f"Unexpected type {type(a)}")
    return result

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    if self.condition:
      self.condition.validate(engine, model, errors)
    for alternative in self.alternatives:
      alternative.validate(engine, model, errors)

  def evaluate(self, data: str, engine: "ParsingEngine",
               mapper: CaptureMapper) -> MatchesAndRegexUsed:
    # If we have a condition but it's not fulfilled, don't return anything.
    if self.condition:
      # Wrap in () to make sure that we have capture something
      regex = self.condition.to_regex(engine, CaptureMapper())
      multi_line_prefix = "(?m)"
      if not re2.search(f"{multi_line_prefix}(?i:{regex})", data):
        return {}, set()
    for p in self.alternatives:
      result, regex_used = p.evaluate(data, engine, mapper)
      if result:
        return result, regex_used
    return {}, set()


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

  def to_regex(self, engine: "ParsingEngine", mapper: CaptureMapper) -> str:
    resolved = self.capture.resolve(engine)
    return resolved.to_regex(None, engine, mapper)

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    if self.condition:
      self.condition.validate(engine, model, errors)
    self.capture.validate(engine, model, errors)

  def evaluate(self, data: str, engine: "ParsingEngine",
               mapper: CaptureMapper) -> MatchesAndRegexUsed:
    # If we have a condition but it's not fulfilled, don't return anything.
    if self.condition:
      # Wrap in () to make sure that we have capture something
      regex = self.condition.to_regex(engine, CaptureMapper())
      multi_line_prefix = "(?m)"
      if not re2.search(f"{multi_line_prefix}(?i:{regex})", data):
        return {}, set()
    resolved = self.capture.resolve(engine)
    if type(resolved) == Capture:
      return cast(Capture, resolved).evaluate(data, engine, mapper)
    elif type(self.capture) == Separator:
      return {}, set()
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
                    mapper: CaptureMapper) -> List[str]:
    return [p.to_regex(engine, mapper) for p in self.parts]

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    if self.condition:
      self.condition.validate(engine, model, errors)
    for p in self.parts:
      p.validate(engine, model, errors)

  def evaluate(self, data: str, engine: "ParsingEngine",
               mapper: CaptureMapper) -> MatchesAndRegexUsed:
    # If we have a condition but it's not fulfilled, don't return anything.
    if self.condition:
      # Wrap in () to make sure that we have capture something
      regex = self.condition.to_regex(engine, CaptureMapper())
      multi_line_prefix = "(?m)"
      if not re2.search(f"{multi_line_prefix}(?i:{regex})", data):
        return {}, set()

    result = {}
    regex_used = set()
    for p in self.parts:
      local_result, local_regex_used = p.evaluate(data, engine, mapper)
      if local_result:
        # If the same token is matched multiple times, only the last extracted
        # value will be returned.
        result.update(local_result)
        regex_used = regex_used.union(local_regex_used)

    return result, regex_used


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
        for p in capture_node.parts or capture_node.alternatives:
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
