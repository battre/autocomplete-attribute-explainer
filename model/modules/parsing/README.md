# Parsing engine

This module deals with the problem of parsing an address like
```
Avenida Mem de Sá, 1234
apto 12
1 andar
referência: foo
```
into structurd information:
```yaml
street: "Avenida Mem de Sá"
building: "1234"
unit: "apto 12"
unit-type: "apto"
unit-name: "12"
floor: "1"
landmark: "foo"
```

The following sections explain the components to parse addresses bottom up.

# Regular expression components

Regular expression components are the building blocks of address parsing.

## Syntax
```
regex_fragment: str
regex_reference: str
regex_concat:
  parts: List<regex_component>
  wrap_non_capture: bool = True
```
## Typedefs
```
regex_component = regex_fragment | regex_reference | regex_concat
```

## Explanation

A `regex_fragment` is the smallest building block and basically just a string.

`regex_fragment`s can be inlined or stored in a lookup-map (which is defiend in
the `regex_definitions` section of a rules file). To lookup an entry, you can
use a `regex_reference`, which takes the identifier as a parameter.

Regular expressions can also be built by concatenating
fragments or references using the `regex_concat` component which consists of a
list of `regex_component`s. By default the concatenation is wrapped in `(?:` and
`)` unless that is disabled via `wrap_non_capture: false`.

All regular expressions assume the availability of capture groups and multi-line
mode, where `^` and `$` match the beginning and end of a line, not of the input.

The value of `kFooAndFooRe` would be `(?:foo\s+foo)`.

## Examples:
```yaml
regex_definitions:
  kFooRe: {regex_fragment: 'foo'}
  kSeparator: {regex_fragment: '\s+'}
  kFooAndFooRe:
    regex_concat:
    - regex_reference: kFoo
    - regex_reference: kSeparator
    - regex_reference: kFoo
```

# Captures

Captures are primarily a mechanism to capture specific information out of a
string and bind it to a capture group (which corresponds to a field type, i.e.
the output of parsing).

## Syntax
```
match_quantifier: MATCH_REQUIRED | MATCH_OPTIONAL | MATCH_LAZY_OPTIONAL
capture:
  output: type_name
  [temp_output: str]
  [prefix: regex_component]
  parts: List<capture_or_regex_component>
  [suffix: regex_component]
  [match_quantifier]
capture_reference: str
separator: regex_component = regex_fragment("^|\s+|\s*,\s*")
no_capture:
  parts: List<capture_or_regex_component>
  [match_quantifier]
```
## Typedefs
```
capture_component = capture_reference | capture | no_capture | separator
capture_or_regex_component = capture_component | regex_component
capture_sequence = List<capture_component>
```

## Explanation

The purpose of the capture component is to bind a part of string to a field
type. Imagine you want to extract the `5` out of `floor: 5` and assign it
autocomplete field type `floor`. You could phrase this as

```yaml
capture:
  # This is the field type and the output if the capture matches a string.
  output: floor
  # This is a required prefix before the floor number. It needs to exist but
  # won't be produced as output.
  prefix: { regex_fragment: 'floor:\s*' }
  # This is now the the regular expression that needs to be matched after the
  # floor prefix. If a match is found, the matching substring it bound to the
  # output 'floor'.
  parts:
  - regex_fragment: '\d+'
  - regex_fragment: '|'
  - regex_fragment: 'underground'
```

Capture groups may have a `prefix` and/or `suffix`. These are regular
expressions that need to match the input before the actual content (`parts`) of
the regular expression matches.

Captures are powerful in that they can be built recursively and chained.

A capture group may be built recursively by stating that a `unit` consists of
a `unit-type` and a `unit-name` separated by whitespace:
```yaml
capture:
  output: unit
  parts:
  - capture:
      output: unit-type
      parts: [ {regex_fragment: 'apartment|apt\.?|suite'} ]
  - separator: {regex_fragment: '\s+'}
  - capture:
      output: unit-name
      parts: [ {regex_reference: '\d+'} ]
```

