#!/bin/python3
"""Helpers for reading (in the loosest sense) Pāli prose."""

from typing import Iterable
import re

# How the Pāli starts off a new story: "At that time..." or
# "When the Buddha had stayed at ... for as long as he liked..."
NEW_STORY_RE = re.compile(r"^tena (kho pana )?samayena\b|yathābhirantaṁ viharitvā")


def opens_new_story(line: str) -> bool:
  return bool(NEW_STORY_RE.search(line.lstrip(' “‘').lower()))


def open_quotes(lines: Iterable[str]) -> int:
  """How many double quotes are left open at the end of `lines`.

  The source text is missing the odd closing quote, so, to not let that
  throw the count off forever, it's reset whenever a new story starts."""
  count = 0
  for line in lines:
    if opens_new_story(line):
      count = 0
    count += line.count('“') - line.count('”')
  return count


def split_words(line: str) -> list[str]:
  """Splits on whitespace and after dashes"""
  return line.replace('—', '— ').split()


def word_parts(text: str, only_starts: bool = False) -> set[str]:
  """Every five letters in a row in `text`, not counting the ends of the words.
  With `only_starts`, just the first five letters of each word.

  A crude way to see that "aḍḍhapallaṅkan" has to do with "pallaṅkena" """
  ret = set()
  for word in re.findall(r"[^\W\d_]+", text.lower()):
    stem = word[:-2] # near enough
    if len(stem) < 5:
      continue
    ret.update(stem[i:i + 5] for i in range(1 if only_starts else len(stem) - 4))
  return ret
