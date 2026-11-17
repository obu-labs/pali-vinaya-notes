#!/bin/python3
"""Working out which notes a chapter will be written to."""

from collections import Counter
from typing import Iterable, Iterator, Optional, Union

from utils.bilara import BilaraText

from .model import Note, Section
from .rules import RuleIndex
from .sections import chapter_bounds, last_section, parse_sections
from .splitting import LIMITS, Limits, split_units
from .titles import heading_title, note_stem, unit_title

Part = Union[list[str], Section]


def walk(notes: Iterable[Note]) -> Iterator[Note]:
  """Every note in `notes` and under them, in reading order"""
  for note in notes:
    yield from note.walk()


def planned_keys(notes: Iterable[Note]) -> list[str]:
  """Every segment that `notes` cover, in the order they'll be read"""
  return [
    key for note in walk(notes)
    for key in ([note.heading_key] if note.heading_key else []) + note.keys
  ]


def parts_of(text: BilaraText, rules: RuleIndex, section: Section, limits: Limits = LIMITS) -> list[Part]:
  """Returns the units of text and subheadings directly under `section`, in order"""
  parts: list[Part] = []
  for item in section.items:
    if isinstance(item, Section):
      parts.append(item)
    else:
      parts.extend(split_units(text, rules, item, limits))
  return parts


def build_notes(
  text: BilaraText,
  rules: RuleIndex,
  parts: list[Part],
  number: tuple[int, ...],
  parent: Optional[Note],
  limits: Limits = LIMITS,
) -> list[Note]:
  notes: list[Note] = []
  for part in parts:
    child_number = number + (len(notes) + 1,)
    if isinstance(part, Section):
      notes.append(build_note(text, rules, part, child_number, parent, limits))
    else:
      notes.append(Note(child_number, unit_title(text, part), keys=part, parent=parent))
  return notes


def build_note(
  text: BilaraText,
  rules: RuleIndex,
  section: Section,
  number: tuple[int, ...],
  parent: Optional[Note],
  limits: Limits = LIMITS,
) -> Note:
  """Returns the Note for the heading `section` with the Notes for everything under it"""
  note = Note(number, heading_title(text, section.key), heading_key=section.key, parent=parent)
  parts = parts_of(text, rules, section, limits)
  if not note.title: # A few of the inserted headings are blank
    note.title = unit_title(text, next((p for p in parts if isinstance(p, list)), []))
  # A heading's text goes in its own note when there's only the one unit of
  # it or when it's just the one unit introducing the subheadings.
  if parts and isinstance(parts[0], list) and all(isinstance(p, Section) for p in parts[1:]):
    note.keys = parts.pop(0)
  note.children = build_notes(text, rules, parts, number, note, limits)
  return note


def plan_notes(
  text: BilaraText, rules: RuleIndex, uddana_title: str, limits: Limits = LIMITS,
) -> list[Note]:
  """Returns the (top-level) Notes for the chapter `text`, named and numbered"""
  start, end = chapter_bounds(text.html, text.keys)
  assert start < end, "Found nothing between the title and the end of the chapter"
  root = parse_sections(text.html, text.keys[start:end])
  assert any(isinstance(item, Section) for item in root.items), "Found no headings"

  # After the text comes the chapter's summary verses (the uddāna)
  ending = text.keys[end:]
  has_uddana = any("uddana" in text.html[key] for key in ending)
  if not has_uddana:
    last = last_section(root)
    for key in ending:
      last.add(key)

  notes = build_notes(text, rules, parts_of(text, rules, root, limits), (), None, limits)
  if has_uddana:
    notes.append(Note((len(notes) + 1,), uddana_title, keys=ending))
  assert planned_keys(notes) == text.keys[start:], "Some of the chapter has gone missing or out of order!"
  for note in walk(notes):
    note.stem = note_stem(note.number, note.title, is_heading=bool(note.heading_key))
  return notes


def duplicated_stems(stems: Iterable[str]) -> set[str]:
  """Returns (in lowercase) the names used more than once, ignoring case.

  Obsidian wants every note in the vault to have a unique name."""
  counts = Counter(stem.lower() for stem in stems)
  return {stem for stem, count in counts.items() if count > 1}
