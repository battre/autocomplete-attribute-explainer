import unittest

from renderer import Renderer
from modules.parsing import (RegexFragment, RegexReference, RegexConcat,
                             Separator, Capture, Decomposition,
                             DecompositionCascade, ExtractPart, ExtractParts,
                             ParsingEngine, CaptureMapper)
from modules.model import Model
from schema import Schema, SchemaError
from ruamel.yaml import YAML
from textwrap import dedent

###### Tests of RegexComponent


class TestRegexFragment(unittest.TestCase):

  def setUp(self):
    self.renderer = Renderer()
    self.engine = ParsingEngine()
    self.model = Model()

  def test_creation(self):
    yaml = {'regex_fragment': 'foobar'}

    schema = Schema(RegexFragment.schema())
    schema.validate(yaml)

    regex = RegexFragment.from_yaml_dict(yaml)
    self.assertIsNotNone(regex)
    self.assertEqual('foobar', regex.to_regex(self.engine, CaptureMapper()))

    # Verify that newlines are stripped at the end
    yaml = YAML(typ='safe').load(
      'regex_fragment: |-\n' + \
      '  foo\n' + \
      '  bar\n'
    )

    schema = Schema(RegexFragment.schema())
    schema.validate(yaml)

    regex = RegexFragment.from_yaml_dict(yaml)
    self.assertIsNotNone(regex)
    self.assertEqual('foobar', regex.to_regex(self.engine, CaptureMapper()))

  def test_validate(self):
    # Ensure that a valid expression produces no errors.
    errors = []
    regex = RegexFragment.from_yaml_dict({'regex_fragment': 'a+'})
    self.assertIsNotNone(regex)
    regex.validate(self.engine, self.model, errors)
    self.assertEqual([], errors)

    # Ensure that an invalid expression produces errors.
    errors = []
    regex = RegexFragment.from_yaml_dict({'regex_fragment': '+'})
    self.assertIsNotNone(regex)
    regex.validate(self.engine, self.model, errors)
    self.assertNotEqual([], errors)


class TestRegexReference(unittest.TestCase):

  def setUp(self):
    self.renderer = Renderer()
    self.engine = ParsingEngine()
    self.engine.regex_definitions['definition'] = \
        RegexFragment.from_yaml_dict({'regex_fragment': 'foobar'})
    self.model = Model()

  def test_creation(self):
    yaml1 = {'regex_reference': 'definition'}

    schema = Schema(RegexReference.schema())
    schema.validate(yaml1)

    # Verify that to_regex resolves to the original fragment
    ref = RegexReference.from_yaml_dict(yaml1)
    self.assertIsNotNone(ref)
    self.assertEqual('foobar', ref.to_regex(self.engine, CaptureMapper()))

    self.engine.regex_definitions['ref1'] = ref

    # Verify that resolution works multiple steps
    yaml2 = {'regex_reference': 'ref1'}
    ref2 = RegexReference.from_yaml_dict(yaml2)
    self.assertIsNotNone(ref2)
    self.assertEqual('foobar', ref2.to_regex(self.engine, CaptureMapper()))

  def test_validate(self):
    # Ensure that a valid expression produces no errors.
    errors = []
    ref = RegexReference.from_yaml_dict({'regex_reference': 'definition'})
    self.assertIsNotNone(ref)
    ref.validate(self.engine, self.model, errors)
    self.assertEqual([], errors)

    # Ensure that an invalid expression produces errors.
    errors = []
    ref = RegexReference.from_yaml_dict({'regex_reference': 'undefined'})
    self.assertIsNotNone(ref)
    ref.validate(self.engine, self.model, errors)
    self.assertNotEqual([], errors)

    # Ensure that a reference to an invalid item produces errors.
    self.engine.regex_definitions['invalid'] = \
        RegexFragment.from_yaml_dict({'regex_fragment': '+'})
    errors = []
    ref = RegexReference.from_yaml_dict({'regex_reference': 'invalid'})
    self.assertIsNotNone(ref)
    ref.validate(self.engine, self.model, errors)
    self.assertNotEqual([], errors)


