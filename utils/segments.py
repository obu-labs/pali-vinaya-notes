#!/bin/python3
"""Helpers for SuttaCentral's segment ids, such as "pli-tv-kd20:27.2.8" """


def segment_numbers(key: str) -> list[str]:
  """ "pli-tv-kd20:27.2.8" -> ['27', '2', '8'] """
  return key.split(':')[1].split('.')


def paragraph_of(key: str) -> list[str]:
  """The "paragraph" that the segment id says it's part of.

  pli-tv-kd20:27.2.8 is in ['27', '2'], as is pli-tv-kd15:16.1.11.2
  whereas pli-tv-kd16:7.5 is in ['7']."""
  numbers = segment_numbers(key)
  return numbers[:2] if len(numbers) > 2 else numbers[:1]


def first_number(key: str) -> str:
  """ "pli-tv-kd20:27.2.8" -> "27" """
  return segment_numbers(key)[0]
