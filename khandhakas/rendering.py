#!/bin/python3
"""Rendering the text of a note as markdown."""

from dataclasses import dataclass
from typing import Callable, Mapping, Optional, Sequence
import re

import markdownify

from utils.bilara import BilaraText
from utils.pali import split_words
from utils.text import join_phrases, strip_number_prefix

from .markup import (
  COUNTED_PARAGRAPH_RE,
  COUNTER_RE,
  LIST_ITEM_RE,
  is_end_marker,
  rule_tag,
)
from .rules import rule_end

# Stands in for the "\." of an escaped "1\." until after markdownify has run
NUMBER_DOT = ""
# Obsidian doesn't render definition lists, so we make do with paragraphs
DEFINITION_LIST_TAGS = {
  "<dl>": "", "</dl>": "",
  "<dt>": "<p><strong>", "</dt>": "</strong></p>",
  "<dd>": "<p>", "</dd>": "</p>",
}

# Takes a footnote's text and returns the marker for it
Footnoter = Callable[[str], str]


def _plain_comment(html: str) -> str:
  return markdownify.markdownify(html).strip()


def _no_variant_locations(words: list[str], key: str) -> None:
  return None


@dataclass(frozen=True)
class RenderOptions:
  # Renders one of the translator's notes (html) as markdown
  render_comment: Callable[[str], str] = _plain_comment
  # Takes the words of the Pāli at a segment id and returns which of them
  # its variant readings are for: {index of the word: [reading, variant]}
  # or None if it can't tell.
  locate_variants: Callable[[list[str], str], Optional[Mapping[int, Sequence[str]]]] = _no_variant_locations


def render_pali_line(text: BilaraText, key: str, footnote: Footnoter, options: RenderOptions) -> str:
  """Returns the Pāli at `key` with its variant readings footnoted"""
  words = split_words(text.pali(key))
  variant = text.variants.get(key)
  if not variant:
    line = " ".join(words)
  else:
    locations = options.locate_variants(words, key)
    if locations:
      line = " ".join(
        word + (footnote(" → ".join(locations[i])) if i in locations else "")
        for i, word in enumerate(words)
      )
    else:
      # We can't tell which word(s) this variant is about,
      # so the note just goes at the end of the line
      line = " ".join(words) + footnote(variant.strip())
  if "— " not in text.pali(key):
    line = line.replace("— ", "—") # undo the word splitting
  return line


def render_rule(
  text: BilaraText, keys: Sequence[str], tag: re.Match, footnote: Footnoter, options: RenderOptions,
) -> tuple[str, str, str, str]:
  """Returns (html before, Pāli lines, English, html after) for the rule at `keys`"""
  before = text.html[keys[0]].split('{}', 1)[0]
  after = text.html[keys[-1]].split('{}', 1)[1]
  pali = "<br>".join(
    render_pali_line(text, k, footnote, options) for k in keys if text.pali(k).strip()
  )
  english = []
  counter = COUNTER_RE.search(tag.group(0))
  if counter:
    english.append(f"({counter.group(1)})")
  for key in keys:
    line = text.en(key).strip()
    if key in text.comments:
      line += footnote(options.render_comment(text.comments[key]))
    if line:
      english.append(line)
  if tag.group(1) == 'p':
    # We replace the paragraph with our own blocks
    before = before.replace(tag.group(0), "")
    after = after.replace("</p>", "", 1)
  return (before, pali, join_phrases(english), after)


def lists_that_skip_numbers(html: Mapping[str, str], keys: Sequence[str]) -> set[int]:
  """Returns the indexes of the `keys` in ordered lists which have an <li value='N'>.

  Markdown lists can't skip numbers, so we have to number those ourselves."""
  ret: set[int] = set()
  start: Optional[int] = None
  depth = 0
  skips = False
  for i, key in enumerate(keys):
    template = html[key]
    if depth == 0 and '<ol>' in template:
      start = i
      skips = False
    depth += template.count('<ol>') - template.count('</ol>')
    if start is not None:
      skips = skips or "<li value='" in template
      if depth <= 0:
        if skips:
          ret.update(range(start, i + 1))
        start = None
    depth = max(depth, 0)
  return ret


