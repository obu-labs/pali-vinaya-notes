#!/bin/python3
"""What SuttaCentral's html says about a segment of a Khandhaka."""

from typing import Optional
import re

# The <h5>s are labels inside of the text rather than divisions of it
HEADING_RE = re.compile(r"<h([2-4])\b")
END_OF_CHAPTER_RE = re.compile(r"class='end(sutta|book)'")
END_MARKER_RE = re.compile(r"<p class='end(sutta|book)?'>\{\}")
# e.g. "The first wonder is finished."
END_OF_PASSAGE_RE = re.compile(r"^<p class='end'>\{\}</p>$")
RULE_RE = re.compile(r"<(p|li)\b[^>]*\bclass='rule'[^>]*>")
COUNTER_RE = re.compile(r"\sdata-counter='([^']*)'")
COUNTED_PARAGRAPH_RE = re.compile(r"<p data-counter='([^']*)'>")
LIST_ITEM_RE = re.compile(r"<li(?: value='(\d+)')?>")
# Embedded texts which are kept whole
STORY_SECTIONS = frozenset({'suttanta', 'jataka'})


def heading_level(template: str) -> Optional[int]:
  """Returns 2 for an <h2> etc. or None if this isn't one of the headings dividing up the text"""
  heading = HEADING_RE.search(template)
  return int(heading.group(1)) if heading else None


def rule_tag(template: str) -> Optional[re.Match]:
  """Returns the opening tag of the rule starting in `template`, if there is one"""
  return RULE_RE.search(template)


def is_end_of_chapter(template: str) -> bool:
  return bool(END_OF_CHAPTER_RE.search(template))


def is_end_marker(template: str) -> bool:
  """Is this any of the lines announcing that something has finished?"""
  return bool(END_MARKER_RE.search(template))


def is_end_of_passage(template: str) -> bool:
  """Is this a line announcing that some part of the chapter has finished?"""
  return bool(END_OF_PASSAGE_RE.match(template))


def is_homage(template: str) -> bool:
  """Is this the "Namo tassa..."?"""
  return "class='namo'" in template


def is_counted(template: str) -> bool:
  """Is this one of the paragraphs that SuttaCentral numbers in the margin?"""
  return 'data-counter' in template


def starts_story(template: str) -> bool:
  return any(f"<section class='{story}'" in template for story in STORY_SECTIONS)


def is_ruled_off(template: str) -> bool:
  """Is there a horizontal rule above this?
  (Not counting those between numbered paragraphs, which are never divisions)"""
  return '<hr' in template and not is_counted(template)
