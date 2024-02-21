from renderer import Renderer
from modules.abstract_module import AbstractModule
from pathlib import Path
from typing import Any, Optional
from schema import Schema
import schema
import re
from renderer import Renderer
import os


class GraphsModule(AbstractModule):
  """Module to generate pdf renderings of address trees."""

  def schema(self):
    return Schema({
        "enabled": bool,
        schema.Optional("abbreviations"): {
            str: str
        },
        schema.Optional("deduplicate-nodes"): bool,
        "graphs": {
            str: {
                "start-nodes": [str],
                schema.Optional("stop-at"): [str],
                schema.Optional("stop-before"): [str],
            }
        }
    })

  def observe_file(self, path: Path, renderer: Renderer):
    match = re.fullmatch(r'(?P<country>..|global)-graphs\.yaml', path.name)
    if not match:
      return

    country = match.groupdict()['country']
    yaml = self.read_yaml(path)
    renderer.country_data[country][self.name()] = yaml
    renderer.add_country(country)

  def render_graph(self, country: str, renderer: Renderer, graphviz, graph_id,
                   yaml):
    abbreviations = yaml.get('abbreviations', {})
    deduplicate = yaml.get('deduplicate-nodes', False)

    g = graphviz.Digraph(f'{country}-{graph_id}')

    # Token name generation for the graphviz file. If "deduplicate-nodes" is
    # true in the config file, every token_id gets assigned the same graphviz
    # node and we may generate a DAG. If "deduplicate-nodes" is false, every
    # call to create_graphviz_token creates a new graphviz node.
    token_counter = 0
    graphviz_token_deduplication_map = {}

    def create_graphviz_token(token_id) -> int:
      nonlocal token_counter, graphviz_token_deduplication_map, deduplicate
      if deduplicate and token_id in graphviz_token_deduplication_map:
        return graphviz_token_deduplication_map[token_id]
      token_counter += 1
      if deduplicate:
        graphviz_token_deduplication_map[token_id] = token_counter
      return token_counter

    edge_deduplication_set = set()

    def add_edge(from_graphviz_token, to_graphviz_token):
      nonlocal g, deduplicate, edge_deduplication_set
      if deduplicate:
        if (from_graphviz_token, to_graphviz_token) in edge_deduplication_set:
          return
      g.edge(f'token_{from_graphviz_token}', f'token_{to_graphviz_token}')
      if deduplicate:
        edge_deduplication_set.add((from_graphviz_token, to_graphviz_token))

    # Recursive function that adds a new token for token_id to the graphviz
    # graph plus all of it's children. The return value is the graphviz token
    # that was introduced for the new node. It is used for linking nodes.
    def add_token_and_children(token_id) -> Optional[int]:
      if token_id in yaml['graphs'][graph_id].get('stop-before', []):
        return None

      nonlocal country, renderer, g, abbreviations
      token_id_number = create_graphviz_token(token_id)

      label = token_id
      if token_id in abbreviations:
        label = abbreviations[token_id]

      g.node(f'token_{token_id_number}', label)

      token = renderer.country_data[country]['model'].find_token(token_id)
      if (token_id not in yaml['graphs'][graph_id].get('stop-at', [])
          and not token.is_atomic_token() and token.children):
        for child_id in token.children:
          child_id_number = add_token_and_children(child_id)
          if child_id_number:
            add_edge(token_id_number, child_id_number)

      return token_id_number

    for token_id in yaml['graphs'][graph_id]['start-nodes']:
      add_token_and_children(token_id)

    g.render(directory=renderer.output_dir)

  def render_epilogue(self, country: str, renderer: Renderer) -> Optional[str]:
    yaml = renderer.country_data[country].get(self.name())
    if not yaml or not yaml['enabled']:
      return None

    try:
      import graphviz
    except ModuleNotFoundError:
      print("Skipping graph generation because graphviz could not be found")

    graphs = yaml.get("graphs", {})
    for graph_id in graphs.keys():
      self.render_graph(country, renderer, graphviz, graph_id, yaml)

    return None
