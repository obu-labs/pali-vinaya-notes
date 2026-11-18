#!/bin/python3
"""Finding the rules (the html marked class='rule') and comparing them."""

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence
import re

from utils.bilara import BilaraText
from utils.pali import word_parts

from .markup import rule_tag


@dataclass(frozen=True)
class RuleIndex:
  """What we need to know about a chapter's rules to tell if two of them are related"""
  # Every segment that's part of a rule
  rule_keys: frozenset[str] = frozenset()
  # Words like "bhikkhave", "āpatti" or (in the robes chapter) "cīvaraṁ"
  # show up in too many rules to say anything about what a rule is about
  common_word_parts: frozenset[str] = frozenset()


def rule_end(html: Mapping[str, str], keys: Sequence[str], start: int, tag: re.Match) -> int:
  """Returns the index in `keys` of the last segment of the rule starting at `start`"""
  closing_tag = f"</{tag.group(1)}>"
  end = start
  while closing_tag not in html[keys[end]].split('{}', 1)[1] and end < len(keys) - 1:
    end += 1
  return end


def find_rules(html: Mapping[str, str], keys: Sequence[str]) -> list[list[str]]:
  """Returns the segments of each rule in `keys`"""
  rules: list[list[str]] = []
  i = 0
  while i < len(keys):
    tag = rule_tag(html[keys[i]])
    if not tag:
      i += 1
      continue
    end = rule_end(html, keys, i, tag)
    rules.append(list(keys[i:end + 1]))
    i = end + 1
  return rules


def _pali_of(text: BilaraText, keys: Iterable[str]) -> str:
  return " ".join(text.pali(key) for key in keys)


def index_rules(text: BilaraText) -> RuleIndex:
  rules = find_rules(text.html, text.keys)
  counts = Counter(
    part for rule in rules for part in word_parts(_pali_of(text, rule))
  )
  return RuleIndex(
    rule_keys=frozenset(key for rule in rules for key in rule),
    common_word_parts=frozenset(
      part for part, count in counts.items() if count > max(3, len(rules) // 30)
    ),
  )


def rules_share_a_word(
  text: BilaraText, index: RuleIndex, keys: Iterable[str], other_keys: Iterable[str],
) -> bool:
  """Do the rules in `keys` and `other_keys` have a distinctive word (or part of a compound) in common?"""
  rules = _pali_of(text, (k for k in keys if k in index.rule_keys))
  other_rules = _pali_of(text, (k for k in other_keys if k in index.rule_keys))
  in_common = (word_parts(rules) & word_parts(other_rules, only_starts=True)) \
    | (word_parts(rules, only_starts=True) & word_parts(other_rules))
  return bool(in_common - index.common_word_parts)
