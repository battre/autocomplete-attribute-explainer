import unittest

from renderer import Renderer
from unittest.mock import patch, mock_open
from modules.model import ParseGlobalModelModule
from modules.formatting import FormattingModule
from pathlib import Path
from textwrap import dedent

GLOBAL_MODEL_FILENAME = "test/global-model.yaml"
GLOBAL_FORMATTING_FILENAME = "test/global-formatting-rules.yaml"

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
    self.formatting_file_content = ""

  def __call__(self, *args, **kwargs):
    return mock_open(read_data=self.formatting_file_content)(*args, **kwargs)


class TestFormattingModule(unittest.TestCase):

  def setUp(self):
    self.renderer = Renderer()

  def setUpModel(self, model_file_content):
    with patch("builtins.open", new_callable=OpenMock) as mock:
      mock.formatting_file_content = model_file_content
      ParseGlobalModelModule().observe_file(Path(GLOBAL_MODEL_FILENAME),
                                            self.renderer)

  def setUpFormatting(self, formatting_file_content):
    self.formatting = FormattingModule()
    with patch("builtins.open", new_callable=OpenMock) as mock:
      mock.formatting_file_content = formatting_file_content
      self.formatting.observe_file(Path(GLOBAL_FORMATTING_FILENAME),
                                   self.renderer)

  def test_named_rules(self):
    # Test that a named rule is resolved.
    self.setUpModel(
        dedent("""\
      concepts:
      - A:
        - B
      """))
    self.setUpFormatting(
        dedent("""\
      named-formatting-rules:
        rule-name:
          A:
          - B
      formatting-rules:
        A:
        - reference: "rule-name"
      """))
    result = self.formatting.collect_details_for_formatting(
        "global", "A", self.renderer)
    self.assertEqual(result["inputs"], [{"token": "B"}])

    # Expect an error if a named rule does not exist.
    self.setUpFormatting(
        dedent("""\
      formatting-rules:
        A:
        - reference: "rule-name"
      """))
    result = self.formatting.collect_details_for_formatting(
        "global", "A", self.renderer)
    self.assertNotEqual(result["errors"], [])

    # Verify that a rule can have only one reference
    self.setUpFormatting(
        dedent("""\
      named-formatting-rules:
        rule-name:
          A:
          - B
      formatting-rules:
        A:
        - reference: "rule-name"
        - reference: "rule-name"
      """))
    result = self.formatting.collect_details_for_formatting(
        "global", "A", self.renderer)
    self.assertNotEqual(result["errors"], [])

  def test_validate(self):
    self.setUpModel(DEFAULT_GLOBAL_MODEL)

    # Default case, a rule consists of its descendants.
    self.setUpFormatting(
        dedent("""\
      formatting-rules:
        A:
        - B
        - separator: ", "
        - E
      """))
    result = self.formatting.collect_details_for_formatting(
        "global", "A", self.renderer)
    self.assertEqual(result["errors"], [])

    # A rule replaces a token (B) with that token's descendants (D, E).
    self.setUpFormatting(
        dedent("""\
      formatting-rules:
        A:
        - C
        - D
        - E
      """))
    result = self.formatting.collect_details_for_formatting(
        "global", "A", self.renderer)
    self.assertEqual(result["errors"], [])

    # It's a bug if a token (B) is only replaced with a subset of the
    # descendants.
    self.setUpFormatting(
        dedent("""\
      formatting-rules:
        A:
        - C
        - E
      """))
    result = self.formatting.collect_details_for_formatting(
        "global", "A", self.renderer)
    self.assertNotEqual(result["errors"], [])

    # It's a bug if a token (B) has an input that is not a member of the
    # descendants.
    self.setUpFormatting(
        dedent("""\
      formatting-rules:
        A:
        - B
        - E
        - F
      """))
    result = self.formatting.collect_details_for_formatting(
        "global", "A", self.renderer)
    self.assertNotEqual(result["errors"], [])

  def test_formatting(self):
    self.setUpModel(
        dedent("""\
      concepts:
      - A:
        - B:
          - C
          - D
        - E
      """))

    self.setUpFormatting(
        dedent("""\
      formatting-rules:
        A:
        - B
        # Default separator of ' ' applies here
        - E

        B:
        - prefix: "prefixC "
        - C
        - suffix: " suffixC"
        - separator: "\\n"
        - prefix: "prefixD "
        - D
        - suffix: " suffixD"
      """))
    errors = []
    result = self.formatting.apply_formatting(country="global",
                                              token_id="A",
                                              data={
                                                  "C": "C",
                                                  "D": "D",
                                                  "E": "E"
                                              },
                                              renderer=self.renderer,
                                              errors=errors)
    self.assertEqual(errors, [])
    self.assertEqual(result, "prefixC C suffixC\nprefixD D suffixD E")

    # If "C" is empty, neither prfix nor suffix nor separator should be printed.
    result = self.formatting.apply_formatting(country="global",
                                              token_id="A",
                                              data={
                                                  "D": "D",
                                                  "E": "E"
                                              },
                                              renderer=self.renderer,
                                              errors=errors)
    self.assertEqual(errors, [])
    self.assertEqual(result, "prefixD D suffixD E")

    # If only "C" is non-empty, the prefix, value and suffix should be printed
    # but nothing else.
    result = self.formatting.apply_formatting(country="global",
                                              token_id="A",
                                              data={
                                                  "C": "C",
                                              },
                                              renderer=self.renderer,
                                              errors=errors)
    self.assertEqual(errors, [])
    self.assertEqual(result, "prefixC C suffixC")


if __name__ == '__main__':
  unittest.main()
