#!/bin/python3

import re
import json
import os
from pathlib import Path
import requests

import joblib

from idrangepathstore import IDRangePathStore

SCUID_SEGMENT_PATHS = IDRangePathStore()

def superscript_number(n: int) -> str:
  ret = str(n)
  return ret.replace('0', '\u2070')\
    .replace('1', '\u00b9')\
    .replace('2', '\u00b2')\
    .replace('3', '\u00b3')\
    .replace('4', '\u2074')\
    .replace('5', '\u2075')\
    .replace('6', '\u2076')\
    .replace('7', '\u2077')\
    .replace('8', '\u2078')\
    .replace('9', '\u2079')

def full_obsidian_style_link_for_scuid(scuid: str, relative_to: Path) -> str:
  path = SCUID_SEGMENT_PATHS.get(scuid)
  if not path:
    raise ValueError(f"Unknown SCUID: {scuid}")
  return "[" + path.stem + abs_path_to_obsidian_link_text(path, relative_to)

def abs_path_to_obsidian_link_text(path: Path, relative_to: Path) -> str:
  if relative_to.suffix: # if the filename contains a dot, assume it's a file
    relative_to = relative_to.parent
  relpath = os.path.relpath(path, relative_to)
  return "](" + \
    relpath.replace(' ', '%20') + \
    ")"
  
# This is the style for the links that Ajahn Brahmali includes in his notes
# See suttacentral.sc_link_for_ref for the format of our links
SUTTACENTRAL_LINK_RE = re.compile(
  r'\[([^\]]+)\]\(https://suttacentral\.net/([\w-]+)/en/brahmali/?#?([0-9.]*)\)'
)

def rewrite_suttacentral_links_in_markdown_file(markdownfile: Path):
  text = markdownfile.read_text(encoding='utf-8')

  def replacer(match):
    link_text = match.group(1)
    document = match.group(2)
    segment = match.group(3)
    if segment:
      while segment[-1] == '.':
        segment = segment[:-1]
      scid = f"{document}:{segment}"
    else:
      scid = document

    absolute_path = SCUID_SEGMENT_PATHS.get(scid)

    if absolute_path:
      obsidian_link = abs_path_to_obsidian_link_text(absolute_path, markdownfile.parent)
      return f"[{link_text}{obsidian_link}"
    else:
      return match.group(0)  # Leave unchanged if not found

  new_text = SUTTACENTRAL_LINK_RE.sub(replacer, text)
  if new_text != text:
    markdownfile.write_text(new_text, encoding='utf-8')

def rewrite_suttacentral_links_in_folder(folder: Path):
  for markdownfile in folder.glob('**/*.md'):
    rewrite_suttacentral_links_in_markdown_file(markdownfile)
 
