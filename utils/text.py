#!/bin/python3
"""Helpers for plain text, titles and filenames."""

from functools import reduce
from typing import Collection, Iterable
import re

from unidecode import unidecode

TAG_RE = re.compile(r"<[^>]+>")
# e.g. "3. ", "14.1. " or "17–18. "
NUMBER_PREFIX_RE = re.compile(r"^\d+([.–-]\d+)*\.\s+")
SENTENCE_END_RE = re.compile(r"[.?!][”’]*(?=\s|$)")
ENDS_SENTENCE_RE = re.compile(r"[.?!][”’]*$")
PARAGRAPH_BREAK_RE = re.compile(r"\n\s*\n")
# Not a good look at the end of a truncated title
TRAILING_WORDS = frozenset({
  'a', 'an', 'the', 'of', 'to', 'as', 'and', 'or', 'in', 'for', 'with', 'at',
  'by', 'on', 'who', 'that', 'is', 'are', 'be', 'if', 'but', 'from', 'when',
  'which', 'has', 'have', 'not', 'was', 'were', 'than', 'into',
})


def plain_text(html: str) -> str:
  """Strips the tags and extra whitespace out of `html`"""
  return re.sub(r"\s+", " ", TAG_RE.sub("", html)).strip()


def strip_number_prefix(title: str) -> str:
  """ "17–18. The account of Ambapālī" -> "The account of Ambapālī" """
  return NUMBER_PREFIX_RE.sub("", title)


def ends_sentence(text: str) -> bool:
  return bool(ENDS_SENTENCE_RE.search(text))


def first_sentence(text: str, min_length: int = 12) -> str:
  """Returns `text` up to (not including) the end of its first sentence,
  unless that would leave fewer than `min_length` characters."""
  end = SENTENCE_END_RE.search(text)
  if end and end.start() >= min_length:
    return text[:end.start()]
  return text


def append_phrase(text: str, phrase: str) -> str:
  """Adds `phrase` to `text` with a space, unless `text` ends with a dash"""
  if text.endswith("—"):
    return text + phrase
  return f"{text} {phrase}".strip()


def join_phrases(phrases: Iterable[str]) -> str:
  return reduce(append_phrase, phrases, "")


def filename_title(
  text: str,
  max_length: int,
  trailing_words: Collection[str] = TRAILING_WORDS,
) -> str:
  """Turns a bit of text into something safe to use in a filename and a link.

  Titles longer than `max_length` are cut off at the end of a word
  (and not at one of the `trailing_words`)."""
  text = unidecode(plain_text(text))
  text = re.sub(r"(?<=\d)\.(?=\d)", "\0", text) # keep any decimal points
  text = re.sub(r"\s*(?:--|[:;])\s*", ", ", text)
  text = re.sub(r"[^A-Za-z0-9 ,'()\0-]", "", text)
  text = re.sub(r"\s+", " ", text)
  text = re.sub(r"(?:\s*,)+", ",", text).strip(" ,-'")
  if len(text) > max_length:
    words = text[:max_length + 1].split(" ")[:-1]
    while len(words) > 1 and words[-1].strip(",-'").lower() in trailing_words:
      words.pop()
    text = " ".join(words).rstrip(" ,-'")
  return text.replace("\0", ".") or "Untitled"


def indent_later_paragraphs(markdown: str, indent: str = "    ") -> str:
  """Indents every paragraph after the first, which is what it takes
  to keep them all inside of the one markdown footnote or list item."""
  return PARAGRAPH_BREAK_RE.sub("\n\n" + indent, markdown)
