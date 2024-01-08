import copy
from modules.abstract_module import AbstractModule
from modules.model.model import Model, CompoundToken, AtomicToken
from pathlib import Path
import re
from renderer import Renderer
from schema import Schema
import schema
from typing import Any, Set, List
from renderer import Renderer


class ParseCountryModelModule(AbstractModule):

  def schema(self):
    return Schema({
        # List of tokens that are removed from the model.
        schema.Optional("cut-off-tokens"): [str],
        # List of tokenns whose children are removed from the mode.
        schema.Optional("cut-off-children"): [str],
        # New definitions or re-definitions (token_id -> list of children)
        schema.Optional("extra-definitions"): {
            str: [str]
        },
        # List of tokens to be appended after the key token.
        schema.Optional("append-after"): {
            str: [str]
        },
        # Similar to extra-definitions, this contains entries of (token_id ->
        # list of children), but these nodes are designated as synthesized
        # nodes. These are nodes that live outside the main hierarchy. They
        # don't have to be stored in the model. Instead their value be formatted
        # from their children. They are injected into the model at the position
        # of the lowest common ancestore of all children.
        schema.Optional("synthesized-nodes"): {
            str: [str]
        }
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
        assert not isinstance(parent, AtomicToken)
        if anchor in parent.children:
          insert_idx = parent.children.index(anchor)
          parent.children = (parent.children[:insert_idx + 1] + nodes +
                             parent.children[insert_idx + 1:])

  def _find_lowest_common_ancestor(self, model: Model,
                                   children: List[str]) -> str:
    """
    Returns the lowest common ancestor of all children in the model tree.

    Args:
      model: The model
      children: A list of token_ids from which we look for the lowest
         common ancestor.
    """

    # Store for each child in children a path from the root node to the child.
    # Each path is a list of token_ids. paths_to_node is a list of len(children)
    # such paths.
    paths_to_nodes = [
        model.find_path_to_node(child_id) for child_id in children
    ]

    # Remove the first entries from all lists and store them in last_heads.
    last_heads = [path.pop(0) for path in paths_to_nodes]

    while True:
      # At this point all heads should share the same node.
      assert all(last_heads[0] == l for l in last_heads)

      # What is the minimum length of all remaining paths?
      min_remaining_length = min([len(path) for path in paths_to_nodes])

      # At least the leaf nodes should remain
      assert min_remaining_length >= 1

      # If one remaining path starts starts with a different head, we have found
      # the lowest common ancestor.
      if not all(paths_to_nodes[0][0] == path[0] for path in paths_to_nodes):
        return last_heads[0]

      # Remove the first entries from all lists and store them in last_heads
      # again.
      last_heads = [path.pop(0) for path in paths_to_nodes]

  def _apply_synthesized_nodes(self, model: Model, yaml: Any) -> None:
    synthesized_nodes = yaml.get('synthesized-nodes', {})
    for id, children in synthesized_nodes.items():
      # Verify properties of synthesized nodes:
      assert id not in model.concepts
      assert len(children) > 0
      for child_id in children:
        assert child_id in model.concepts
        child = model.concepts[child_id]
        if not child.is_atomic_token():
          assert not isinstance(child, AtomicToken)
          assert not child.is_synthesized
      new_token = CompoundToken(model, id, children, is_synthesized=True)
      model.concepts[id] = new_token

      lowest_common_anecstor = self._find_lowest_common_ancestor(
          model, children)
      assert lowest_common_anecstor
      model.concepts[lowest_common_anecstor].children.append(id)

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
    self._apply_synthesized_nodes(model, yaml)

    # Persist the cut-offs so that other modules can apply them as well.
    renderer.country_data[country]['cut-off-tokens'] = set(
        yaml.get('cut-off-tokens', []))
    renderer.country_data[country]['cut-off-children'] = set(
        yaml.get('cut-off-children', []))
    renderer.country_data[country]['all-removed-tokens'] = all_removed_tokens

    renderer.set_model(country, model)