def render_segments(
  text: BilaraText, keys: Sequence[str], options: RenderOptions = RenderOptions(),
) -> tuple[str, list[str]]:
  """Returns the (markdown, footnotes) for the text at `keys`

  The rules get their Pāli in a blockquote followed by the English in bold.
  Everything else is just the translation."""
  footnotes: list[str] = []
  def footnote(note: str) -> str:
    footnotes.append(note)
    return f"[^{len(footnotes)}]"

  skipping_lists = lists_that_skip_numbers(text.html, keys)
  item_number = 0
  def number_item(item: re.Match) -> str:
    nonlocal item_number
    item_number = int(item.group(1)) if item.group(1) else item_number + 1
    return f"<p>{item_number}{NUMBER_DOT} "

  html: list[str] = []
  previous_rule: Optional[int] = None # where in `html` the rule just before this is
  i = 0
  while i < len(keys):
    key = keys[i]
    template = text.html[key]
    tag = rule_tag(template)
    if tag:
      end = rule_end(text.html, keys, i, tag)
      before, pali, english, after = render_rule(text, keys[i:end + 1], tag, footnote, options)
      i = end + 1
      if pali and not english and previous_rule is not None:
        # The translation of this rule was combined with the previous one's
        html[previous_rule] = html[previous_rule].replace(
          "</blockquote>", f"<br>{pali}</blockquote>", 1,
        )
        html.append(before + after)
        continue
      previous_rule = len(html) if pali else None
      if pali:
        before += f"<blockquote>{pali}</blockquote>"
      if english:
        before += f"<p><strong>{english}</strong></p>"
      html.append(before + after)
      continue
    previous_rule = None
    line = text.en(key)
    if key in text.comments:
      line = line.rstrip() + footnote(options.render_comment(text.comments[key])) + " "
    if line.strip() and is_end_marker(template):
      line = f"<em>{line.strip()}</em>"
    if COUNTED_PARAGRAPH_RE.search(template):
      # SuttaCentral numbers some paragraphs in the margin. Those numbers skip
      # ahead and run across our notes, so we can't make markdown lists of them.
      next_block = next((
        text.html[k] for k in keys[i + 1:] if text.html[k].startswith('<')
      ), '')
      # Sometimes the "1" is on the paragraph introducing a numbered list
      number = "" if next_block.startswith('<ol>') else r"(\1) "
      template = COUNTED_PARAGRAPH_RE.sub("<p>" + number, template)
    if i in skipping_lists:
      if '<ol>' in template:
        item_number = 0
      template = LIST_ITEM_RE.sub(number_item, template).replace("</li>", "</p>")
      template = template.replace("<ol>", "").replace("</ol>", "")
    if "<span class='pe'>" in template:
      # An editorial note such as "(to be expanded as above)"
      template = template.replace("<span class='pe'>", "<em>").replace("</span>", "</em>")
    for old, new in DEFINITION_LIST_TAGS.items():
      template = template.replace(old, new)
    if i == 0:
      # No need for a line across the top of the note
      template = template.replace("<hr>", "", 1)
    if "class='verse-line'" in template:
      line = line.strip()
      if template.endswith("</span>"):
        template += "<br>"
    html.append(template.replace('{}', line))
    i += 1
  markdown = markdownify.markdownify("".join(html)).strip()
  markdown = markdown.replace(NUMBER_DOT, "\\.")
  return (re.sub(r"\n{3,}", "\n\n", markdown), footnotes)


def render_heading(text: BilaraText, key: Optional[str]) -> str:
  """Returns the markdown for the heading at `key`: the English, then the Pāli.

  Our files are numbered by where they are in the folder, which often isn't the
  (English) heading's number. The Pāli headings keep their traditional numbers."""
  if not key:
    return ""
  heading = strip_number_prefix(markdownify.markdownify(text.en(key)).strip())
  pali = text.pali(key).strip()
  if not heading:
    return f"## {pali}\n\n" if pali else ""
  ret = f"## {heading}\n"
  if pali:
    ret += f"\n*{pali}*\n"
  return ret + "\n"
