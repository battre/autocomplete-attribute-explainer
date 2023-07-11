import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Union, Optional, Iterator, Set
# using strenum for backwards compatibility
from strenum import StrEnum

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


### Captures components: higher-level, more powerful regex

CaptureComponent = Union["NoCapturePattern", "CaptureTypeWithPattern",
                         "CaptureTypeWithPattern"]


@dataclass
class CaptureReference:
  name: str


class MatchQuantifier(StrEnum):
  # The capture group is required.
  MATCH_REQUIRED = "MATCH_REQUIRED"
  # The capture group is optional.
  MATCH_OPTIONAL = "MATCH_OPTIONAL"
  # The capture group is lazy optional meaning that it is avoided if an overall
  # match is possible.
  MATCH_LAZY_OPTIONAL = "MATCH_LAZY_OPTIONAL"


@dataclass
class CaptureOptions:
  # A separator that must be matched after a capture group.
  # By default, a group must be either followed by a space-like character (\s)
  # or it must be the last group in the line. The separator is allowed to be
  # empty.
  separator: Union["RegexFragment", "RegexReference"] = RegexFragment(',|\s+|$')

  # Indicates if the group is required, optional or even lazy optional.
  quantifier: MatchQuantifier = MatchQuantifier.MATCH_REQUIRED


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


@dataclass
class CaptureTypeWithPattern:
  """A capturing regex pattern"""
  output: str  # Field-type e.g. given-name
  parts: List[Union[CaptureReference, NoCapturePattern,
                    "CaptureTypeWithPattern"]]
  options: CaptureOptions


@dataclass
class CaptureTypeWithPatternCascade:
  """List of CaptureTypeWithPattern sorted by priority in which they are tried."""
  # The output of this cascade. This is just for documentation purposes because
  # all patterns need to generate this FieldType and share the same `out` value.
  output: str
  patterns: List[CaptureTypeWithPattern]


@dataclass
class ParsingEngine:
  regexes: Dict[str, RegexComponent] = field(default_factory=dict)
  capture_patterns_constants: Dict[str, CaptureComponent] = field(
      default_factory=dict)
  capture_patterns: Dict[str, Union[CaptureTypeWithPattern,
                                    CaptureTypeWithPatternCascade]] = field(
                                        default_factory=dict)
