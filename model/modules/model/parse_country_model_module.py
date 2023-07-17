import copy
from modules.abstract_module import AbstractModule
from modules.model.model import Model, CompoundToken
from pathlib import Path
import re
from renderer import Renderer
from schema import Schema
import schema
from typing import Any, Set
from renderer import Renderer


class ParseCountryModelModule(AbstractModule):

  def schema(self):
    return Schema({
        schema.Optional("cut-off-tokens"): [str],
        schema.Optional("cut-off-children"): [str],
        schema.Optional("extra-definitions"): {
            str: [str]
        },
        schema.Optional("append-after"): {
            str: [str]
        },
    })

  def _apply_cut_offs(self, model: Model, yaml: Any) -> Set[str]:
    # Tokens that should be removed from the entrie tree:
    cut_off_tokens = set(yaml.get('cut-off-tokens', []))
    # Child tokens that should be removed
    cut_off_children = set(yaml.get('cut-off-children', []))

    # Create a copy of token ids to be resilient to deletions while
    # iterating.
    token_ids = [token.id for token in model.pre_order()]

    for token_id in token_ids:
      if not token_id in model.concepts:
        continue  # Already deleted
      token = model.concepts[token_id]

      if token.id in cut_off_children:
        assert not token.is_atomic_token()
        token.children = []

      if not token.is_atomic_token():
        if set(token.children) & cut_off_tokens:
          token.children = [
              c for c in token.children if c not in cut_off_tokens
          ]

      if token.id in cut_off_tokens:
        del model.concepts[token_id]

    token_ids_afterwards = [token.id for token in model.pre_order()]
    return set(token_ids) - set(token_ids_afterwards)

  def _add_extra_definitions(self, model: Model, yaml: Any) -> None:
    for id, children_ids in yaml.get('extra-definitions', {}).items():
      model.concepts[id] = CompoundToken(model, id, children_ids)

  def _apply_append_after(self, model: Model, yaml: Any) -> None:
    append_after = yaml.get('append-after', {})
    for anchor, nodes in append_after.items():
      for parent in model.pre_order():
        if parent.is_atomic_token():
          continue
        if anchor in parent.children:
          insert_idx = parent.children.index(anchor)
          parent.children = (parent.children[:insert_idx + 1] + nodes +
                             parent.children[insert_idx + 1:])

  def observe_file(self, path: Path, renderer: Renderer):
    match = re.fullmatch(r'(?P<country>..)-model\.yaml', path.name)
    if not match:
      return
    country = match.groupdict()['country']
    renderer.add_country(country)

    # It's guaranteed that the generic model has been loaded already.
    model = copy.deepcopy(renderer.country_data["global"]["model"])

    yaml = self.read_yaml(path)

    all_removed_tokens = self._apply_cut_offs(model, yaml)
    self._add_extra_definitions(model, yaml)
    self._apply_append_after(model, yaml)

    # Persist the cut-offs so that other modules can apply them as well.
    renderer.country_data[country]['cut-off-tokens'] = set(
        yaml.get('cut-off-tokens', []))
    renderer.country_data[country]['cut-off-children'] = set(
        yaml.get('cut-off-children', []))
    renderer.country_data[country]['all-removed-tokens'] = all_removed_tokens

    renderer.set_model(country, model)
