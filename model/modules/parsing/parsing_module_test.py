import unittest

from renderer import Renderer
from unittest.mock import patch, mock_open
from modules.model import ParseGlobalModelModule, ParseCountryModelModule
from modules.parsing import ParsingModule
from pathlib import Path
from textwrap import dedent

GLOBAL_MODEL_FILENAME = "test/global-model.yaml"
GLOBAL_PARSING_FILENAME = "test/global-parsing-rules.yaml"

DEFAULT_GLOBAL_MODEL = """\
concepts:
- A:
  - B:
    - C
    - D
  - E
"""


class OpenMock:

  def __init__(self):
    self.read = self
    self.file_content = ""

  def __call__(self, *args, **kwargs):
    return mock_open(read_data=self.file_content)(*args, **kwargs)


class TestFormattingModule(unittest.TestCase):

  def setUp(self):
    self.renderer = Renderer()

  def setUpCountryModel(self, country, model_file_content):
    with patch("builtins.open", new_callable=OpenMock) as mock:
      mock.file_content = model_file_content
      path = Path(f"test/{country}-model.yaml")
      if country == 'global':
        ParseGlobalModelModule().observe_file(path, self.renderer)
      else:
        ParseCountryModelModule().observe_file(path, self.renderer)

  def setUpModel(self, model_file_content):
    self.setUpCountryModel('global', model_file_content)

  def setUpCountryParsing(self, country, file_content):
    self.parsing = ParsingModule()
    with patch("builtins.open", new_callable=OpenMock) as mock:
      mock.file_content = file_content
      self.parsing.observe_file(Path(f"test/{country}-parsing-rules.yaml"),
                                self.renderer)
      self.parsing_engine = self.renderer.country_data[country]['ParsingEngine']

  def setUpParsing(self, file_content):
    self.setUpCountryParsing('global', file_content)

  def test_new_lines_in_regex_constant(self):
    # Test that a named rule is resolved.
    self.setUpModel(dedent(DEFAULT_GLOBAL_MODEL))
    # Verify that the newline is stripped.
    self.setUpParsing(
        dedent("""\
        regex_constants:
          kConst:
            regex_fragment: |-
              a
              b
        """))
    result = self.parsing_engine.regexes.get('kConst')
    self.assertIsNotNone(result)
    self.assertEqual(result.to_regex(self.parsing_engine), "ab")

    # Verify that the whitespace is not stripped:
    # Note that the \\ evaluates to a single \ in the simulated file read
    # operation.
    self.setUpParsing(
        dedent("""\
        regex_constants:
          kConst:
            regex_fragment:
              "a \\
              b"
        """))
    result = self.parsing_engine.regexes.get('kConst')
    self.assertIsNotNone(result)
    self.assertEqual(result.to_regex(self.parsing_engine), "a b")

  def test_parsing_regex(self):
    # Test that a named rule is resolved.
    self.setUpModel(dedent(DEFAULT_GLOBAL_MODEL))
    # Verify that the newline is stripped.
    self.setUpParsing(
        dedent("""\
        regex_constants:
          kFragment:
            regex_fragment: ab
          kReference:
            regex_reference: kFragment
          kConcat:
            regex_concat:
              parts:
              - regex_fragment: c
              - regex_reference: kFragment
              - regex_concat:
                  parts:
                  - regex_fragment: d
                  - regex_fragment: e
                  options:
                    wrap_non_capture: false
        """))
    result = self.parsing_engine.regexes.get('kFragment')
    self.assertIsNotNone(result)
    self.assertEqual(result.to_regex(self.parsing_engine), "ab")

    result = self.parsing_engine.regexes.get('kReference')
    self.assertIsNotNone(result)
    self.assertEqual(result.to_regex(self.parsing_engine), "ab")

    result = self.parsing_engine.regexes.get('kConcat')
    self.assertIsNotNone(result)
    self.assertEqual(result.to_regex(self.parsing_engine), "(?:cabde)")

  def test_parsing_capture_components(self):
    self.setUpModel(dedent(DEFAULT_GLOBAL_MODEL))
    # Test that a named rule is resolved.
    self.setUpParsing(
        dedent("""\
        regex_constants:
          kFragment:
            regex_fragment: ab

        capture_pattern_constants:
          kReference:
            capture_reference: kFragment
          kNoCapturePattern:
            no_capture_pattern:
              parts:
                - regex_reference: kFragment
              options:
                quantifier: MATCH_OPTIONAL
                separator:
                  regex_fragment: sep
          kCaptureTypeWithPattern:
            capture_type_with_pattern:
              output: B
              parts:
                - capture_reference: kReference
                - capture_reference: kNoCapturePattern
              # options remain empty and should be default options
        """))

    result = self.parsing_engine.capture_patterns_constants.get('kReference')
    self.assertIsNotNone(result)
    self.assertEqual(result.to_regex(self.parsing_engine), "ab")

    result = self.parsing_engine.capture_patterns_constants.get(
        'kNoCapturePattern')
    self.assertIsNotNone(result)
    self.assertEqual(result.to_regex(self.parsing_engine), "(?i:ab(?:sep)+)?")

    result = self.parsing_engine.capture_patterns_constants.get(
        'kCaptureTypeWithPattern')
    self.assertIsNotNone(result)
    self.assertEqual(result.to_regex(self.parsing_engine),
                     "(?i:(?P<B>ab(?i:ab(?:sep)+)?)(?:,|\s+|$)+)")

  def test_parsing_capture_cascade(self):
    self.setUpModel(dedent(DEFAULT_GLOBAL_MODEL))
    # Test that a named rule is resolved.
    self.setUpParsing(
        dedent("""\
        regex_constants:
          kFragment:
            regex_fragment: ab

        capture_pattern_constants:
          kP1:
            capture_type_with_pattern:
              output: A
              parts:
                - regex_fragment: a.*a
          kP2:
            capture_type_with_pattern:
              output: A
              parts:
                - regex_fragment: b.*b

        capture_patterns:
          kP3:
            capture_type_with_pattern_cascade:
              output: A
              patterns:
                - capture_reference: kP1
                - capture_reference: kP2
                - capture_type_with_pattern:
                    output: A
                    parts:
                      - regex_fragment: c.*c
        """))

    result = self.parsing_engine.capture_patterns.get('kP3')
    self.assertIsNotNone(result)
    self.assertEqual(result.to_regex_list(self.parsing_engine), [
        '(?i:(?P<A>a.*a)(?:,|\\s+|$)+)',
        '(?i:(?P<A>b.*b)(?:,|\\s+|$)+)',
        '(?i:(?P<A>c.*c)(?:,|\\s+|$)+)',
    ])

  def test_pruning(self):
    # This is a complex test where a global model is set up which is then
    # modified by a country model that prunes some of the types used in capture
    # patterns.
    self.setUpModel(
        dedent("""\
      concepts:
      - A:
        - B:
          - C
          - D
        - E:
          - F
          - G
      """))
    self.setUpCountryModel(
        "XX",
        dedent("""\
      cut-off-children:
      - B
      cut-off-tokens:
      - G
      """))
    self.setUpParsing(
        dedent("""\
      capture_pattern_constants:
        kB:
          capture_type_with_pattern:
            output: B
            parts:
            - capture_type_with_pattern:
                output: C
                parts:
                - regex_fragment: C
                options:
                  separator: {regex_fragment: "_"}
            - capture_type_with_pattern:
                output: D
                parts:
                - regex_fragment: D
                options:
                  # TODO: This is not ideal: Both B and D end with a separator
                  # and we don't dedupe.
                  separator: {regex_fragment: ""}
        kE:
          capture_type_with_pattern:
            output: E
            parts:
            - capture_type_with_pattern:
                output: F
                parts:
                - regex_fragment: F
                options:
                  separator: {regex_fragment: "_"}
            - capture_type_with_pattern:
                output: G
                parts:
                - regex_fragment: G
        kA:
          capture_type_with_pattern:
            output: A
            parts:
            - capture_reference: kB
            - capture_reference: kE
      capture_patterns:
        A:
          capture_reference: kA
      """))
    result = self.parsing_engine.capture_patterns['A'].evaluate(
        "C_D F_G", self.parsing_engine)
    self.assertEqual(
        {
            'A': 'C_D F_G',
            'B': 'C_D',
            'C': 'C',
            'D': 'D',
            'E': 'F_G',
            'F': 'F',
            'G': 'G'
        }, result)

    self.setUpCountryParsing("XX", "")
    result = self.parsing_engine.capture_patterns['A'].evaluate(
        "C_D F_G", self.parsing_engine)
    self.assertEqual({'A': 'C_D F_G', 'B': 'C_D', 'E': 'F_G', 'F': 'F'}, result)


if __name__ == '__main__':
  unittest.main()