class TestRegexConcat(unittest.TestCase):

  def setUp(self):
    self.renderer = Renderer()
    self.engine = ParsingEngine()
    self.engine.regex_definitions['definition'] = \
        RegexFragment.from_yaml_dict({'regex_fragment': 'foobar'})
    self.model = Model()

  def test_creation(self):
    yaml = YAML(typ='safe').load(
        dedent("""\
        regex_concat:
          parts:
          - regex_fragment: 'fragment1'
          - regex_reference: 'definition'
          # And recursion...
          - regex_concat:
              parts:
              - regex_fragment: 'A'
              - regex_fragment: 'B'
              wrap_non_capture: False
        """))

    schema = Schema(RegexConcat.schema())
    schema.validate(yaml)

    concat = RegexConcat.from_yaml_dict(yaml)
    self.assertIsNotNone(concat)

    self.assertEqual('(?:fragment1foobarAB)',
                     concat.to_regex(self.engine, CaptureMapper()))

  def test_validate(self):
    # Ensure that a valid expression produces no errors.
    yaml = YAML(typ='safe').load(
        dedent("""\
        regex_concat:
          parts:
          - regex_fragment: 'fragment1'
          - regex_reference: 'definition'
          # And recursion...
          - regex_concat:
              parts:
              - regex_fragment: 'A'
              - regex_fragment: 'B'
              wrap_non_capture: false
        """))
    errors = []
    ref = RegexConcat.from_yaml_dict(yaml)
    self.assertIsNotNone(ref)
    ref.validate(self.engine, self.model, errors)
    self.assertEqual([], errors)


###### Tests of CaptureComponent


class TestSeparator(unittest.TestCase):

  def setUp(self):
    self.renderer = Renderer()
    self.engine = ParsingEngine()
    self.model = Model()

  def test_creation(self):
    yaml = {'separator': {'regex_fragment': 'foobar'}}

    schema = Schema(Separator.schema())
    schema.validate(yaml)

    regex = Separator.from_yaml_dict(yaml)
    self.assertIsNotNone(regex)
    self.assertEqual('foobar', regex.to_regex(self.engine, CaptureMapper()))

    errors = []
    regex.validate(self.engine, self.model, errors)
    self.assertEqual([], errors)


class TestCapture(unittest.TestCase):

  def setUp(self):
    self.renderer = Renderer()
    self.engine = ParsingEngine()

  def test_creation(self):
    yaml = YAML(typ='safe').load(
        dedent("""\
        capture:
          output: 'out-put'
          prefix: { regex_fragment: 'prefix' }
          parts:
          - capture:
              output: 'o1'
              prefix: { regex_fragment: 'p1' }
              parts:
              - regex_fragment: '\w+'
              suffix: { regex_fragment: 's1' }
          - separator:
              regex_fragment: '\s+sep1\s+'
          - capture:
              output: 'o2'
              prefix: { regex_fragment: 'p2' }
              parts:
              - regex_fragment: '\w+'
              suffix: { regex_fragment: 's2' }
              quantifier: MATCH_OPTIONAL
          - separator:
              regex_fragment: '\s+sep2\s+'
          - capture:
              output: 'o3'
              parts:
              - regex_fragment: '\w+'
              quantifier: MATCH_LAZY_OPTIONAL
          suffix: { regex_fragment: 'suffix' }
        """))

    schema = Schema(Capture.schema_capture())
    schema.validate(yaml)

    regex = Capture.from_yaml_dict(yaml)
    self.assertIsNotNone(regex)
    capture1 = '(?:p1(?P<o1>\w+)s1)'
    # Capture2 gets the preceding separator included and is optional.
    capture2 = '(?:\s+sep1\s+p2(?P<o2>\w+)s2)?'
    # Capture3 gets the preceding separator and is lazy optional.
    capture3 = '(?:\s+sep2\s+(?P<o3>\w+))??'
    # out-put becomes out_put
    expected = f"(?:prefix(?P<out_put>{capture1}{capture2}{capture3})suffix)"
    self.assertEqual(expected, regex.to_regex(None, self.engine,
                                              CaptureMapper()))
    inner_input = (
      ('p1' + 'foo' + 's1') + \
      ' sep1 ' + \
      ('p2' + 'bar' + 's2') + \
      ' sep2 ' + \
      ('' + 'baz' + '')
    )
    input = f"prefix{inner_input}suffix"
    result = regex.evaluate(input, self.engine, CaptureMapper())[0]
    expected = {
        'out-put': inner_input,
        'o1': 'foo',
        'o2': 'bar',
        'o3': 'baz',
    }
    self.assertEqual(expected, result)

  def test_no_capture_alternatives(self):
    yaml = YAML(typ='safe').load(
        dedent("""\
        capture:
          output: 'foo'
          prefix: { regex_fragment: 'prefix\s' }
          parts:
          - no_capture:
              alternatives:
              - capture:
                  output: 'bar'
                  parts:
                  - regex_fragment: 'a\d+'
              - capture:
                  output: 'bar'
                  parts:
                  - regex_fragment: '\d+a'
          suffix: { regex_fragment: '\ssuffix' }
        """))

    schema = Schema(Capture.schema_capture())
    schema.validate(yaml)

    regex = Capture.from_yaml_dict(yaml)
    self.assertIsNotNone(regex)
    capture1 = '(?P<bar>a\d+)'
    capture2 = '(?P<bar__2>\d+a)'
    no_capture = f"(?:{capture1}|{capture2})"
    expected = f"(?:prefix\s(?P<foo>{no_capture})\ssuffix)"
    self.assertEqual(expected, regex.to_regex(None, self.engine,
                                              CaptureMapper()))
    input = f"prefix 1a suffix"
    result = regex.evaluate(input, self.engine, CaptureMapper())[0]
    expected = {
        'foo': "1a",
        'bar': '1a',
    }
    self.assertEqual(expected, result)

    input = f"prefix a1 suffix"
    result = regex.evaluate(input, self.engine, CaptureMapper())[0]
    expected = {
        'foo': "a1",
        'bar': 'a1',
    }
    self.assertEqual(expected, result)


