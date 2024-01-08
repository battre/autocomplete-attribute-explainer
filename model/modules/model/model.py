from typing import Dict, List, Union, Optional, Iterator
from abc import ABC, abstractmethod

AtomicOrCompoundToken = Union['AtomicToken', 'CompoundToken']


class TokenBase(ABC):
  """Base class for tokens."""

  # Pointer to the model owning the token.
  model: "Model"
  id: str

  def __init__(self, model: "Model", id: str):
    self.model = model
    self.id = id

  def __str__(self) -> str:
    return self.id

  @abstractmethod
  def pre_order(self) -> Iterator[AtomicOrCompoundToken]:
    pass

  @abstractmethod
  def is_atomic_token(self) -> bool:
    return True


class AtomicToken(TokenBase):
  """An atomic token (e.g. the given-name)."""

  def __init__(self, model: "Model", id: str):
    super().__init__(model, id)

  def __str__(self) -> str:
    return super().__str__()

  def pre_order(self) -> Iterator[AtomicOrCompoundToken]:
    yield self

  def is_atomic_token(self):
    return True


class CompoundToken(TokenBase):
  model: "Model"
  id: str
  children: List[str]
  is_synthesized: bool

  def __init__(self,
               model: "Model",
               id: str,
               children: List[str],
               is_synthesized=False):
    super().__init__(model, id)
    self.children = children
    self.is_synthesized = is_synthesized

  def __str__(self) -> str:
    concepts = ", ".join(
        [self.model.concepts[c].__str__() for c in self.children])
    return f'{super().__str__()}: [{concepts}]'

  def pre_order(self) -> Iterator[AtomicOrCompoundToken]:
    yield self
    for child in self.children:
      for token in self.model.concepts[child].pre_order():
        yield token

  def is_atomic_token(self):
    return False


class Translation:
  value: Dict[str, str]  # locale (lower case 2-digit code) -> string

  def __init__(self, yaml: Union[dict, str]):
    """Converts a yaml representation of a translation to a `Translation`.

        Examples of valid values for `yaml` are the values of `description` in
        - description: foobar
        - description:
          - en: foobar
          - fr: baz
        In other words: A string or a list of dictionaries with a single entry,
        where the key represents a locale and the value a translation string
        """
    self.value = dict()
    if isinstance(yaml, str):
      self.value["en"] = yaml
    elif isinstance(yaml, dict):
      self.value = {k: v for k, v in yaml.items()}
    else:
      assert False, f"unexpected type: {yaml}"

  def locales(self) -> List[str]:
    return list(self.value)

  def get(self, locale) -> Optional[str]:
    return self.value[locale] or self.value["en"]

  def __str__(self) -> str:
    return "{" + ", ".join(f"{k}: {v}" for k, v in self.value.items()) + "}"


class Model:
  """The model for a single country."""
  concepts: Dict[str, AtomicOrCompoundToken]
  root_concepts: List[str]
  short_descriptions: Dict[str, Translation]

  def __init__(self):
    self.concepts = dict()
    self.root_concepts = []
    self.short_descriptions = dict()

  def __str__(self) -> str:
    return ("\n".join([self.concepts[c].__str__() for c in self.root_concepts]))

  def add_token(self, token: AtomicOrCompoundToken):
    self.concepts[token.id] = token

  def pre_order(self) -> Iterator[AtomicOrCompoundToken]:
    for root_concept in self.root_concepts:
      for entry in self.concepts[root_concept].pre_order():
        yield entry

  def pre_order_only_uniques(self) -> Iterator[AtomicOrCompoundToken]:
    """Pre-order traversal that shows each node only once"""
    seen = set()
    for entry in self.pre_order():
      if entry.id in seen:
        continue
      seen.add(entry.id)
      yield entry

  def pre_order_descend_only_once(self) -> Iterator[AtomicOrCompoundToken]:
    descended = set()

    def recursion(
        node: AtomicOrCompoundToken) -> Iterator[AtomicOrCompoundToken]:
      yield node
      if not node.is_atomic_token() and node.id not in descended:
        assert not isinstance(node, AtomicToken)
        descended.add(node.id)
        for child_id in node.children:
          for child in recursion(self.concepts[child_id]):
            yield child

    for root_concept_id in self.root_concepts:
      for node in recursion(self.concepts[root_concept_id]):
        yield node

  def find_token(self, id) -> Optional[AtomicOrCompoundToken]:
    return self.concepts[id]

  def find_path_to_node(self, id) -> List[str]:
    path = []

    def recursion(node: AtomicOrCompoundToken) -> bool:
      path.append(node.id)
      if node.id == id:
        return True
      if not node.is_atomic_token():
        assert not isinstance(node, AtomicToken)
        for child_id in node.children:
          if found := recursion(self.concepts[child_id]):
            return found
      path.pop()
      return False

    for root_concept_id in self.root_concepts:
      if recursion(self.concepts[root_concept_id]):
        return path
    return path