In this case the string matching `(apartment|apt\.?|suite)\s+\d+` is assigned
to the output `unit`, the string matching `(apartment|apt\.?|suite)` is assigned
to the output `unit-type`, and the string matching `\d+` is assigned to the
output `unit-name`.

It is possible to make a capture optional:
```yaml
capture:
  output: unit
  parts:
  - capture:
      output: unit-type
      parts: [ {regex_fragment: 'apartment|apt\.?|suite'} ]
      match_quantifier: MATCH_OPTIONAL  # <----
  - separator: {regex_fragment: '\s+'}
  - capture:
      output: unit-name
      parts: [ {regex_reference: '\d+'} ]
```

Now, both `apartment 5` and `5` would match. In the latter case we would get
`{unit: '5', unit-type: '', unit-name: '5'}`.

A capture may contain more separtors and captures and deeper recursion:
```yaml
capture:
  output: unit-and-floor
  parts:
    - capture:
      output: unit
      parts:
      - capture:
          output: unit-type
          parts: [ {regex_fragment: 'apartment|apt\.?|suite'} ]
          match_quantifier: MATCH_OPTIONAL
      - separator: {regex_fragment: '\s+'}
      - capture:
          output: unit-name
          parts: [ {regex_reference: '\d+'} ]
    - separator: {regex_fragment: '-'}
    - capture:
      output: floor
      parts:
      - regex_fragment: '\d+'
      match_quantifier: MATCH_OPTIONAL
```

This examples illustrates how separators are bound to the following capture
group: The `floor` is optional and we end up building a regex similar to
`(?:-(?P<floor>\d+))?` with the following structure:
```
(?:-(?P<floor>\d+))?
                   ^ The entire capture is optional
    ^^^^^^^^^^^^^^ This captures the floor number
   ^ This is the separator and is part of the optional regex, so only if a floor
     numbe ris present we expect to see the '-' separator.
```

The takeaway here is that `seperator`s are bound to the capture that follows
them. They are only expected to occur if the thier bound capture exists in the
input.

`no_capture` groups exist to support the `match_quantifier` without having to
bind the match to an output. They are also useful for nestig captures.

Captures may be defined in `capture_definitions` and referenced via
`capture_reference`, analogously to regular expressions.

Finally there is the `temp_output` attribute of a `capture`. The purpose of this
is the following: Captures are mapped into regular expressions and these may not
contain duplicate capture groups (e.g. `(?P<Foo>\w+)|(?P<Foo>\d+)` would be
illegal because it contains the same capture group `Foo` twice). To work around
this we can define a `temp_output` which needs to be unique in the final regular
expression. But what ever is captured is mapped to `output`. If multiple
`temp_output` captures are matched and mapped to the same `output` the result is
undefined.

# Parsing

The parsing is the final layer of abstraction, which tells the browser which
rules to apply on certain inputs, e.g. how to parse an `in-building-location`
into components.

There are two fundamental strategies:
* `decomposition` means taking an entire string and splitting it into pieces
* `extract_parts` means taking a string and extracting substrings from arbitrary
  locations, e.g. before or after the literal `floor`.

## Syntax
```
decomposition:
  capture: capture | capture_reference: capture_reference
  [anchor_beginning: bool = True]
  [anchor_end: bool = True]
decomposition_cascade:
  [condition: regex_component]
  alternatives: capture_sequence | decomposition_cascade
extract_part:
  [condition: regex_component]
  capture: capture | capture_reference
extract_parts:
  extract_part: List<extract_part>
parsing_component = decomposition | decomposition_cascade |
```

## Explanation

A `decomposition` tries to match an entire string (unless `anchor_beginning` or
`anchor_end` create exceptions). It can contain either a single `capture` or a
single `capture_reference`.

Decompositions are embedded in `parsing_definitions` and instruct the browser
how to process observed data. So for example, if the browser has seen a
`street-location` field, the following parsing definition can indicate which
capture to use to process it:
```yaml
parsing_definitions:
  street-location:
    decomposition:
      capture_reference: ParseStreetLocation
```