###### Tests of ParsingComponent


class TestDecomposition(unittest.TestCase):

  def setUp(self):
    self.renderer = Renderer()
    self.engine = ParsingEngine()

  def test_creation(self):
    yaml = YAML(typ='safe').load(
        dedent("""\
        decomposition:
          capture:
            output: foo
            parts: [ { regex_fragment: '\w+' } ]
        """))

    schema = Schema(Decomposition.schema())
    schema.validate(yaml)

    decomposition = Decomposition.from_yaml_dict(yaml)
    self.assertIsNotNone(decomposition)
    expected = "^(?P<foo>\w+)$"
    self.assertEqual(expected,
                     decomposition.to_regex(self.engine, CaptureMapper()))

    self.assertEqual({'foo': 'aaa'},
                     decomposition.evaluate('aaa', self.engine,
                                            CaptureMapper())[0])
    self.assertEqual({},
                     decomposition.evaluate('aaa aaa', self.engine,
                                            CaptureMapper())[0])

    # Test anchoring disabled.
    yaml = YAML(typ='safe').load(
        dedent("""\
        decomposition:
          capture:
            output: foo
            parts: [ { regex_fragment: '\w+' } ]
          anchor_beginning: false
          anchor_end: false
        """))

    schema = Schema(Decomposition.schema())
    schema.validate(yaml)

    decomposition = Decomposition.from_yaml_dict(yaml)
    self.assertIsNotNone(decomposition)
    expected = "(?P<foo>\w+)"
    self.assertEqual(expected,
                     decomposition.to_regex(self.engine, CaptureMapper()))

    self.assertEqual({'foo': 'aaa'},
                     decomposition.evaluate('aaa', self.engine,
                                            CaptureMapper())[0])
    self.assertEqual({'foo': 'aaa'},
                     decomposition.evaluate('aaa aaa', self.engine,
                                            CaptureMapper())[0])


