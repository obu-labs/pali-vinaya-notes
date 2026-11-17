#!/bin/python3
"""Fixing up the links to SuttaCentral in the translation and its notes."""

from typing import Callable, Optional
import re

# Ajahn Brahmali's notes link to the rules by their Vibhaṅga id.
# When the link doesn't name a segment we have a note for (see
# mdutils.rewrite_suttacentral_links_in_folder), we send it to the rule's note.
RULE_HREF_RE = re.compile(
  r"href=(['\"])https://suttacentral\.net/"
  r"(pli-tv-b[ui]-vb-[a-z]{2}\d+|B[ui] [A-Z][a-z] \d+)/en/brahmali/?(?:#([0-9.]*))?\1"
)
RULE_MENTION_RE = re.compile(r"\b(Bu|Bi) (Pj|Ss|Ay|Np|Pc|Pd|Sk) (\d+)\b")
ANCHOR_SPLIT_RE = re.compile(r"(<a\b.*?</a>)", re.DOTALL)
# The links in the translation itself ("To be expanded as in Kd 7:6.1.1") leave
# off the "/en/brahmali" that mdutils looks for when it rewrites the links
BARE_LINK_RE = re.compile(r"(https://suttacentral\.net/pli-tv-[\w-]+)(?=#)")


def complete_bare_links(html: str) -> str:
  """ "suttacentral.net/pli-tv-kd7#6.1.1" -> "suttacentral.net/pli-tv-kd7/en/brahmali#6.1.1" """
  return BARE_LINK_RE.sub(r"\1/en/brahmali", html)


def rule_uid_for_mention(sangha: str, rule_class: str, number: str) -> str:
  """("Bu", "Ss", "13") -> "pli-tv-bu-vb-ss13" """
  return f"pli-tv-{sangha.lower()}-vb-{rule_class.lower()}{number}"


def link_rule_mentions(
  note: str,
  href_for_rule: Callable[[str], Optional[str]],
  has_note_for_segment: Callable[[str], bool],
) -> str:
  """Points the Pātimokkha rules mentioned in `note` (html) at their notes.

  `href_for_rule` takes a rule's uid ("pli-tv-bu-vb-ss13") and returns the link
  to its note, or None if it hasn't got one. `has_note_for_segment` says whether
  a particular segment ("pli-tv-bu-vb-ss13:1.2.3") will be linked up later on."""
  def replace_href(match: re.Match) -> str:
    uid = match.group(2)
    if ' ' in uid: # A typo'd link such as "suttacentral.net/Bi Pc 12/en"
      uid = rule_uid_for_mention(*uid.split(' '))
    segment = (match.group(3) or '').rstrip('.')
    if segment and has_note_for_segment(f"{uid}:{segment}"):
      return f'href="https://suttacentral.net/{uid}/en/brahmali#{segment}"'
    href = href_for_rule(uid)
    if not href:
      return match.group(0)
    return f'href="{href}"'

  def replace_mention(match: re.Match) -> str:
    href = href_for_rule(rule_uid_for_mention(*match.groups()))
    if not href:
      return match.group(0)
    return f'<a href="{href}">{match.group(0)}</a>'

  parts = ANCHOR_SPLIT_RE.split(note)
  for i, part in enumerate(parts):
    if i % 2: # an existing <a> tag
      parts[i] = RULE_HREF_RE.sub(replace_href, part)
    else:
      parts[i] = RULE_MENTION_RE.sub(replace_mention, part)
  return "".join(parts)
