#!/bin/python3
"""Fetches the Khandhakas from SuttaCentral and writes their notes to disk.

This is the only part of the package that touches the network, the disk
or the state in the `suttacentral` module."""

from dataclasses import replace
from typing import Iterator, Mapping, Optional, Sequence

import requests

from vnmutils.mdutils import SCUID_SEGMENT_PATHS, abs_path_to_obsidian_link_text

import suttacentral
from utils.bilara import BilaraText
from utils.text import indent_later_paragraphs, plain_text

from .links import complete_bare_links, link_rule_mentions
from .model import Note
from .pages import render_breadcrumbs, render_note_page, render_toc_page
from .planning import duplicated_stems, plan_notes, walk
from .rendering import RenderOptions, render_heading, render_segments
from .rules import index_rules
from .titles import folder_name, toc_stem

SUTTAPLEX_URL = "https://suttacentral.net/api/suttaplex/{}?language=en"


@suttacentral.disk_memoizer.cache()
def get_kd_plex() -> list[dict]:
  r = requests.get(SUTTAPLEX_URL.format("pli-tv-kd"))
  return r.json()


class Khandhaka:
  def __init__(self, plex: dict, data: dict):
    self.plex = plex
    self.uid: str = plex['uid']
    self.acronym: str = plex['acronym']
    self.data = data
    text = BilaraText.from_json(data)
    self.text = replace(text, translation={
      key: complete_bare_links(line) for key, line in text.translation.items()
    })
    self.folder = suttacentral.KD_FOLDER / folder_name(self.acronym, plex['original_title'])
    self.toc = Note(
      (0,),
      plain_text(plex['translated_title']),
      stem=toc_stem(plex['translated_title']),
    )
    try:
      self.notes = plan_notes(self.text, index_rules(self.text), f"Uddāna of {self.acronym}")
    except AssertionError as e:
      raise AssertionError(f"{self.uid}: {e}") from e

  def all_notes(self) -> Iterator[Note]:
    yield self.toc
    yield from walk(self.notes)

  def set_paths(self):
    for note in self.all_notes():
      note.path = self.folder / f"{note.stem}.md"

  def _href_for_rule(self, uid: str) -> Optional[str]:
    if uid not in suttacentral.RULENAMES:
      return None
    link = abs_path_to_obsidian_link_text(suttacentral.pm_file_for_scid(uid), self.folder)
    return link[2:-1] # strip off the "](" and ")"

  def _render_comment(self, comment: str) -> str:
    comment = link_rule_mentions(
      comment,
      self._href_for_rule,
      lambda scid: bool(SCUID_SEGMENT_PATHS.get(scid)),
    )
    comment = suttacentral.render_note_as_markdown(comment, self.folder, strict=False)
    return indent_later_paragraphs(comment)

  def _locate_variants(self, words: list[str], key: str) -> Optional[Mapping[int, Sequence[str]]]:
    try:
      return suttacentral.build_variant_map(words, key, self.data)
    except Exception:
      return None

  def render(self):
    """Writes this chapter's notes to its folder"""
    options = RenderOptions(
      render_comment=self._render_comment,
      locate_variants=self._locate_variants,
    )
    self.folder.mkdir(parents=True)
    suttacentral.write_md_file(self.toc.path, self.uid, None, render_toc_page(
      self.plex['blurb'],
      self.notes,
      self.folder,
      f"https://suttacentral.net/{self.uid}/en/brahmali",
    ))
    notes = list(walk(self.notes))
    # "Next" goes to the next note that has something to read in it
    readable = [note for note in notes if note.keys]
    for note in notes:
      next_note = None
      body, footnotes = "", []
      if note.keys:
        i = readable.index(note)
        next_note = readable[i + 1] if i + 1 < len(readable) else None
        body, footnotes = render_segments(self.text, note.keys, options)
      suttacentral.write_md_file(
        note.path,
        note.start_key,
        note.keys[-1] if note.keys else None,
        render_note_page(
          note,
          next_note,
          self.folder,
          breadcrumbs=render_breadcrumbs(
            note, self.toc, f"{self.acronym}: {self.toc.title}", self.folder,
          ),
          heading=render_heading(self.text, note.heading_key),
          body=body,
          footnotes=footnotes,
          source_url=suttacentral.sc_link_for_ref(note.start_key),
        ),
      )


def plan_khandhakas() -> list[Khandhaka]:
  """Fetches the Khandhakas and works out what notes they'll be written to."""
  plexes = get_kd_plex()[1:] # The first entry is the Khandhaka collection itself
  assert len(plexes) == 22, f"Expected 22 Khandhakas but got {len(plexes)}"
  khandhakas = []
  for plex in plexes:
    print(f"  Fetching {plex['acronym']}...")
    khandhakas.append(Khandhaka(plex, suttacentral.get_vb_json(plex['uid'])))
  # Where the same section number and title appear in several chapters, say which is which.
  duplicates = duplicated_stems(
    note.stem for kd in khandhakas for note in kd.all_notes()
  )
  for kd in khandhakas:
    for note in kd.all_notes():
      if note.stem.lower() in duplicates:
        note.stem += f" ({kd.acronym})"
    kd.set_paths()
  return khandhakas


def render_khandhakas():
  khandhakas = plan_khandhakas()
  for kd in khandhakas:
    print(f"  Writing {kd.acronym} ({kd.plex['original_title']})...")
    kd.render()
