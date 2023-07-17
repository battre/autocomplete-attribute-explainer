# Parsing field contents

This module deals with understanding the contents of fields, e.g. with
heuristics to take a full name and split it into a given name, middle name,
family name, or even a first and second family name.

The process of **parsing** is taking a value and breaking it into smaller
pieces.

This operation is inherently difficult and we operate under the assumption that
we don't have to get it right: If a user submits a full name, we make an
educated guess at determinig the given and family name for the next time the
user tries to fill a form with a given and family name field. But if we got it
wrong, we will learn from this attempt and override the previousy assumed
values.

The grammar looks as follows:

## regex_constants

regex_constants are mechanism to define regular expressions named concepts,
which can be reused, composited and overridden by country specific constants.

### Syntax:
```yaml
# optional
regex_constants:
  "regex_constant name":
    # A "regex_component",
    # one of the regex_fragment, regex_reference, regex_concat

    # A regular expression or a part of a regular expression.
    regex_fragment:
      "fragment of a regular expression, e.g. 'a.*b'."

    # Lookup of a named regex_constants for reuse and composition. This
    # evaluates to the contents of the named regex_constant.
    regex_reference:
      "regex_constant name"

    # Concatenation of several regular expressions.
    regex_concat:
      parts:
      # list of regex_fragment, regex_reference and regex_concat items.
      - regex_fragment: ...
      - regex_reference: ...
      - regex_concat: ...
      # optional
      options:
        # Wraps the concatenation of a regular expression in (?: ) to make it
        # a non-capture group.
        # optional
        wrap_non_catpure: true/false (Default: true)
```

### Example:
```yaml
regex_constants:
  kSingleWordRe:
    regex_fragment: |-
      (?:[^\s,]+)
  kTwoWordsRe:
    regex_concat:
      parts:
        - regex_reference: kSingleWordRe
        - regex_fragment: \s+
        - regex_reference: kSingleWordRe
```

## Capture groups

Capture patterns are a higher level concept that is built on top of regular
expressions. They can be parameterized for eager and lazy matching and used to
capture different parts of a string in a dictionary.

The purpose of capture_pattnern_constants is to create named entities that can
be referenced, reused and overriden by country specific rules.

### Syntax for `capture_pattnern_constants`
```yaml
# optional
capture_pattnern_constants:
  "capture_pattnern_constants name:"
    # one of capture_reference, no_capture_pattern or capture_type_with_pattern.

    # Creates an alias for a capture_pattnern_constants.
    capture_reference:
      "capture_pattnern_constants name"

    capture_type_with_pattern:
      # The type that will be captured from this capture pattern, e.g.
      # "given-name".
      output: "field_type name"
      parts:
        # A list of the following types that are matched in sequence.
        - regex_fragment: ...
        - regex_reference: ...
        - regex_concat: ...
        - capture_reference: ...
        - no_capture_pattern: ...
        - capture_type_with_pattern: ...
      # optional
      options:
        # Specifies the eagerness of matching the capture pattern.
        # - MATCH_REQUIRED (default): The capture group is required.
        # - MATCH_OPTIONAL: The capture group is optional.
        # - MATCH_LAZY_OPTIONAL: The capture group is lazy optional meaning that
        #   it is avoided if an overall match is possible.
        # optional:
        quantifier: MATCH_REQUIRED | MATCH_OPTIONAL | MATCH_LAZY_OPTIONAL
        # Specifies the separator that *follows* this field. Default: ",|\s+|$"
        # optional
        separator: regex_component

    # Captures a substring without storing it.
    no_capture_pattern:
      pattern: regex_component  # See regex_constants above.
      # optional
      options:
        # See capture_type_with_pattern above.
```

### Syntax for `capture_patterns`

```yaml
# optional
capture_patterns:
  "field_type name":
    # on of capture_reference, capture_type_with_pattern,
    # capture_type_with_pattern_cascade

    # See above. Note that this MUST refer to a capture_type_with_pattern
    # (or to another capture_reference that resovles to a
    # capture_type_with_pattern)
    capture_reference:
      "capture_pattnern_constants name"

    # See above. Note that the output MUST match the "field_type name" of this
    # capture pattern.
    capture_type_with_pattern:
      ...

    # A sequence of capture patterns. If `condition` matches the current string
    # the `patterns` are matched one after another. The first pattern that
    # returns a non-empty result terminates the process and defined the final
    # result.
    capture_type_with_pattern_cascade:
      output: "field_type name"
      condition: regex_component
      patterns:
      - capture_reference: ...
      - capture_type_with_pattern: ...
      - capture_type_with_pattern_cascade: ...
```

## Tests for `capture_pattnern_constants`
These tests are executed with `python3 main.py`.

```yaml
# optional
test_capture_pattnern_constants:
# A list of tests, each with the following structure.
- id: "ID or description of the test (printed in case of failure)"
  capture_pattern_constant: "capture_pattnern_constants name"
  input: "Text matched by the capture pattern"
  # Dictionary with the captured output values.
  output:
    "capture group name": "value"
    ...
```

## Tests for `capture_patterns`
These tests are executed with `python3 main.py`.

```yaml
# optional
test_capture_patterns:
# A list of tests, each with the following structure.
- id: "ID or description of the test (printed in case of failure)"
  type: "field_type name"
  input: "Text matched by the capture pattern"
  # Dictionary with the captured output values.
  output:
    "field_type": "value"
    ...
```