# Regular expression components
## Classes
```
regex_fragment: str
regex_reference: str
regex_concat: {parts: List<regex_component>, wrap_non_capture: bool = True}
```
## Typedefs
```
regex_component = regex_fragment | regex_reference | regex_concat
```

# Captures
## Classes
```
match_quantifier: MATCH_REQUIRED | MATCH_OPTIONAL | MATCH_LAZY_OPTIONAL
capture_reference: str
separator: regex_component = regex_fragment("^|\s+|\s*,\s*")
capture: {
  output: type_name,
  [prefix: regex_component],
  parts: capture_sequence,
  [suffix: regex_component],
  [match_quantifier]
}
capture_alternatives: {
  output: type_name,
  alternatives: capture,
  priority_list: [type_name]
}
no_capture: { parts: capture_sequence, [match_quantifier] }
```
## Typedefs
```
capture_component = capture_reference | capture | no_capture | separator
capture_or_regex_component = capture_component | regex_component
capture_sequence = List<capture_component>
```

# Parsing
```
decomposition: { capture: capture | capture_reference: capture_reference, [anchor_beginning: bool = True], [anchor_end: bool = True] }
decomposition_cascade: { [condition: regex_component], alternatives: capture_sequence | decomposition_cascade}
extract_part: { [condition: regex_component], capture: capture | capture_reference }
extract_parts: [extract_part]
parsing_component = decomposition | decomposition_cascade |
```

# Top-level
```
regex_definitions: name -> regex_component
capture_definitions: name -> capture_component
parsing_definitions: type_name -> parsing_component
```