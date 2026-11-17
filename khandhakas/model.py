#!/bin/python3
"""The shapes a Khandhaka takes on its way to becoming notes."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional, Union

from utils.segments import first_number


@dataclass
class Section:
  """A heading in the source html and what's under it:
  runs of segments and subheadings, in order."""
  level: int
  key: Optional[str]
  # Some headings open a <section> which is then closed somewhere in the text
  wraps: bool = False
  items: list[Union[list[str], 'Section']] = field(default_factory=list)

  def add(self, key: str):
    if self.items and isinstance(self.items[-1], list):
      self.items[-1].append(key)
    else:
      self.items.append([key])


@dataclass
class Atom:
  """The smallest run of segments we're willing to consider splitting off."""
  keys: list[str] = field(default_factory=list)
  has_rule: bool = False
  # Must this start a new note?
  hard: bool = False
  # Does this start with a horizontal rule?
  ruled_off: bool = False
  # Is this an embedded sutta or jātaka?
  story: bool = False
  # Does this start with one of a series of numbered paragraphs?
  counted: bool = False

  @property
  def number(self) -> str:
    """The first number in the segment ids. e.g. "27" for pli-tv-kd20:27.2.8"""
    return first_number(self.keys[0])


@dataclass
class Note:
  """A markdown file to be written.

  A Note has `keys` (the segments whose text it contains) and/or
  `children`, in which case it's (also) an index of them."""
  number: tuple[int, ...]
  title: str
  heading_key: Optional[str] = None
  keys: list[str] = field(default_factory=list)
  children: list['Note'] = field(default_factory=list)
  parent: Optional['Note'] = None
  stem: str = ''
  path: Optional[Path] = None

  def walk(self) -> Iterator['Note']:
    yield self
    for child in self.children:
      yield from child.walk()

  @property
  def start_key(self) -> str:
    return self.heading_key or self.keys[0]