A `decomposition_cascade` enables us to try one alternative after the next
until we have found a match. It can even be fitted with a condition to only
use it in case the condition is fulfilled. Here is a complex case that is used
for parsing names:
```yaml
parsing_definitions:
  name:
    decomposition_cascade:
      alternatives:
      - decomposition_cascade:
          condition:
            regex_reference: kHasCjkNameCharacteristics
          alternatives:
          - decomposition: {capture_reference: ParseSeparatedCjkNameExpression}
          - decomposition: {capture_reference: ParseKoreanTwoCharacterLastNameExpression}
          - decomposition: {capture_reference: ParseCommonCjkTwoCharacterLastNameExpression}
          - decomposition: {capture_reference: ParseCjkSingleCharacterLastNameExpression}
      - decomposition_cascade:
          condition:
            regex_reference: kHasHispanicLatinxNameCharacteristics
          alternatives:
          - decomposition: {capture_reference: ParseHispanicFullNameExpression}
      - decomposition_cascade:
          # No condition, this is the fallback.
          alternatives:
          - decomposition: {capture_reference: ParseOnlyLastNameExpression}
          - decomposition: {capture_reference: ParseLastCommaFirstMiddleNameExpression}
          - decomposition: {capture_reference: ParseFirstMiddleLastNameExpression}
```
If the regex `kHasCjkNameCharacteristics` matches the input, four different ways
of decompositioning the input are attempted. If neither of those generated a
match, the next cascade for hispanic/latinx names is attempted.

An alternative strategy is to rely on `extract_parts`. For example a street
address is inherently complex to parse because apartments, floors, doors, etc.
can be presented in arbitrary order. `extract_parts` can help looking for
keywords (e.g. "floor") and adjacent information (e.g. the floor number). Unlike
for a `decomposition_cascade`, `extract_parts` does not follow the "the first
match wins" principle but applies all matching attempts in a row.

Here is an example:
```yaml
parsing_definitions:
  street-address-alternative-1:
    extract_parts:
      parts:
      - extract_part:
          # This field has an implicit anchoring to the beginning of the
          # input. So we will not apply the regex in the middle of the text.
          capture_reference: ParseStreetLocation
      - extract_part:
          capture_reference: ParseUnitWithMandatoryUnitType
      - extract_part:
          capture_reference: ParseFloorWithMandatoryPrefix
      - extract_part:
          capture_reference: ParseFloorWithMandatorySuffix
      - extract_part:
          capture_reference: ParseLandmarkWithMandatoryPrefix
```

Here, `ParseUnitWithMandatoryUnitType` may be defined as follows:
```yaml
capture_definitions:
  ParseUnitWithMandatoryUnitType:
    capture:
      output: unit
      parts:
      - capture:
          output: unit-type
          parts: [ {regex_fragment: 'apartment|apt\.?|suite'} ]
      - separator: {regex_fragment: '\s+'}
      - capture:
          output: unit-name
          parts: [ {regex_reference: '\d+'} ]
```

Note how this can match at any point in the input stirng but it requires the
discovery of a `unit-type`.

# Top-level syntax

As indicated above, a rules file is structured into three sections with
dictionaries:

```
regex_definitions: name -> regex_component
capture_definitions: name -> capture_component
parsing_definitions: type_name -> parsing_component
```

# Gotchas for multi-line inputs:

Assume multi-line semantics (i.e. '(?m)' is prefixed to the query). This means
that '^' and '$' match the beginning/end of lines, not of the entire input. If
you want to anchor to the beginning of the input, you need to use `\A`.

Note that something like `[^,]+` consumes characters beyond new lines. You can
use `[^,\n]+` if you want to end at line-ends.

# Naming conventions:

**Regular expressions** (defined in `regex_definitions`) are labeled as
constants: `kCamelCase`. Regular expressions that match a value (e.g. a house
number like 5) end in `ValueRe` while regular expressions that match a string
(e.g. "floor", not the floor number) end in `LiteralRe`.

**Captures** (defined in `capture_definitions`) are follow function style naming
and start with `Parse`. E.g. `ParseStreetLocation`.
