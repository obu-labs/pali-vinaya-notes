#!/bin/python3
"""Helpers for keeping track of where we are in a stream of html fragments."""

import re

BLOCK_TAG_RE = re.compile(
  r"<(/?)(p|li|ol|ul|dl|dt|dd|blockquote|section)\b(?:[^>]*\bclass='([^']*)')?[^>]*>"
)

# An open element: its (tag, css class)
Element = tuple[str, str]


def block_tags(fragment: str) -> list[tuple[bool, str, str]]:
  """Returns (is_closing, tag, css class) for each block-level tag in `fragment`"""
  return [
    (bool(closing), tag, css_class)
    for closing, tag, css_class in BLOCK_TAG_RE.findall(fragment)
  ]


def update_open_elements(
  open_elements: tuple[Element, ...], fragment: str,
) -> tuple[tuple[Element, ...], list[Element]]:
  """Works out which block-level elements are still open after `fragment`.

  Returns (the new open elements, the outermost elements which got closed).
  A closing tag closes the innermost element with that tag, along with
  anything left open inside of it. One that matches nothing is ignored."""
  elements = list(open_elements)
  closed_outermost: list[Element] = []
  for closing, tag, css_class in block_tags(fragment):
    if not closing:
      elements.append((tag, css_class))
      continue
    for i in range(len(elements) - 1, -1, -1):
      if elements[i][0] == tag:
        if i == 0:
          closed_outermost.append(elements[i])
        del elements[i:]
        break
  return (tuple(elements), closed_outermost)
