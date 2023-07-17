import unittest

from renderer import Renderer
from unittest.mock import patch, mock_open
from modules.model import ParseGlobalModelModule
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

  def setUpModel(self, model_file_content):
    with patch("builtins.open", new_callable=OpenMock) as mock:
      mock.file_content = model_file_content
      ParseGlobalModelModule().observe_file(Path(GLOBAL_MODEL_FILENAME),
                                            self.renderer)

  def setUpParsing(self, file_content):
    self.parsing = ParsingModule()
    with patch("builtins.open", new_callable=OpenMock) as mock:
      mock.file_content = file_content
      self.parsing.observe_file(Path(GLOBAL_PARSING_FILENAME), self.renderer)
      self.parsing_engine = self.renderer.country_data['global'][
          'ParsingEngine']

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

        capture_pattnern_constants:
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
    self.assertEqual(result.to_regex(self.parsing_engine), "(?:ab(?:sep)+)?")

    result = self.parsing_engine.capture_patterns_constants.get(
        'kCaptureTypeWithPattern')
    self.assertIsNotNone(result)
    self.assertEqual(result.to_regex(self.parsing_engine),
                     "(?i:(?P<B>ab(?:ab(?:sep)+)?)(?:,|\s+|$)+)")

  def test_parsing_capture_cascade(self):
    self.setUpModel(dedent(DEFAULT_GLOBAL_MODEL))
    # Test that a named rule is resolved.
    self.setUpParsing(
        dedent("""\
        regex_constants:
          kFragment:
            regex_fragment: ab

        capture_pattnern_constants:
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


if __name__ == '__main__':
  unittest.main()
