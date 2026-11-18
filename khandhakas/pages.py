#!/bin/python3
"""Putting together the contents of each note's file."""

from pathlib import Path
from typing import Optional, Sequence

import markdownify

from vnmutils.mdutils import abs_path_to_obsidian_link_text

from .model import Note


def link_to(note: Note, folder: Path, text: Optional[str] = None) -> str:
  """Returns a markdown link to `note` from a file in `folder`"""
  return f"[{text or note.stem}{abs_path_to_obsidian_link_text(note.path, folder)}"


def render_breadcrumbs(note: Note, toc: Note, chapter_name: str, folder: Path) -> str:
  """Links to the table of contents and each of the headings that `note` is under"""
  crumbs = []
  parent = note.parent
  while parent:
    crumbs.insert(0, link_to(parent, folder))
    parent = parent.parent
  crumbs.insert(0, link_to(toc, folder, chapter_name))
  return "\n" + " › ".join(crumbs) + "\n\n"


def render_contents(notes: Sequence[Note], folder: Path, indent: str = "") -> str:
  """A nested list of links to `notes` and everything under them"""
  ret = ""
  for note in notes:
    ret += f"{indent}- {link_to(note, folder)}\n"
    ret += render_contents(note.children, folder, indent + "  ")
  return ret


def render_footnotes(footnotes: Sequence[str]) -> str:
  if not footnotes:
    return ""
  ret = "\n## Footnotes\n\n"
  for i, footnote in enumerate(footnotes):
    ret += f"[^{i + 1}]: {footnote}\n"
  return ret


def render_note_page(
  note: Note,
  next_note: Optional[Note],
  folder: Path,
  breadcrumbs: str,
  heading: str,
  body: str,
  footnotes: Sequence[str],
  source_url: str,
) -> str:
  """Returns the contents of the file for `note`

  `body` and `footnotes` are the rendered text of the note, if it has any,
  and `source_url` is where to find that on SuttaCentral."""
  ret = breadcrumbs + heading
  if note.keys:
    ret += body
    ret += f"\n\n~ [Ajahn Brahmali's translation]({source_url})\n"
  if note.children:
    if note.keys:
      ret += "\n### Contents\n\n"
    ret += render_contents(note.children, folder)
  if not note.keys:
    ret += f"\nSource: <{source_url}>\n"
  elif next_note:
    ret += f"\n**Next:** {link_to(next_note, folder)}\n"
  return ret + render_footnotes(footnotes)


def render_toc_page(blurb: str, notes: Sequence[Note], folder: Path, source_url: str) -> str:
  """Returns the contents of a chapter's summary and table of contents file"""
  ret = "\n## Summary\n\n"
  ret += markdownify.markdownify(blurb or '').strip()
  ret += "\n\n## Table of Contents\n\n"
  ret += render_contents(notes, folder)
  ret += f"\nSource: <{source_url}>\n"
  return ret
