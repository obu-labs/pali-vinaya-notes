#!/bin/python3
"""A read-only view of the segmented texts SuttaCentral's "bilarasuttas" API returns."""

from dataclasses import dataclass, field
from typing import Iterable, Mapping


def _without_blanks(texts: Mapping[str, str]) -> dict[str, str]:
  return {key: text for key, text in texts.items() if text and text.strip()}


@dataclass(frozen=True)
class BilaraText:
  """A text as a list of segment ids (`keys`) and what there is for each of them:
  the `html` it goes in (with a "{}" for where), its `translation`, its `root`
  text and any `comments` on the translation or `variants` of the root."""
  keys: list[str]
  html: Mapping[str, str]
  translation: Mapping[str, str]
  root: Mapping[str, str]
  comments: Mapping[str, str] = field(default_factory=dict)
  variants: Mapping[str, str] = field(default_factory=dict)

  @classmethod
  def from_json(cls, data: dict) -> 'BilaraText':
    """Takes the API's response, minus the blanks it has for the
    segments that don't have a comment or a variant."""
    return cls(
      keys=list(data['keys_order']),
      html=data['html_text'],
      translation=data['translation_text'],
      root=data['root_text'],
      comments=_without_blanks(data.get('comment_text', {})),
      variants=_without_blanks(data.get('variant_text', {})),
    )

  def en(self, key: str) -> str:
    return self.translation.get(key, '')

  def pali(self, key: str) -> str:
    return self.root.get(key, '')

  def size(self, keys: Iterable[str]) -> int:
    """How many of `keys` have been translated"""
    return sum(1 for key in keys if self.en(key).strip())