class TestDecompositionCascade(unittest.TestCase):

  def setUp(self):
    self.renderer = Renderer()
    self.engine = ParsingEngine()

  def test_creation(self):
    yaml = YAML(typ='safe').load(
        dedent("""\
        decomposition_cascade:
          condition: { regex_fragment: '^1' }
          alternatives:
          - decomposition:
              capture:
                output: 'foo'
                parts: [ { regex_fragment: '.*a+' } ]
          - decomposition:
              capture:
                output: 'foo'
                parts: [ { regex_fragment: '.*b+' } ]
        """))

    schema = Schema(DecompositionCascade.schema())
    schema.validate(yaml)

    cascade = DecompositionCascade.from_yaml_dict(yaml)
    self.assertIsNotNone(cascade)

    # Note how this tests the capture mapper.
    expected = ["^(?P<foo>.*a+)$", "^(?P<foo__2>.*b+)$"]
    self.assertEqual(expected,
                     cascade.to_regex_list(self.engine, CaptureMapper()))

    self.assertEqual({'foo': '1aaa'},
                     cascade.evaluate('1aaa', self.engine, CaptureMapper())[0])
    self.assertEqual({'foo': '1bbb'},
                     cascade.evaluate('1bbb', self.engine, CaptureMapper())[0])
    # The condition (a "1" at the beginning is violated), therefore, we don't
    # return anything.
    self.assertEqual({},
                     cascade.evaluate('aaa', self.engine, CaptureMapper())[0])

    # Test nested cascades:
    yaml = YAML(typ='safe').load(
        dedent("""\
        decomposition_cascade:
          condition: { regex_fragment: '^1' }
          alternatives:
          - decomposition:
              capture:
                output: 'foo'
                parts: [ { regex_fragment: '.*a+' } ]
          - decomposition_cascade:
              condition: { regex_fragment: '2' }
              alternatives:
              - decomposition:
                  capture:
                    output: 'foo'
                    parts: [ { regex_fragment: '.*b+' } ]
        """))

    schema = Schema(DecompositionCascade.schema())
    schema.validate(yaml)

    cascade = DecompositionCascade.from_yaml_dict(yaml)
    self.assertIsNotNone(cascade)
    self.assertEqual({'foo': '1aaa'},
                     cascade.evaluate('1aaa', self.engine, CaptureMapper())[0])
    self.assertEqual({'foo': '12bbb'},
                     cascade.evaluate('12bbb', self.engine, CaptureMapper())[0])


class TestExtractPart(unittest.TestCase):

  def setUp(self):
    self.renderer = Renderer()
    self.engine = ParsingEngine()

  def test_creation(self):
    yaml = YAML(typ='safe').load(
        dedent("""\
        extract_part:
          condition: { regex_fragment: '^1' }
          capture:
            output: 'out-put'
            prefix: { regex_fragment: 'prefix' }
            parts:
              - regex_fragment: '[_a]+'
            suffix: { regex_fragment: 'suffix' }
        """))

    schema = Schema(ExtractPart.schema())
    schema.validate(yaml)

    extract_part = ExtractPart.from_yaml_dict(yaml)
    self.assertIsNotNone(extract_part)
    expected = '(?:prefix(?P<out_put>[_a]+)suffix)'
    self.assertEqual(expected,
                     extract_part.to_regex(self.engine, CaptureMapper()))
    self.assertEqual({'out-put': '_a_'},
                     extract_part.evaluate('1prefix_a_suffix', self.engine,
                                           CaptureMapper())[0])


class TestExtractParts(unittest.TestCase):

  def setUp(self):
    self.renderer = Renderer()
    self.engine = ParsingEngine()

  def test_creation(self):
    yaml = YAML(typ='safe').load(
        dedent("""\
        extract_parts:
          condition: { regex_fragment: '^1'}
          parts:
          - extract_part:
              capture:
                output: building
                prefix: { regex_fragment: 'house number\s+' }
                parts:
                  - regex_fragment: '\d+'
          - extract_part:
              capture:
                output: unit
                prefix: { regex_fragment: 'apartment\s+' }
                parts:
                  - regex_fragment: '\d+'
        """))

    schema = Schema(ExtractParts.schema())
    schema.validate(yaml)

    extract_parts = ExtractParts.from_yaml_dict(yaml)
    self.assertIsNotNone(extract_parts)
    self.assertEqual({
        'building': '1',
        'unit': '2'
    },
                     extract_parts.evaluate('1 house number 1 apartment 2',
                                            self.engine, CaptureMapper())[0])
