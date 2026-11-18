#!/bin/python3
"""Reading the structure of a chapter from the headings in its html."""

from typing import Mapping, Sequence

from utils.html import block_tags

from .markup import heading_level, is_end_of_chapter
from .model import Section


def chapter_bounds(html: Mapping[str, str], keys: Sequence[str]) -> tuple[int, int]:
  """Returns the indexes of `keys` where the chapter's text starts (after its
  title) and ends (before the lines announcing the end and its summary verses)."""
  start = next(i for i, key in enumerate(keys) if '<h1' in html[key]) + 1
  end = next(
    (i for i, key in enumerate(keys) if is_end_of_chapter(html[key])),
    len(keys),
  )
  return (start, end)


def parse_sections(html: Mapping[str, str], keys: Sequence[str]) -> Section:
  """Returns a headingless Section containing all of `keys` under their headings"""
  root = Section(1, None)
  stack = [root]
  sections_open_in_text = 0
  for key in keys:
    template = html[key]
    level = heading_level(template)
    if level:
      while stack[-1].level >= level:
        stack.pop()
      section = Section(level, key, wraps=template.startswith('<section'))
      stack[-1].items.append(section)
      stack.append(section)
      sections_open_in_text = 0
      continue
    stack[-1].add(key)
    for closing, tag, _ in block_tags(template):
      if tag != 'section':
        continue
      if not closing:
        sections_open_in_text += 1
      elif sections_open_in_text:
        sections_open_in_text -= 1
      else:
        # This closes a <section> that a heading opened,
        # so whatever comes next isn't under that heading
        for i in range(len(stack) - 1, 0, -1):
          if stack[i].wraps:
            del stack[i:]
            break
  return root


def last_section(section: Section) -> Section:
  """Returns the Section that the very end of `section` is directly under"""
  while section.items and isinstance(section.items[-1], Section):
    section = section.items[-1]
  return section
