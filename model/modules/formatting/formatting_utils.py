from renderer import Renderer
from modules.model.model import Model, AtomicToken
from typing import Optional, List, Set, Union


def collect_details_for_formatting(country: str, token_id: str,
                                   renderer: Renderer) -> Optional[dict]:
  model = renderer.get_model(country)

  token = model.find_token(token_id)
  if not token or token.is_atomic_token():
    return None

  named_formatting_rules = (renderer.country_data[country].get(
      'named-formatting-rules', {}))
  formatting_rules = (renderer.country_data[country].get(
      'formatting-rules', {}))

  # We think of a formatting rule as `output = function(inputs)`, so the
  # inputs below are the tokens that feed into the formatted output.
  FLAG_MISSING_RULES = False
  if FLAG_MISSING_RULES:
    inputs = formatting_rules.get(token_id, [])
  else:
    inputs = formatting_rules.get(token_id, None)
    if not inputs:
      return None

  errors = []

  # A special case is references to named formatting rules. Only one reference
  # may exist per rule.
  while len(inputs) == 1 and 'reference' in inputs[0]:
    rule = named_formatting_rules.get(inputs[0]['reference'], None)
    if rule:
      inputs = rule.get(token_id, None)
    else:
      errors += [f"No named-rule {inputs[0]['reference']} found"]
      inputs = []

  for input in inputs:
    if 'reference' in input:
      errors += [f"A rule for {token_id} had more than one reference"]
      inputs = []
      break

  if not errors:
    errors += validate(token_id, inputs, model)
  if errors:
    print(f"Formatting errors for {token_id}: {errors}")
    print(model.find_token(token_id))

  return {
      'model': model,
      'token_id': token_id,
      'inputs': inputs,
      'errors': errors,
      'named_formatting_rules': named_formatting_rules,
      'formatting_rules': formatting_rules,
  }


def validate(token_id: str, inputs: List[dict], model: Model) -> List[str]:
  """Returns a list of errors to be shown when validating the formatting rule."""

  # Ignore tokens that don't exist in the model.
  token = model.find_token(token_id)
  if not token:
    return []

  if token.is_atomic_token() and inputs:
    return ["You cannot provide rules for atomic tokens"]

  # Children of the token in the model.
  assert not isinstance(token, AtomicToken)
  children_of_token = set(token.children)
  # Tokens that are used during formatting or explicitly skipped.
  input_tokens = set([t['token'] for t in inputs if 'token' in t])
  input_tokens = input_tokens.union(
      set([t['skip'] for t in inputs if 'skip' in t]))

  errors = []
  for t in input_tokens - children_of_token:
    # If an input token is not a direct child, it needs to be a desendant.
    if not is_descendant_of(t, token_id, model):
      errors.append(
          f"'{t}' exists in the rule but is not a descendant of '{token_id}' in the model."
      )

  for t in children_of_token - input_tokens:
    # If a child is missing all children of that child need to be in the
    # formatting rule.
    if not token_id_or_all_children_in_input_tokens(t, input_tokens, model):
      errors.append(
          f"'{t}' is a child of {token_id} but does not get produced.")

  return errors


def is_descendant_of(descendant_id: str, ancestor_id: str, model: Model):
  """Returns if descendant_id is a descendant of ancestor_id.

  If descendant_id == ancestor_id, that's considered a 'yes'.
  """
  ancestor = model.find_token(ancestor_id)
  if not ancestor or ancestor.is_atomic_token():
    return False
  assert not isinstance(ancestor, AtomicToken)
  return descendant_id in [t.id for t in ancestor.pre_order()]


def token_id_or_all_children_in_input_tokens(token_id: str,
                                             input_token_id: Union[List[str],
                                                                   Set[str]],
                                             model: Model):
  """Returns if token_id is in input_token_id or all children of token_id are.

    input_token_id is a list of token_ids of a formatting expression. This
    function verifies that no token is forgotten in the formatting.
    """
  if token_id in input_token_id:
    return True

  token = model.find_token(token_id)

  if token and not token.is_atomic_token():
    assert not isinstance(token, AtomicToken)
    if not token.children:
      return False
    for child in token.children:
      if not token_id_or_all_children_in_input_tokens(child, input_token_id,
                                                      model):
        return False
    return True

  return False
