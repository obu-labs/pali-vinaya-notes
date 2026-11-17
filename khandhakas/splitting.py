#!/bin/python3
"""Deciding which pieces of the text belong together in a note."""

from dataclasses import dataclass
from typing import Sequence
import re

from utils.bilara import BilaraText
from utils.pali import open_quotes, opens_new_story

from .atoms import atomize
from .model import Atom
from .rules import RuleIndex, rules_share_a_word

# Stories about monastics "being afraid of wrongdoing" because of what the
# Buddha had "prohibited" or taking advantage of what he had "allowed"
# are about amending the rule that came before them.
MODIFICATION_RE = re.compile(r"kukkuccāy|paṭikkhitt|anuññāt")


@dataclass(frozen=True)
class Limits:
  """How big a note is allowed to grow (measured in translated segments)
  before we start looking for a place to split it. See `should_split`"""
  soft: int = 45
  hard: int = 90
  # A trailing bit of text this short with no rule in it is kept with the
  # note before it rather than getting a note of its own.
  short_ending: int = 8
  # And a bit this short ("The Buddha then set out for Vesālī") goes with what follows
  short_opening: int = 3


LIMITS = Limits()


def keys_of(atoms: Sequence[Atom]) -> list[str]:
  return [key for atom in atoms for key in atom.keys]


def has_rule(atoms: Sequence[Atom]) -> bool:
  return any(atom.has_rule for atom in atoms)


def is_fresh_start(text: BilaraText, atom: Atom) -> bool:
  """Does `atom` open the way that the Pāli opens a new story?"""
  first_line = next((text.pali(k) for k in atom.keys if text.pali(k).strip()), '')
  return opens_new_story(first_line)


def is_mid_speech(text: BilaraText, keys: Sequence[str]) -> bool:
  """Has somebody in the story been left with their quotation marks open?"""
  return open_quotes(text.pali(key) for key in keys) > 0


def modifies(text: BilaraText, rules: RuleIndex, keys: Sequence[str], atom: Atom) -> bool:
  """Does the story in `atom` amend, relax or extend the rule(s) in `keys`?"""
  story = " ".join(text.pali(k) for k in atom.keys if k not in rules.rule_keys)
  if MODIFICATION_RE.search(story.lower()):
    return True
  return rules_share_a_word(text, rules, keys, atom.keys)


def should_split(
  text: BilaraText, rules: RuleIndex, unit: Sequence[Atom], atom: Atom, limits: Limits = LIMITS,
) -> bool:
  """Should `atom` start a new note or be added to the `unit` before it?"""
  if atom.hard:
    return True
  keys = keys_of(unit)
  size = text.size(keys)
  last_line = next((text.pali(k).strip() for k in reversed(keys) if text.pali(k).strip()), '')
  if last_line.endswith('—'):
    # The unit ends by introducing what comes next ("...he addressed the monks:")
    return False
  if atom.story:
    return True
  if atom.counted and any(a.counted for a in unit):
    return False # Keep the numbered paragraphs together
  if not is_fresh_start(text, atom):
    # The story continues, a procedure is spelled out ("And it should be done like this...")
    # or another case is considered ("In this case..."). Only split these up if we have to.
    if atom.has_rule and not has_rule(unit):
      return False # This is the rule that the story has been leading up to
    if is_mid_speech(text, keys):
      return size >= 2 * limits.hard
    return size >= limits.hard
  # A new story is starting...
  same_number = atom.number == unit[-1].number
  if not has_rule(unit):
    # ...but the last one hasn't gotten to its point yet. Perhaps it's still setting the scene
    return size >= limits.soft or not same_number
  # ...and we've already got a rule, so we're done, unless it's the story of that rule's amendment
  return not (
    same_number
    and size + text.size(atom.keys) <= limits.hard
    and modifies(text, rules, keys, atom)
  )


def group_atoms(
  text: BilaraText, rules: RuleIndex, atoms: Sequence[Atom], limits: Limits = LIMITS,
) -> list[list[Atom]]:
  """Groups `atoms` into the units that each get a note"""
  units: list[list[Atom]] = []
  for atom in atoms:
    if units and not should_split(text, rules, units[-1], atom, limits):
      units[-1].append(atom)
    else:
      units.append([atom])
  for i in range(len(units) - 2, -1, -1):
    if not units[i + 1][0].hard \
        and not has_rule(units[i]) \
        and text.size(keys_of(units[i])) <= limits.short_opening:
      units[i].extend(units.pop(i + 1))
  if len(units) > 1 \
      and not units[-1][0].hard \
      and not has_rule(units[-1]) \
      and text.size(keys_of(units[-1])) <= limits.short_ending:
    ending = units.pop()
    units[-1].extend(ending)
  return units


def split_units(
  text: BilaraText, rules: RuleIndex, keys: Sequence[str], limits: Limits = LIMITS,
) -> list[list[str]]:
  """Splits a run of text into the units that each get a note.

  The goal is for each note to be about one thing while still keeping each
  rule together with its origin story, its procedure and its amendments.
  """
  return [keys_of(unit) for unit in group_atoms(text, rules, atomize(text, keys), limits)]
