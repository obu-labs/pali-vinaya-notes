#!/bin/python3
"""Finding every place where the text could be split into separate notes."""

from typing import Optional, Sequence

from utils.bilara import BilaraText
from utils.html import Element, update_open_elements
from utils.segments import paragraph_of

from .markup import (
  STORY_SECTIONS,
  is_counted,
  is_end_of_passage,
  is_homage,
  is_ruled_off,
  rule_tag,
  starts_story,
)
from .model import Atom

# Horizontal rules divide up the text, but they're also used
# to space out lists of things that are shorter than this.
SHORT_BLOCK = 10


def atomize(text: BilaraText, keys: Sequence[str], short_block: int = SHORT_BLOCK) -> list[Atom]:
  """Chops `keys` up at every point where it might make sense to start a new note.

  Those points have to be between two top-level blocks of html
  (i.e. not in the middle of a paragraph, list, legal procedure or sutta)
  and are found wherever there's:
    - a horizontal rule,
    - a declaration that some passage "is finished",
    - an embedded sutta or jātaka starting or ending, or
    - a change in the "paragraph" number of the segment ids
      (so, between pli-tv-kd20:27.1.3 and pli-tv-kd20:27.2.1)
  The Atoms after a "finished" and those between horizontal rules (unless
  they're shorter than `short_block`) always start a new note (they're `hard`).
  For the others, see `splitting.should_split`
  """
  atoms: list[Atom] = []
  open_elements: tuple[Element, ...] = ()
  previous_paragraph: Optional[list[str]] = None
  after_story = False
  after_end_of_passage = False
  after_homage = False
  for key in keys:
    template = text.html[key]
    paragraph = paragraph_of(key)
    end_of_passage = is_end_of_passage(template)
    story = starts_story(template)
    ruled_off = False
    boundary = False
    # "X is finished" always goes with X and "Namo tassa..." with what it opens
    if atoms and not open_elements and not end_of_passage and not after_homage:
      ruled_off = is_ruled_off(template)
      boundary = ruled_off or after_end_of_passage or story or after_story \
        or paragraph != previous_paragraph
    if boundary or not atoms:
      atoms.append(Atom(
        hard=boundary and after_end_of_passage,
        ruled_off=ruled_off,
        story=story and not open_elements,
        counted=is_counted(template),
      ))
    atoms[-1].keys.append(key)
    if rule_tag(template):
      atoms[-1].has_rule = True
    # (Closing tags for a <section> opened by a heading won't match anything)
    open_elements, closed = update_open_elements(open_elements, template)
    after_story = any(css_class in STORY_SECTIONS for _, css_class in closed)
    after_end_of_passage = end_of_passage
    after_homage = is_homage(template)
    previous_paragraph = paragraph
  _harden_long_blocks(text, atoms, short_block)
  return atoms


def _harden_long_blocks(text: BilaraText, atoms: list[Atom], short_block: int):
  """Marks as `hard` the Atoms starting with a horizontal rule that
  has at least `short_block` segments of text on both sides of it."""
  blocks = [i for i, atom in enumerate(atoms) if i == 0 or atom.ruled_off] + [len(atoms)]
  sizes = [
    text.size(key for atom in atoms[start:end] for key in atom.keys)
    for start, end in zip(blocks, blocks[1:])
  ]
  for i in range(1, len(sizes)):
    if min(sizes[i - 1], sizes[i]) >= short_block:
      atoms[blocks[i]].hard = True
