"""Shorthand for making up little texts to test with."""

from utils.bilara import BilaraText
from utils.pali import word_parts

from khandhakas.rules import RuleIndex, index_rules

UID = "pli-tv-kd99"
P = "<p>{}</p>"
RULE = "<p class='rule'>{}</p>"
H2 = "<h2>{}</h2>"
H3 = "<h3>{}</h3>"
# How the Pāli opens a new story ("At that time...")
FRESH = "Tena kho pana samayena"


def keys(*numbers: str) -> list[str]:
  """keys("1.1", "1.2") -> ["pli-tv-kd99:1.1", "pli-tv-kd99:1.2"]"""
  return [f"{UID}:{number}" for number in numbers]


def make_json(*rows: tuple) -> dict:
  """Returns what SuttaCentral's API would for a text with a segment for each of `rows`.

  Each row is (segment number, html, English, Pāli, comment, variant)
  with everything after the html being optional."""
  data = {
    'keys_order': [], 'html_text': {}, 'translation_text': {},
    'root_text': {}, 'comment_text': {}, 'variant_text': {},
  }
  for number, html, *rest in rows:
    key = f"{UID}:{number}"
    data['keys_order'].append(key)
    data['html_text'][key] = html
    for field, value in zip(['translation_text', 'root_text', 'comment_text', 'variant_text'], rest + [""] * 4):
      data[field][key] = value
  return data


def make_text(*rows: tuple) -> BilaraText:
  return BilaraText.from_json(make_json(*rows))


def rules_of(text: BilaraText, common_words: str = "") -> RuleIndex:
  """Indexes the rules in `text`, taking our word for which words are too common to count"""
  return RuleIndex(
    rule_keys=index_rules(text).rule_keys,
    common_word_parts=frozenset(word_parts(common_words)),
  )
