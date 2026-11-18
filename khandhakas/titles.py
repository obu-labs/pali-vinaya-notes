#!/bin/python3
"""Naming the notes and their folders."""

from typing import Sequence
import re

from unidecode import unidecode

from utils.bilara import BilaraText
from utils.text import (
  append_phrase,
  ends_sentence,
  filename_title,
  first_sentence,
  plain_text,
  strip_number_prefix,
)

from .markup import is_end_of_passage, is_homage, rule_tag

HEADING_TITLE_LENGTH = 100
UNIT_TITLE_LENGTH = 70
FINISHED_RE = re.compile(r"^(.+?),? (?:is|are) finished\.?$")
# "The first section for recitation is finished" doesn't name what was in it
UNINFORMATIVE_ENDING_RE = re.compile(r"recitation|sections|chapter")


def folder_name(acronym: str, pali_title: str) -> str:
  """e.g. "Kd 4 Pavarana" for the Pavāraṇākkhandhaka"""
  name = pali_title.strip()
  if name.endswith('khandhaka'):
    name = name[:-len('khandhaka')]
    if name.endswith('k'):
      name = name[:-1]
  return f"{acronym} {unidecode(name)}"


def heading_title(text: BilaraText, key: str) -> str:
  """The heading at `key` in English (or failing that in Pāli) without its number"""
  return strip_number_prefix(plain_text(text.en(key)) or plain_text(text.pali(key)))


def unit_title(text: BilaraText, keys: Sequence[str]) -> str:
  """Untitled units are named for what the text says has just "finished",
  or else for their (first) rule, or else for their opening line."""
  last = next((k for k in reversed(keys) if text.en(k).strip()), None)
  if last and is_end_of_passage(text.html[last]):
    finished = FINISHED_RE.match(plain_text(text.en(last)))
    if finished and not UNINFORMATIVE_ENDING_RE.search(finished.group(1)):
      return finished.group(1)
  keys = [k for k in keys if not is_homage(text.html[k])]
  start = next((
    i for i, k in enumerate(keys)
    if rule_tag(text.html[k]) and text.en(k).strip()
  ), 0)
  title = ""
  for key in keys[start:]:
    title = append_phrase(title, plain_text(text.en(key)))
    # Short opening lines such as "The Buddha said," don't say much
    if len(title) >= UNIT_TITLE_LENGTH // 2 or ends_sentence(title):
      break
  return first_sentence(title).strip("“”‘’ ") or "Untitled"


def note_stem(number: Sequence[int], title: str, is_heading: bool) -> str:
  """The filename (without the ".md") for a note"""
  dotted = ".".join(str(n) for n in number)
  limit = HEADING_TITLE_LENGTH if is_heading else UNIT_TITLE_LENGTH
  return f"{dotted} - {filename_title(title, limit)}"


def toc_stem(chapter_title: str) -> str:
  return "0 - " + filename_title(chapter_title, HEADING_TITLE_LENGTH)
