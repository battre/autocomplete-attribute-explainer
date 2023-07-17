import re2
from dataclasses import dataclass, field
from typing import Dict, List, Union, Optional
# using strenum for backwards compatibility
from strenum import StrEnum
from modules.model.model import Model

### The following are low-level tools to create simple regular expressions.


@dataclass
class RegexFragment:
  """A full regular expression or a substring of a regular expression.

  This can exist for example in the context of named regular expression or
  can be a component of a larger regex (see below).

  ```
  regex_constants:
    {constant_name}:
      regex_fragment: {regex_fragment}
  ```

  where constant_name could be "kSingleWordRe" and regex_fragment could be
  '(?:[^\s,]+)'.

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

  def to_regex(self, engine: "ParsingEngine") -> str:
    return self.value

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    try:
      re2.compile(self.to_regex(engine))
    except Exception as e:
      errors.append(e.str())


@dataclass
class RegexReference:
  """Lookup of regular expression by name.

  Name/Value pairs are stored in the ParsingEngine.

  ```
  regex_constants:
    {constant_name}:
      regex_reference: {other_constant_name}
  ```
  """
  name: str

  def to_regex(self, engine: "ParsingEngine") -> str:
    return engine.regexes[self.name].to_regex(engine)

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    if self.name not in engine.regexes:
      errors.append(f"Undefined reference {self.name}")

  def resolve(self, engine: "ParsingEngine") -> "RegexComponent":
    what = self
    while type(what) == RegexReference:
      what = engine.regexes[what.name]
    return what


"""A part of a compound regex."""
RegexComponent = Union["RegexFragment", "RegexReference", "RegexConcat"]


@dataclass
class RegexConcat:
  """Concatenates a series of regular expressions in a non-capture group.

  ```
  regex_constants:
    {constant_name}:
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

  def to_regex(self, engine: "ParsingEngine") -> str:
    # The components and the final string are wrapped in non-capture groups
    # to reduce the risk of side-effects between the components. Imagine
    # the RegexFragments A = "a|b" and B="c". Concatenating them as "a|bc" would
    # probably be unexpected.
    result = "".join([p.to_regex(engine) for p in self.parts])
    if self.wrap_non_capture:
      return "(?:" + result + ")"
    return result

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    try:
      re2.compile(self.to_regex(engine))
    except Exception as e:
      errors.append(e.str())


### Captures components: higher-level, more powerful regex

CaptureComponent = Union["NoCapturePattern", "CaptureTypeWithPattern",
                         "CaptureTypeWithPattern"]


@dataclass
class CaptureReference:
  name: str

  def to_regex(self, engine: "ParsingEngine") -> str:
    if self.name in engine.capture_patterns_constants:
      return engine.capture_patterns_constants[self.name].to_regex(engine)

    return engine.regexes[self.name].to_regex(engine)

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    if (self.name not in engine.regexes
        and self.name not in engine.capture_patterns_constants):
      errors.append(f"Undefined reference {self.name}")

  def resolve(self, engine: "ParsingEngine") -> "RegexComponent":
    what = self
    while type(what) in (RegexReference, CaptureReference):
      if type(what) == RegexReference:
        what = what.resolve(engine)
      elif type(what) == CaptureReference:
        what = engine.capture_patterns_constants[what.name]
    return what


class MatchQuantifier(StrEnum):
  # The capture group is required.
  MATCH_REQUIRED = "MATCH_REQUIRED"
  # The capture group is optional.
  MATCH_OPTIONAL = "MATCH_OPTIONAL"
  # The capture group is lazy optional meaning that it is avoided if an overall
  # match is possible.
  MATCH_LAZY_OPTIONAL = "MATCH_LAZY_OPTIONAL"

  def to_regex_suffix(self) -> str:
    if (self == MatchQuantifier.MATCH_REQUIRED):
      return ""
    elif (self == MatchQuantifier.MATCH_OPTIONAL):
      return "?"
    elif (self == MatchQuantifier.MATCH_LAZY_OPTIONAL):
      return "??"
    else:
      assert (False)


@dataclass
class CaptureOptions:
  # A separator that must be matched after a capture group.
  # By default, a group must be either followed by a space-like character (\s)
  # or it must be the last group in the line. The separator is allowed to be
  # empty.
  separator: Union["RegexFragment", "RegexReference"] = field(
      default_factory=lambda: RegexFragment(',|\s+|$'))

  # Indicates if the group is required, optional or even lazy optional.
  quantifier: MatchQuantifier = MatchQuantifier.MATCH_REQUIRED

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    if not self.separator:
      errors.append("CaptureOptions misses a separator")
    else:
      self.separator.validate(engine, model, errors)
    if not self.quantifier:
      errors.append("CaptureOptions misses a quantifier")


@dataclass
class NoCapturePattern:
  """A non-capturing regex pattern that consists of a concatenation of RegexComponents.

  E.g.
  NoCapturePattern:
    pattern:
      - regex_concat:
          parts:
          - regex: 'Foo'
          - regex: '|'
          - regex_reference: 'kOtherRegex'

  Evaluates to the concatenation of all pattern evaluations.
  """
  pattern: RegexComponent
  options: CaptureOptions

  def to_regex(self, engine: "ParsingEngine") -> str:
    pattern_regex = self.pattern.to_regex(engine)
    separator = self.options.separator.to_regex(engine)
    quantifier = MatchQuantifier.to_regex_suffix(self.options.quantifier)
    return f"(?:{pattern_regex}(?:{separator})+){quantifier}"

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    if not self.pattern:
      self.errors.append("Missing a pattern")
    if not self.options:
      self.errors.append("Missing options")
    else:
      self.options.validate(engine, model, errors)


@dataclass
class CaptureTypeWithPattern:
  """A capturing regex pattern"""
  output: str  # Field-type e.g. given-name
  parts: List[Union[CaptureReference, NoCapturePattern,
                    "CaptureTypeWithPattern", RegexFragment, RegexReference,
                    RegexConcat]]
  options: CaptureOptions

  def to_regex(self, engine: "ParsingEngine") -> str:
    # RE2 does not allow '-' in capture groups, so we replace it with an
    # underscore and do the inverse in evaluate().
    output = self.output.replace('-', '_')
    pattern_regex = "".join(
        [pattern.to_regex(engine) for pattern in self.parts])
    separator = self.options.separator.to_regex(engine)
    quantifier = MatchQuantifier.to_regex_suffix(self.options.quantifier)
    prefix = ""
    suffix = ""
    return f"(?i:{prefix}(?P<{output}>{pattern_regex}){suffix}" + \
           f"(?:{separator})+){quantifier}"

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    if not self.output:
      errors.append("Invalid output")
    if self.output not in model.concepts:
      errors.append("Undefined output type '{self.output}'")
    for part in self.parts:
      part.validate(engine, model, errors)
    if not self.options:
      self.errors.append("Missing options")
    else:
      self.options.validate(engine, model, errors)

  def evaluate(self, data, engine) -> Dict:
    """Evaluates the `CaptureTypeWithPattern` on `data`."""
    regex = self.to_regex(engine)
    if regex_result := re2.fullmatch(regex, data):
      return {
          k.replace('_', '-'): v
          for k, v in regex_result.groupdict().items()
      }
    return {}


@dataclass
class CaptureTypeWithPatternCascade:
  """List of CaptureTypeWithPattern sorted by priority in which they are tried."""
  # The output of this cascade. This is just for documentation purposes because
  # all patterns need to generate this FieldType and share the same `out` value.
  output: str
  condition: Optional[RegexComponent]
  patterns: List[CaptureTypeWithPattern]

  def to_regex_list(self, engine: "ParsingEngine") -> str:
    return [p.to_regex(engine) for p in self.patterns]

  def validate(self, engine: "ParsingEngine", model: Model, errors: List[str]):
    if not self.output:
      errors.append("Invalid output")
    if self.output not in model.concepts:
      errors.append("Undefined output type '{self.output}'")
    if self.condition:
      self.condition.validate(engine, model, errors)
    for pattern in self.patterns:
      if type(pattern) in (CaptureReference, RegexReference):
        pattern = pattern.resolve(engine)
      pattern.validate(engine, model, errors)
      if pattern.output != self.output:
        errors.append(
            f"Mismatching outputs: {self.output} vs. {pattern.output}" +
            f"in {self} vs. {pattern}")

  def evaluate(self, data, engine) -> Dict:
    # If we have a condition but it's not fulfilled, don't return anything.
    if self.condition:
      # Wrap in () to make sure that we have capture something
      regex = self.condition.to_regex(engine)
      if not re2.search(regex, data):
        return {}
    for p in self.patterns:
      while type(p) in (RegexReference, CaptureReference):
        p = p.resolve(engine)
      if result := p.evaluate(data, engine):
        return result
    return {}


@dataclass
class ParsingEngine:
  regexes: Dict[str, RegexComponent] = field(default_factory=dict)
  capture_patterns_constants: Dict[str, CaptureComponent] = field(
      default_factory=dict)
  capture_patterns: Dict[str, Union[CaptureTypeWithPattern,
                                    CaptureTypeWithPatternCascade]] = field(
                                        default_factory=dict)

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

    if not _validate("regexes", self.regexes):
      return False
    if not _validate("capture_patterns_constants",
                     self.capture_patterns_constants):
      return False
    if not _validate("capture_patterns", self.capture_patterns):
      return False
    return True
