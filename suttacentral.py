#!/bin/python3

from collections import deque
from pathlib import Path
from typing import Optional
import requests
import re
import os
import json

import joblib
from unidecode import unidecode
import markdownify

from vnmutils.paliutils import (
  match_terms_to_root_text,
  pali_stem,
  sanitize,
)
from vnmutils.mdutils import (
  full_obsidian_style_link_for_scuid,
  SCUID_SEGMENT_PATHS,
  abs_path_to_obsidian_link_text,
  superscript_number,
)

ROOT_FOLDER = Path(os.path.dirname(__file__))
DATA_FOLDER = ROOT_FOLDER.joinpath('data')
CACHE_FOLDER = DATA_FOLDER.joinpath('.cache')
RULENAMES_FILE = DATA_FOLDER.joinpath('rulenames.json')
RULENAMES = json.load(RULENAMES_FILE.open('rt', encoding='utf-8'))

BRAHMALI_GLOSSARY_FILE = DATA_FOLDER.joinpath('brahmali_glosses.json')

SUDDHASO_FILES_FILE = DATA_FOLDER.joinpath('suddhaso_vibhanga.json')
SUDDHASO_FILES = json.load(SUDDHASO_FILES_FILE.open('rt', encoding='utf-8'))

disk_memoizer = joblib.Memory(
  CACHE_FOLDER,
  verbose=0,
)

# MUST BE CALLED BEFORE RENDER FUNCTIONS
def set_global_folders(pali_path: Path):
  global HYPOTHETICAL_VAULT_ROOT
  global BRAHMALI_GLOSSARY
  global PM_FOLDER
  global VB_FOLDER
  global KD_FOLDER
  global VB_WORD_DEFS_FOLDER

  PALI_FOLDER = pali_path
  HYPOTHETICAL_VAULT_ROOT = pali_path.parent
  BRAHMALI_GLOSSARY = {
    root: HYPOTHETICAL_VAULT_ROOT.joinpath(relpath)
    for root, relpath in
    json.load(BRAHMALI_GLOSSARY_FILE.open('rt', encoding='utf-8')).items()
  }
  PM_FOLDER = PALI_FOLDER.joinpath('Patimokkha')
  VB_FOLDER = PALI_FOLDER.joinpath('Vibhanga')
  KD_FOLDER = PALI_FOLDER.joinpath('Khandhaka')
  VB_WORD_DEFS_FOLDER = VB_FOLDER.joinpath('Word Analysis')
  VB_WORD_DEFS_FOLDER.mkdir(exist_ok=True, parents=True)
  PM_FOLDER.mkdir()

def vb_folder_for_scid(scid: str) -> Path:
  return _rule_path_for_scid(scid, '', VB_FOLDER)

def pm_file_for_scid(scid: str) -> Path:
  return _rule_path_for_scid(scid, '.md', PM_FOLDER)

def pm_file_for_copied_bi_rule(pm_id: str, rule_name: str) -> Path:
  return _rule_path_for_scid(pm_id.replace('-pm-', '-vb-'), '.md', PM_FOLDER, rule_name)

def file_for_category(category: dict) -> Path:
  ret = _rule_dir_for_scid(category['uid'], VB_FOLDER)
  sangha = "Bhikkhu"
  if '-bi-' in category['uid']:
    sangha = "Bhikkhunī"
  return ret / f"The {sangha} {category['root_name']}s.md"

def pm_file_for_as(category_uid: str) -> Path:
  if category_uid.startswith('pli-tv-bu-'):
    return PM_FOLDER / 'Bhikkhu' / '8 - Adhikaranasamatha.md'
  elif category_uid.startswith('pli-tv-bi-'):
    return PM_FOLDER / 'Bhikkhuni' / '7 - Adhikaranasamatha.md'
  raise ValueError(f"Unknown as category uid \"{category_uid}\"")

def pm_file_for_nigamana(category_uid: str) -> Path:
  if category_uid.startswith('pli-tv-bu-'):
    return PM_FOLDER / 'Bhikkhu' / '9 - Nigamana.md'
  elif category_uid.startswith('pli-tv-bi-'):
    return PM_FOLDER / 'Bhikkhuni' / '8 - Nigamana.md'
  raise ValueError(f"Unknown as category uid \"{category_uid}\"")

def _rule_dir_for_scid(scid: str, base: Path):
  ret = base
  offset = 0
  if scid.startswith('pli-tv-bu-vb-'):
    ret = ret / 'Bhikkhu'
  elif scid.startswith('pli-tv-bi-vb-'):
    ret = ret / 'Bhikkhuni'
    if scid[13:15] not in ['pj', 'ss']:
      offset = -1
  else:
    raise ValueError(f"Unknown vb scid \"{scid}\"")
  match scid[13:15]:
    case 'pj':
      ret = ret / '1 - Parajika'
    case 'ss':
      ret = ret / '2 - Sanghadisesa'
    case 'ay':
      ret = ret / '3 - Aniyata'
    case 'np':
      ret = ret / f'{4+offset} - Nissaggiya Pacittiya'
    case 'pc':
      ret = ret / f'{5+offset} - Pacittiya'
    case 'pd':
      ret = ret / f'{6+offset} - Patidesaniya'
    case 'sk':
      ret = ret / f'{7+offset} - Sekhiya'
    case 'as':
      ret = ret / f'{8+offset} - Adhikaranasamatha'
    case _:
      raise ValueError(f"Unknown rule class \"{scid[13:15]}\"")
  return ret

def _rule_path_for_scid(scid: str, suffix: str, base: Path, rule_name: Optional[str] = None) -> Path:
  scid = scid.split(':')[0]
  ret = _rule_dir_for_scid(scid, base)
  if not rule_name:
    rule_name = RULENAMES[scid]
  return ret / f"{scid[7:9].capitalize()} {scid[13:15].capitalize()} {scid[15:]} ({rule_name}){suffix}"

def find_sub_list(sl:list, l:list, start=0) -> int:
    sll = len(sl)
    end = len(l) - sll
    assert sll > 0 and end >= 0
    for i in range(start, end+1):
      if l[i] != sl[0]:
        continue
      if l[i:i+sll]==sl:
        return i
    raise ValueError(f"Sublist {sl} not found in list {l}")

# Note: Currently only supports Ajahn Brahmali's Pali Vinaya translation
BILARA_URL = "https://suttacentral.net/api/bilarasuttas/{}/brahmali?lang=en"
SC_MENU_URL = "https://suttacentral.net/api/menu/{}?language=en"
PARALLELS_URL = "https://suttacentral.net/api/parallels/{}"
LITE_PARALLELS_URL = "https://suttacentral.net/api/parallels_lite/{}"

def sc_link_for_ref(ref: str, doc_id: Optional[str] = None) -> str:
  if doc_id:
    return (f"https://suttacentral.net/{doc_id}/en/brahmali?"
      "layout=linebyline" # IMPORTANT See note below before changing
      f"#{ref}")
  key = ref.split(':')
  return (f"https://suttacentral.net/{key[0]}/en/brahmali?"
    "layout=linebyline" # IMPORTANT See note below before changing
    f"#{key[1]}")
  # This returns the link with the linebyline layout specified
  # mdutils.rewrite_suttacentral_links_in_folder() will rewrite all links in
  # the naked "/en/brahmali#segment" style as it assumes all links in that
  # format are from the original comment_text or Appendix text.
  # Links in other formats (such as that returned above) will not be rewritten.

# Some terms are defining terms in the definition
# rather than terms in the original rule
# This mapping groups those definitions together under the main term
MANUAL_DEFINITION_RANGES = {
  "pli-tv-bu-vb-np19:2.5": "pli-tv-bu-vb-np19:2.12",
  "pli-tv-bu-vb-np22:2.1.5": "pli-tv-bu-vb-np22:2.1.10",
  "pli-tv-bu-vb-pc4:2.1.7": "pli-tv-bu-vb-pc4:2.1.18",
  "pli-tv-bu-vb-pc7:4.1.14": "pli-tv-bu-vb-pc7:4.1.17",
  "pli-tv-bu-vb-pc10:2.1.5": "pli-tv-bu-vb-pc10:2.1.14",
  "pli-tv-bu-vb-pc11:2.1.1": "pli-tv-bu-vb-pc11:2.1.12",
  "pli-tv-bu-vb-pc47:2.1.7": "pli-tv-bu-vb-pc47:2.1.19",
  "pli-tv-bu-vb-pc51:2.1.1": "pli-tv-bu-vb-pc51:2.1.6",
  "pli-tv-bu-vb-pc54:2.1.1": "pli-tv-bu-vb-pc54:2.1.6",
  "pli-tv-bu-vb-pc59:2.1.19": "pli-tv-bu-vb-pc59:2.1.27",
  "pli-tv-bu-vb-pc69:2.1.13": "pli-tv-bu-vb-pc69:2.1.19",
  "pli-tv-bu-vb-pc70:2.1.30": "pli-tv-bu-vb-pc70:2.1.37",
  "pli-tv-bu-vb-pc83:2.1.15": "pli-tv-bu-vb-pc83:2.1.18",
  "pli-tv-bi-vb-np1:2.1.5": "pli-tv-bi-vb-np1:2.1.14",
  "pli-tv-bi-vb-pc4:2.1": "pli-tv-bi-vb-pc4:2.4",
}

# Replace the root text at these segments entirely
ROOT_TEXT_OVERRIDES = {
  "pli-tv-bi-vb-np10:2.3": "bhikkhunīti",
  "pli-tv-bi-vb-np10:2.4": "…pe… ayaṁ imasmiṁ atthe adhippetā bhikkhunīti.",
}

# In the word definitions, some terms are defined as "...pe..."
# This list maps those terms to their definitions at scuid
PE_REFERENCES = [
  {
    'filepath_contains': ' Bu ',
    'term': 'Yo panāti',
    'scuid': 'pli-tv-bu-vb-pj1:8.1.1'
  },
  {
    'filepath_contains': ' Bu ',
    'term': ['Bhikkhūti', 'bhikkhūti'],
    'scuid': 'pli-tv-bu-vb-pj1:8.1.3'
  },
  {
    'filepath_contains': ' Bu ',
    'term': 'Saṅghādisesoti',
    'scuid': 'pli-tv-bu-vb-ss1:2.2.10'
  },
  {
    'filepath_contains': ' Bi ',
    'term_startswith': 'Yā panāti',
    'scuid': 'pli-tv-bi-vb-pj5:2.1.1'
  },
  {
    'filepath_contains': ' Bi ',
    'term': ['bhikkhunīti', 'Bhikkhunīti'],
    'scuid': 'pli-tv-bi-vb-pj5:2.1.3'
  },
  {
    'filepath_contains': ' Bi ',
    'term': 'Saṅghādisesoti',
    'scuid': 'pli-tv-bi-vb-ss1:2.1.25'
  }
]

NOTES_NEEDING_MULTIPLE_LINKS = [
  " as “standard” and ", # BiPc22, BiPc26, BiNp3
  " the renderings “cooked food” for ", # BiSs5
  " and the rendering of ", # BuPc25
]

# After the "Final Ruling" these Origin Stories keep going, describing
# an allowance that was made after the rule. We render these separately.
ALLOWANCE_STORIES = {
  'pli-tv-bu-vb-pc14': 'pli-tv-bu-vb-pc14:1.2.0',
  'pli-tv-bu-vb-pc21': 'pli-tv-bu-vb-pc21:2.0',
  'pli-tv-bu-vb-pc33': 'pli-tv-bu-vb-pc33:4.0',
}

COMMENT_INLINE_PALI = re.compile(r"<i lang=['\"]pi['\"] translate=['\"]no['\"]>(.*?)<\/i>")

@disk_memoizer.cache()
def get_rule_categories(scid):
  r = requests.get(SC_MENU_URL.format(scid))
  return r.json()[0]['children']

@disk_memoizer.cache()
def get_rules_for_category(category_uid: str) -> list[dict]:
  r = requests.get(SC_MENU_URL.format(category_uid))
  return r.json()[0]['children']

@disk_memoizer.cache()
def get_rule_meta(rule_id: str) -> dict:
  r = requests.get(SC_MENU_URL.format(rule_id))
  return r.json()[0]

@disk_memoizer.cache()
def get_lite_parallels(scid: str) -> list:
  r = requests.get(LITE_PARALLELS_URL.format(scid))
  return r.json()

def get_bhikkhuni_rules_in_category(category_uid: str) -> list:
  all_parallels = get_lite_parallels('pli-tv-bi-pm')
  return [rule for rule in all_parallels if rule['uid'].startswith(category_uid)]

@disk_memoizer.cache(cache_validation_callback=joblib.expires_after(days=14))
def get_vb_json(rule_id: str) -> dict:
  r = requests.get(BILARA_URL.format(rule_id))
  return r.json()

def clean_vb_json(data: dict) -> dict:
  """Removes empty comments and empty variants that SuttaCentral returns for segments without entries."""
  if 'comment_text' in data:
    data['comment_text'] = {k: v for k, v in data['comment_text'].items() if v and v.strip()}
  if 'variant_text' in data:
    data['variant_text'] = {k: v for k, v in data['variant_text'].items() if v and v.strip()}
  return data

def get_keys_where_html_contains(vb_json: dict, text: str) -> list[str]:
  return get_keys_where_text_contains(vb_json, 'html_text', text)

def get_key_where_translation_contains(vb_json: dict, text: str) -> str:
  ret = get_keys_where_text_contains(vb_json, 'translation_text', text)
  if len(ret) > 1:
    raise Exception(f"Multiple matches found for {text}: {ret}")
  return ret[0]

def get_key_where_roottext_contains(vb_json: dict, text: str) -> str:
  ret = get_keys_where_text_contains(vb_json, 'root_text', text)
  if len(ret) > 1:
    raise Exception(f"Multiple matches found for {text}: {ret}")
  return ret[0]

def get_keys_where_text_contains(vb_json: dict, text_type: str, text: str) -> list[str]:
  stext = text.casefold() # case insensitive search
  keys = [
    k
    for k in vb_json[text_type]
    if stext in vb_json[text_type][k].casefold()
  ]
  if len(keys) == 0:
    keys = vb_json["keys_order"]
    raise ValueError(f'No match for {text} found in {keys[0]} through {keys[-1]}')
  return keys

def get_definition_refs_from_vb_json(vb_json: dict) -> list[tuple[str, list[str]]]:
  """ Returns a list of tuples in the form: (term_key, [definition_keys])
  """
  keys = get_keys_where_html_contains(vb_json, "<section class='padabhajaniya'><h2")
  ret = list()
  # We have to do this because BuPc71 has two definition sections >.<
  for key in keys:
    ret.extend(get_definition_section_from_vb_json(vb_json, key))
  # HACKS: Swap terms that are out of order in the root text
  if len(ret) > 12 and ret[12][0] in ['pli-tv-bu-vb-ss4:2.26', "pli-tv-bu-vb-np29:2.26"]:
    ret[12], ret[11] = ret[11], ret[12]
  if ret[0][0] == "pli-tv-bu-vb-pc24:2.1.1":
    ret[2], ret[3] = ret[3], ret[2]
  if ret[0][0] == "pli-tv-bu-vb-pc81:2.1.1":
    ret.insert(5, ret[8]) # In Pc81
    del ret[9] # move the ninth item back to position six
  if ret[0][0] == "pli-tv-bu-vb-pc84:4.1.1":
    del ret[4] # doesn't add anything: just messes up later terms
  if len(ret) > 7 and ret[7][0] == "pli-tv-bi-vb-pc8:2.1.15":
    ret[7], ret[8] = ret[8], ret[7]
  return ret

def get_definition_section_from_vb_json(vb_json: dict, key: str) -> list[tuple[str, list[str]]]:
  if 'Definitions' not in vb_json['translation_text'][key]:
    raise Exception(f'Why is {key} not a definition section?')
  key_spot = vb_json['keys_order'].index(key)
  ret = []
  while '</section>' not in vb_json['html_text'][key]:
    key_spot += 1
    key = vb_json['keys_order'][key_spot]
    if '<dt>{}' not in vb_json['html_text'][key]:
      # We've reached the end of the definitions
      #  even if we haven't hit the </section> yet
      break
    while '</dt>' not in vb_json['html_text'][key]:
      print(f"      (Trimming long keyterm at {key})")
      key_spot += 1
      key = vb_json['keys_order'][key_spot]
    term_key = key
    definition_keys = []
    if term_key in MANUAL_DEFINITION_RANGES:
      final_key = MANUAL_DEFINITION_RANGES[term_key]
      while key != final_key:
        key_spot += 1
        key = vb_json['keys_order'][key_spot]
        definition_keys.append(key)
    else: # In the usual case
      while '</dd>' not in vb_json['html_text'][key]:
        key_spot += 1
        key = vb_json['keys_order'][key_spot]
        definition_keys.append(key)
      if '<dd>' not in vb_json['html_text'][definition_keys[0]]:
        if '<dt>' in vb_json['html_text'][definition_keys[0]]:
          print(f"      WARNING: Skipping undefined term {vb_json['html_text'][term_key].format(vb_json['root_text'][term_key])} at {term_key}")
          key = term_key
          key_spot = vb_json['keys_order'].index(key)
          continue
        else:
          raise Exception(f"Unexpected html at {term_key} + 1: {vb_json['html_text'][definition_keys[0]]}")
    ret.append((term_key, definition_keys))
  return ret

def get_final_ruling_refs_from_vb_json(vb_json: dict) -> list[str]:
  key = get_key_where_translation_contains(vb_json, 'Final ruling')
  key = key[:-1] + '1'
  keys = [key]
  if "<p class='rule'" not in vb_json['html_text'][key]:
    raise Exception(f'Why is {key} not a rule paragraph?')
  key_spot = vb_json['keys_order'].index(key)
  while '</p>' not in vb_json['html_text'][key]:
    key_spot += 1
    key = vb_json['keys_order'][key_spot]
    keys.append(key)
  return keys

def _get_root_text(vb_json: dict, k: str) -> list[str]:
  if k in ROOT_TEXT_OVERRIDES:
    return ROOT_TEXT_OVERRIDES[k].split()
  return vb_json['root_text'][k].replace('—', '— ').split()

def get_root_text(vb_json: dict, keys: list[str]) -> list[list[str]]:
  """Returns each key's root text split by word."""
  return [_get_root_text(vb_json, k) for k in keys]

def do_locs_overlap(loc1: tuple[int, int, int], loc2: tuple[int, int, int]) -> bool:
  if loc1[0] != loc2[0]:
    return False
  if loc1[1] > loc2[1]:
    loc1, loc2 = loc2, loc1
  if loc1[2] < loc2[1]:
    return False
  return True

def path_to_suddhaso_file_starting_with(file_prefix: str) -> Optional[Path]:
  for file in SUDDHASO_FILES:
    if file['name'].startswith(file_prefix):
      return HYPOTHETICAL_VAULT_ROOT / 'Bhante Suddhaso' / file['path']
  return None

PREVIOUSLY_WRITTEN_FILES = set()

def write_md_file(
  rule_file: Path,
  start_scuid: str,
  end_scuid: str | None,
  content: str,
  extra_aliases: Optional[list[str]] = None,
) -> None:
  rule_file.parent.mkdir(exist_ok=True, parents=True)
  aliases = start_scuid
  if end_scuid and end_scuid != start_scuid:
    aliases += f"\n  - {end_scuid}"
  if extra_aliases:
    for alias in extra_aliases:
      aliases += f"\n  - {alias}"
  fname = str(rule_file.stem).lower()
  if fname in PREVIOUSLY_WRITTEN_FILES:
    raise Exception(f"ERROR: We already wrote a file named {fname}")
  PREVIOUSLY_WRITTEN_FILES.add(fname)
  rule_file.write_text(f"""---
aliases:
  - {aliases}
---
{content}

[^WARNING]: DO NOT MODIFY. To add your thoughts, create a new note and link to this one. Found a problem? [Open an issue on GitHub](https://github.com/obu-labs/pali-vinaya-notes/issues/).
""")
  SCUID_SEGMENT_PATHS.add(start_scuid, end_scuid, rule_file)

def render_word_definitions(vb_json: dict, root_text: list[list[str]]) -> list[tuple[tuple[int, int, int], Path]]:
  """Renders the Vibhanga's word definitions to files.

  Args:
    vb_json (dict): The Vibhanga's json data for this rule.
    root_text (list[list[str]]): The root text split by line and by word.
  
  Returns a list of tuples in the form:
    (term_index, filepath)
  Where term_index is a tuple in the form:
    (line_number, start_word_index, end_word_index)
  And the filepath is the absolute Path to the rendered file.
  """
  definition_refs = get_definition_refs_from_vb_json(vb_json)
  scuid = vb_json['keys_order'][0].split(":")[0].split('-')
  rule_name = " ".join([
    scuid[2].capitalize(),
    scuid[4][0:2].capitalize(),
    scuid[4][2:],
  ])
  terms = get_root_text(vb_json, [d[0] for d in definition_refs])
  term_locations = match_terms_to_root_text(terms, root_text)
  unique_locs = []
  for loc in term_locations:
    if not (unique_locs and do_locs_overlap(loc, unique_locs[-1])):
      unique_locs.append(loc)
  grouped_definitions = {
    loc: [definition_refs[i] for i, loc2 in enumerate(term_locations) if do_locs_overlap(loc, loc2)]
    for loc in unique_locs
  }
  # Sometimes there are multiple occurrences of the same phrase in a rule
  # and each can have a different definition. This numbers them appropriately.
  root_phrases = {}
  seen_phrases = {}
  for loc in unique_locs:
    root_phrase = root_text[loc[0]][loc[1]:(loc[2]+1)]
    root_phrase = ' '.join([sanitize(w, lower=True) for w in root_phrase])
    if root_phrase in seen_phrases:
      n = seen_phrases[root_phrase]
      if n == 2:
        first_occurrence = [l for l in root_phrases.keys() if root_phrases[l] == root_phrase][0]
        root_phrases[first_occurrence] = f"{root_phrase} (1)"
      root_phrase = f"{root_phrase} ({n})"
      seen_phrases[root_phrase] = n + 1
    else:
      seen_phrases[root_phrase] = 2
    root_phrases[loc] = root_phrase
  ret = []
  for loc in unique_locs:
    definitions = grouped_definitions[loc]
    root_phrase = root_phrases[loc]
    filepath = VB_WORD_DEFS_FOLDER.joinpath(f"{root_phrase} - {rule_name} Definition.md")
    ret.append((loc, filepath))
    # resplit the definitions that were manually merged for the sake of the matching algo
    i = 0
    while i < len(definitions):
      term_key, definition_keys = definitions[i]
      if term_key not in MANUAL_DEFINITION_RANGES:
        i += 1
        continue
      for j in range(len(definition_keys)):
        if '<dt>{}' in vb_json['html_text'][definition_keys[j]]:
          definitions.insert(i+1, (definition_keys[j], definition_keys[j+1:]))
          del definitions[i][1][j:]
          break
      i += 1
    render_word_definition_file(filepath, definitions, vb_json)
  return ret

def build_variant_map(line: list[str], key: str, vb_json: dict) -> dict[int, list[str]]:
  """Given a `line` of Pali words at `key` in `vb_json`, return a map from word indexes to variant_text."""
  variant_map = {}
  if key in vb_json.get('variant_text', {}):
    variant_raw = vb_json['variant_text'][key].strip()
    if not variant_raw:
      return {}
    sanitized_line = [sanitize(w) for w in line]
    line_variants = variant_raw.replace(' | ', '; ').split("; ")
    list_variants = []
    for line_variant in line_variants:
      if ' → ' in line_variant:
        list_variants.append(line_variant)
      else:
        list_variants[-1] += "; " + line_variant
    list_variants = [vs.split(" → ") for vs in list_variants]
    location_of_variant = 0
    for v in list_variants:
      assert len(v) == 2, f"Expected {key} variant to have two parts, got {v}"
      if key == "pli-tv-bi-vb-pj6:1.23.1" and v[0] == 'ti':
        v[0] = "vajjappaṭicchādikā"
      try:
        location_of_variant = find_sub_list([sanitize(w) for w in v[0].replace('—', '— ').split()], sanitized_line)
      except ValueError:
        raise Exception(f"Couldn't find \"{v[0]}\" in \"{line}\" at {key}")
      variant_map[location_of_variant] = v
  return variant_map

def _render_translation_line(text: str) -> str:
  """Converts inline HTML (e.g. <i lang='pi'>) in a translation segment to Markdown."""
  return markdownify.markdownify(text).strip()

def _render_footnotes(footnotes: list[str], heading: str = "Footnotes") -> str:
  if not footnotes:
    return ""
  ret = f"\n## {heading}\n"
  for i, footnote in enumerate(footnotes):
    ret += f"\n[^{i + 1}]: {footnote}\n"
  return ret

def render_word_definition_file(filepath: Path, definitions: list[tuple[str, list[str]]], vb_json: dict):
  def apply_pe_references(term: str, definition: str) -> str:
    """Apply special case pe replacements based on filepath and term."""
    if definition.count("…pe…") != 1:
      return definition
    for case in PE_REFERENCES:
      if case['filepath_contains'] not in filepath.stem:
        continue
      term_match = False
      if 'term' in case:
        term_list = case['term'] if isinstance(case['term'], list) else [case['term']]
        term_match = term in term_list
      elif 'term_startswith' in case:
        term_match = term.startswith(case['term_startswith'])
      if term_match:
        replacement = f"[…pe…{abs_path_to_obsidian_link_text(SCUID_SEGMENT_PATHS.get(case['scuid']), filepath.parent)}"
        return definition.replace("…pe…", replacement)
    return definition
  
  def render_section(section_term_key: str, section_dd_keys: list[str]) -> str:
    """Render one ## Pali (English) + blockquote + translation + link section."""
    nonlocal footnotes
    term = vb_json['root_text'][section_term_key].strip()
    root_text = get_root_text(vb_json, section_dd_keys)
    definition = ''
    for i, line in enumerate(root_text):
      definition += '\n> '
      line_key = section_dd_keys[i]
      if line_key in ['pli-tv-bu-vb-pc71:2.1.9']:
        # In these exceptional cases where I can't parse the variant_text,
        # just stick the note on the end of the line
        footnotes.append(vb_json['variant_text'][line_key].strip())
        definition += vb_json['root_text'][line_key].strip()
        definition += f"[^{len(footnotes)}] "
        continue
      definition += render_pali_line_with_variants(line, line_key, vb_json, footnotes) + ' '
    definition = apply_pe_references(term, definition)

    out = f"## {term}"
    if section_term_key in vb_json['translation_text']:
      out += " ("
      out += _render_translation_line(vb_json['translation_text'][section_term_key].replace(": ", ""))
      out += ")"
    out += "\n"
    out += definition
    out += "\n"

    translation = [vb_json['translation_text'][k] for k in section_dd_keys if k in vb_json['translation_text']]
    if translation:
      for i, line in enumerate(translation):
        line_key = section_dd_keys[i]
        out += f"\n{_render_translation_line(line)}"
        if 'comment_text' in vb_json and line_key in vb_json['comment_text']:
          comment_text = vb_json['comment_text'][line_key]
          # Hacky fix for an Ajahn Brahmali typo
          if line_key == "pli-tv-bu-vb-pc25:3.1.10":
            if "“standard fingerbreadths”. For an explanation of <i lang='pi' translate='no'>sugataṅgula</i>, the idea" not in comment_text:
              raise Exception(comment_text)
            comment_text = comment_text.replace(
              "“standard fingerbreadths”. For an explanation of <i lang='pi' translate='no'>sugataṅgula</i>, the idea",
              "“standard fingerbreadths”. For an explanation of <i lang='pi' translate='no'>sugata</i>, the idea",
            )
          footnotes.append(render_note_as_markdown(comment_text, filepath.parent))
          out += f"[^{len(footnotes)}]"
      out += "\n"
      out += f"\n~ [Ajahn Brahmali's translation]({sc_link_for_ref(section_term_key)})\n\n"
    return out

  ret = ''
  footnotes = []
  for term_key, definition_keys in definitions:
    # Split definition_keys at any interior <dt> boundaries.
    # A <dt> inside definition_keys is a sub-term that gets its own full
    # ## Pali (English) + blockquote + translation + link section.
    sections = []  # list of (section_term_key, [dd_keys])
    current_term_key = term_key
    current_dd_keys = []
    for dk in definition_keys:
      if '<dt>' in vb_json['html_text'].get(dk, ''):
        # Flush the previous section (if it has body keys), start a new one
        if current_dd_keys:
          sections.append((current_term_key, current_dd_keys))
        current_term_key = dk
        current_dd_keys = []
      else:
        current_dd_keys.append(dk)
    if current_dd_keys or not sections:
      sections.append((current_term_key, current_dd_keys))

    for section_term_key, section_dd_keys in sections:
      ret += render_section(section_term_key, section_dd_keys)
    line_key = definition_keys[-1]
  ret += _render_footnotes(footnotes).lstrip('\n')
  end_ref = line_key
  # Above we hacked some definitions out of order
  # This messes with the ranges, so just refer to these by
  # the first reference only.
  if end_ref.startswith("pli-tv-bi-vb-pc8:2.1."):
    end_ref = definitions[0][0]
  write_md_file(filepath, definitions[0][0], end_ref, ret)

def rule_shortname(scid: str) -> str:
  textid, segid = scid.split(':')
  splittextid = textid.split('-')
  ruleid = splittextid[-1]
  assert len(ruleid) >= 3 and len(ruleid) <= 4 and int(ruleid[2:]) > 0
  return f"{splittextid[2].capitalize()} {ruleid[0:2].capitalize()} {ruleid[2:]} ({RULENAMES[textid]})"

def render_note_as_markdown(note: str, cwd: Path, strict: bool = True) -> str:
  """Renders one of Ajahn Brahmali's notes (html) as markdown for a file in `cwd`.

  If `strict`, raises an Exception when a reference to one of the appendices
  can't be linked. Otherwise, such references are left as plain text."""
  # We're currently not importing the Plant or Furniture Appendices, so link to them on the web
  note = note.replace(
    "see Appendix of Plants",
    "see [Appendix of Plants](https://suttacentral.net/edition/pli-tv-vi/en/brahmali/appendix-plants?lang=en)",
  )
  note = note.replace(
    "see Appendix of Furniture",
    "see [Appendix of Furniture](https://suttacentral.net/edition/pli-tv-vi/en/brahmali/appendix-furniture?lang=en)",
  )
  if "see the same appendix" in note and (strict or (
    cwd == VB_WORD_DEFS_FOLDER and "“robe-cloth”, see the same appendix" in note
  )):
    # A hacky implementation. Check our assumptions still hold first
    assert cwd == VB_WORD_DEFS_FOLDER, "Expected 'see the same appendix' to be in a word def"
    assert "“robe-cloth”, see the same appendix" in note, "Expected 'see the same appendix' to be about robecloth!"
    note = note.replace(
      "see the same appendix",
      "see [the same appendix](../../../Ajahn%20Brahmali/Glosses/Cīvara%20means%20“robe”%20“robe-cloth”.md)"
    )
  pali_terms = []
  if any(needle in note for needle in NOTES_NEEDING_MULTIPLE_LINKS):
    pali_terms = list(COMMENT_INLINE_PALI.finditer(note))
    pali_terms.reverse()
    for term in pali_terms:
      stemmed_term = pali_stem(term.group(1))
      if " " in stemmed_term:
        if not strict:
          continue
        raise NotImplementedError("Teach me how to handle multi-word Pali terms")
      if stemmed_term in BRAHMALI_GLOSSARY:
        start, end = term.span(1)
        prefix = note[:start]
        suffix = note[end:]
        term_link = abs_path_to_obsidian_link_text(
          BRAHMALI_GLOSSARY[stemmed_term],
          cwd
        )
        term_link = f"[{term.group(1)}{term_link}"
        note = prefix + term_link + suffix
  elif "Appendix of Technical Terms" in note:
    split_note = note.split("Appendix of Technical Terms")
    note = ""
    for part in split_note[:-1]:
      note += part
      pali_terms = list(COMMENT_INLINE_PALI.finditer(part))
      if len(pali_terms) == 0 and strict:
        raise Exception(f"Unable to find a Pali term in \"\"\"{part}\"\"\"")
      else:
        pali_terms.reverse() # we want to find the last linkable one
        matched = False
        for term in pali_terms:
          term = pali_stem(term.group(1))
          if term == 'bahidvārakoṭṭhak':
            term = 'koṭṭhak' # Hack around BuNp15:1.2.16
          elif term == 'anujānām':
            term = 'anuj' # BuPc21:1.23
          elif term == 'dūses':
            term = 'dūs' # BuPc27
          elif term in ['abbhantar', 'dhan', 'yoj', 'aṅgul']:
            term = 'sugat' # This is one of the measurement terms
          if " " in term:
            if not strict:
              continue
            raise NotImplementedError("Teach me how to handle multi-word Pali terms")
          if term in BRAHMALI_GLOSSARY:
            matched = True
            note += "[Appendix of Technical Terms"
            note += abs_path_to_obsidian_link_text(
              BRAHMALI_GLOSSARY[term],
              cwd,
            )
            break
        if not matched:
          if strict:
            raise Exception(f"Unable to find glossary item match in \"\"\"{part}\"\"\"")
          note += "Appendix of Technical Terms"
    note += split_note[-1]
  return markdownify.markdownify(note).strip()

def render_nonoffenses(vb_json: dict, heading_scid: str):
  if "<section class='anapatti'" not in vb_json['html_text'][heading_scid]:
    raise Exception(f"Expected {heading_scid} to be a nonoffense section start")
  fpath = vb_folder_for_scid(heading_scid).joinpath(
    f"Nonoffenses for {rule_shortname(heading_scid)}.md"
  )
  ret = ''
  footnotes = []
  translator_note_count = 0
  key_spot = vb_json['keys_order'].index(heading_scid)
  scid = heading_scid
  assert heading_scid.endswith('.0')
  linkto = vb_json['keys_order'][key_spot + 1]
  assert linkto.endswith('.1')
  while '</section>' not in vb_json['html_text'][scid]:
    key_spot += 1
    scid = vb_json['keys_order'][key_spot]
    try:
      ret += f"\n{_render_translation_line(vb_json['translation_text'][scid])}"
      if 'comment_text' in vb_json and scid in vb_json['comment_text']:
        footnotes.append(render_note_as_markdown(vb_json['comment_text'][scid], fpath.parent))
        translator_note_count += 1
        ret += f"[^{len(footnotes)}]"
      ret += "  \n"
    except KeyError:
      pass # if no translation, just concat the root onto the previous
    try:
      ret += f"> {vb_json['root_text'][scid].strip()}"
      if 'variant_text' in vb_json and scid in vb_json['variant_text']:
        footnotes.append(vb_json['variant_text'][scid])
        ret += f"[^{len(footnotes)}]"
      ret += "  \n"
    except KeyError:
      pass # if no root_text, just concat the translation onto the previous
  ret += _render_footnotes(footnotes, heading="Footnote" if len(footnotes) == 1 else "Footnotes")
  ret += "\nTranslation "
  if translator_note_count:
    ret += "and note"
    if translator_note_count > 1:
      ret += "s"
    ret += " "
  ret += f"by Ajahn Brahmali.\nSource: <{sc_link_for_ref(linkto)}>\n"
  write_md_file(fpath, heading_scid, scid, ret)

PM_RULE_HTMLS = {
  "<p>{}</p>",
  "<p>{} ",
  "<p>{}",
  "{} ",
  "{}",
  "{}</p>",
}
PM_NOT_RULE_HTMLS = {
  "<hr><p>{} ",
  "<hr><p>{}",
  "<h4>{}</h4>",
  "<p class='endsection'>{}</p>",
}
def get_pm_rule_keys(patimokkha: dict, rule_name: str) -> list[str]:
  rule_header_loc = get_key_where_roottext_contains(
    patimokkha,
    rule_name,
  )
  assert patimokkha['html_text'][rule_header_loc] == "<h4>{}</h4>", f"Unexpected html for {rule_header_loc}"
  loc_i = patimokkha['keys_order'].index(rule_header_loc) + 1
  cur_loc = patimokkha['keys_order'][loc_i]
  ret = []
  while patimokkha['html_text'][cur_loc] in PM_RULE_HTMLS:
    ret.append(cur_loc)
    loc_i += 1
    cur_loc = patimokkha['keys_order'][loc_i]
  assert patimokkha['html_text'][cur_loc] in PM_NOT_RULE_HTMLS, f"Unknown HTML found at {cur_loc}: \"{patimokkha['html_text'][cur_loc]}\""
  return ret

def get_bu_parallel_for_rule(rule: dict) -> str:
  bu_parallel_id = 'pli-tv-bi-pm-pc90'
  if rule['uid'].startswith('pli-tv-bi-pm-pd'):
    bu_parallel_id = 'pli-tv-bi-pm-pd1'
  elif rule['uid'] == 'pli-tv-bi-pm-sk30':
    bu_parallel_id = 'pli-tv-bu-pm-sk30'
  elif rule['uid'] not in {'pli-tv-bi-pm-pc91', 'pli-tv-bi-pm-pc92', 'pli-tv-bi-pm-pc93'}:
    bu_parallel = rule['uid'].replace('-bi-', '-bu-')[:15]
    bu_parallel = [p for p in rule['parallels'] if (p['to']['uid'] or '').startswith(bu_parallel)]
    assert len(bu_parallel) == 1, f"Found {len(bu_parallel)} parallels for {rule['uid']} {rule['name']}: {bu_parallel}"
    bu_parallel = bu_parallel[0]
    bu_parallel_id = bu_parallel['to']['uid']
  return bu_parallel_id

def render_copied_bi_rule(bhikkhuni_patimokkha: dict, category: dict, rule_meta: dict, number: int, next_file: Path | None):
  bhikkhuni_patimokkha = clean_vb_json(bhikkhuni_patimokkha)
  rulename = RULENAMES[rule_meta['uid'].replace('-pm-', '-vb-')]
  rule_keys = get_pm_rule_keys(bhikkhuni_patimokkha, f"{category['root_name']} {number}. ")
  ret = """
## The Rule
"""
  footnotes = []
  filepath = pm_file_for_copied_bi_rule(rule_meta['uid'], rulename)
  root_lines = [bhikkhuni_patimokkha['root_text'][k] for k in rule_keys]
  translation_lines = [bhikkhuni_patimokkha['translation_text'][k] for k in rule_keys]
  for i, line in enumerate(root_lines):
    variant_map = build_variant_map(line, rule_keys[i], bhikkhuni_patimokkha)
    assert len(variant_map) == 0, f"Unexpectedly found variants at {rule_keys[i]}: {variant_map}"
    ret += f"\n> {line} "
  ret += "\n"
  for i, line in enumerate(translation_lines):
    key = rule_keys[i]
    ret += f"\n{_render_translation_line(line)}"
    if key in bhikkhuni_patimokkha.get('comment_text', {}):
      notedown = render_note_as_markdown(
        bhikkhuni_patimokkha['comment_text'][key],
        filepath,
      )
      if "see Appendix on Individual Bhikkhunī Rules" in notedown:
        assert key == "pli-tv-bi-pm:9.1", "I thought the only Indv Rule note was BiPj1"
        notedown = notedown.replace(
          "see Appendix on Individual Bhikkhunī Rules",
          "see [Appendix on Individual Bhikkhunī Rules](../../../../Ajahn%20Brahmali/Specific%20Bhikkhuni%20Rules/Bhikkhunī%20pārājika%201.md)",
        )
      footnotes.append(notedown + " (AjBr)")
      ret += f"[^{len(footnotes)}]"
    ret += "  "
  ret += f"\n~ [Ajahn Brahmali's translation]({sc_link_for_ref(rule_keys[0])})"
  ret += "\n\n## Vibhaṅga\n\n"
  ret += "The Vibhaṅga for this rule doesn't exist. "
  ret += "Please see [the monk's rule"
  ret += abs_path_to_obsidian_link_text(SCUID_SEGMENT_PATHS.get(get_bu_parallel_for_rule(rule_meta)), filepath)
  ret += " for links to its analysis.\n"
  if next_file:
    ret += "\n\n**Next:** [" + next_file.stem
    ret += abs_path_to_obsidian_link_text(next_file, filepath)
    ret += "\n"
  ret += _render_footnotes(footnotes)
  write_md_file(filepath, rule_meta['uid'], None, ret)


def render_origin_story_for_rule(vb_json: dict) -> str:
  origin_story_scid = None
  for header in ['Origin story', 'First substory', 'First sub-story']:
    try:
      origin_story_scid = get_key_where_translation_contains(vb_json, header)
      break
    except ValueError:
      continue
  if not origin_story_scid:
    raise ValueError(f"Could not find origin story header in {vb_json.get('keys_order', ['?'])[0]}")
  final_ruling_key = get_key_where_translation_contains(vb_json, 'Final ruling')
  final_ruling_key_index = vb_json['keys_order'].index(final_ruling_key)
  fpath = vb_folder_for_scid(origin_story_scid).joinpath(
    f"Origin story for {rule_shortname(origin_story_scid)}.md"
  )
  ret = ''
  footnotes = []
  if origin_story_scid == 'pli-tv-bu-vb-pc1:1.1.0':
    key_index = vb_json['keys_order'].index('pli-tv-bu-vb-pc1:1.2')
  else:
    key_index = vb_json['keys_order'].index(origin_story_scid) + 1
  key = origin_story_scid
  while key_index < final_ruling_key_index:
    key = vb_json['keys_order'][key_index]
    line = vb_json['html_text'][key]
    text = vb_json['translation_text'].get(key, '')
    if 'comment_text' in vb_json and key in vb_json['comment_text']:
      footnotes.append(render_note_as_markdown(vb_json['comment_text'][key], fpath.parent))
      text = text.rstrip()
      text += f"[^{len(footnotes)}] "
    ret += line.replace("{}", text)
    key_index += 1
  ret = "\nTranslated by Ajahn Brahmali\n\nSource: <" + \
    sc_link_for_ref(origin_story_scid) + \
    ">\n\n" + markdownify.markdownify(ret) + "...\n"
  ret += _render_footnotes(footnotes)
  write_md_file(fpath, origin_story_scid, key, ret)
  return origin_story_scid

def render_allowance_for_rule(vb_json: dict, allowance_scid: str) -> str:
  fpath = vb_folder_for_scid(allowance_scid).joinpath(
    f"Allowance for {rule_shortname(allowance_scid)}.md"
  )
  definitions_key = get_keys_where_html_contains(vb_json, "<section class='padabhajaniya'><h2")
  definitions_key_index = vb_json['keys_order'].index(definitions_key[0])
  ret = ''
  footnotes = []
  key = allowance_scid
  key_index = vb_json['keys_order'].index(allowance_scid)
  assert key_index < definitions_key_index, f"Expected {allowance_scid} to be before {definitions_key[0]}"
  # Render the origin story for the allowance
  while True:
    key = vb_json['keys_order'][key_index]
    line = vb_json['html_text'][key]
    if 'rule' in line:
      break
    text = vb_json['translation_text'].get(key, '')
    if 'comment_text' in vb_json and key in vb_json['comment_text']:
      footnotes.append(render_note_as_markdown(vb_json['comment_text'][key], fpath.parent))
      text = text.rstrip()
      text += f"[^{len(footnotes)}] "
    ret += line.replace("{}", text)
    key_index += 1
  # Render the text of the allowance
  ret = markdownify.markdownify(ret) + "\n\n#### The Allowance\n"
  while key_index < definitions_key_index:
    key = vb_json['keys_order'][key_index]
    translation = _render_translation_line(vb_json['translation_text'].get(key, ''))
    text = vb_json['root_text'].get(key, '')
    # TODO render variants as footnotes as well here
    if 'comment_text' in vb_json and key in vb_json['comment_text']:
      footnotes.append(render_note_as_markdown(vb_json['comment_text'][key], fpath.parent))
      translation += f"[^{len(footnotes)}]"
    ret += f"\n> {text.strip()}\n"
    ret += f"\n**{translation}**\n"
    key_index += 1
  ret = "\nTranslated by Ajahn Brahmali\n\nSource: <" + \
    sc_link_for_ref(allowance_scid) + ">\n\n" + ret
  ret += _render_footnotes(footnotes)
  write_md_file(fpath, allowance_scid, key, ret)
  return allowance_scid

def _get_post_definitions_span(vb_json: dict) -> list[str]:
  """Returns keys after the last Definitions </dl> up to the next major section (cakka/anapatti/etc.)."""
  keys = vb_json['keys_order']
  # Find the last padabhajaniya section
  last_pada_start = -1
  for i, k in enumerate(keys):
    if "class='padabhajaniya'" in vb_json['html_text'].get(k, ''):
      last_pada_start = i
  if last_pada_start == -1:
    return []
  # Walk to the end of the padabhajaniya section (tracking nested <section> tags)
  # and continue past </section> until the next major section.
  depth = 0
  j = last_pada_start
  while j < len(keys):
    hj = vb_json['html_text'].get(keys[j], '')
    depth += len(re.findall(r'<section\b', hj))
    depth -= len(re.findall(r'</section>', hj))
    if depth <= 0:
      break
    j += 1
  end_j = j
  while end_j + 1 < len(keys):
    nh = vb_json['html_text'].get(keys[end_j + 1], '')
    if any(c in nh for c in ["class='cakka'", "class='anapatti'", "class='endsutta'", "class='uddana'", "class='vinaya-vinita'"]):
      break
    end_j += 1
  span = keys[last_pada_start:end_j + 1]
  # Check if this span contains a procedure (<section class='kamma'> or <section class='formal-statement'>)
  first_proc_idx = next(
    (idx for idx, k in enumerate(span) if "class='kamma'" in vb_json['html_text'].get(k, '') or "class='formal-statement'" in vb_json['html_text'].get(k, '')),
    -1,
  )
  # For rules with a procedure, find the last </dl> BEFORE the procedure (so trailing <hr><dl> like Bu NP 22 stays in the procedure).
  # Otherwise, find the last </dl> in the padabhajaniya section itself.
  search_end = first_proc_idx if first_proc_idx != -1 else (j - last_pada_start + 1)
  last_dl = -1
  for idx in range(search_end):
    if '</dl>' in vb_json['html_text'].get(span[idx], ''):
      last_dl = idx
  if last_dl == -1:
    return []
  if first_proc_idx != -1:
    return span[last_dl + 1:]
  return span[last_dl + 1:j - last_pada_start + 1]

def get_derived_offenses_and_procedure_refs(vb_json: dict, is_sekhiya: bool) -> tuple[list[str], tuple[str, str, list[str]] | None]:
  """Returns (derived_offenses_keys, (link_label, file_prefix, procedure_keys) | None)."""
  keys = vb_json['keys_order']
  if is_sekhiya:
    fr_keys = get_final_ruling_refs_from_vb_json(vb_json)
    last_fr = fr_keys[-1]
    if '</section>' not in vb_json['html_text'][last_fr]:
      idx = keys.index(last_fr) + 1
      out = []
      while idx < len(keys):
        out.append(keys[idx])
        if '</section>' in vb_json['html_text'][keys[idx]]:
          break
        idx += 1
      return (out, None)
    return (_get_post_definitions_span(vb_json), None)

  trailing = _get_post_definitions_span(vb_json)
  if not trailing:
    return ([], None)
  has_proc = any(
    "class='kamma'" in vb_json['html_text'].get(k, '') or "class='formal-statement'" in vb_json['html_text'].get(k, '')
    for k in trailing
  )
  if not has_proc:
    return (trailing, None)

  relinq_idx = next(
    (idx for idx, k in enumerate(trailing) if 'should be relinquished' in vb_json['translation_text'].get(k, '')),
    -1,
  )
  if relinq_idx != -1:
    return (trailing[:relinq_idx], ("Relinquishment Procedure", "Relinquishment procedure", trailing[relinq_idx:]))
  return ([], ("Formal Procedure", "Formal procedure", trailing))

def _render_pali_english_blocks(
  vb_json: dict,
  seg_keys: list[str],
  fpath: Path,
  doc_id: Optional[str] = None,
) -> str:
  """Renders a sequence of segments as paragraph-grouped Pali blockquotes + Markdown English + footnotes."""
  paragraphs: list[list[str]] = []
  current_para: list[str] = []
  for k in seg_keys:
    h = vb_json['html_text'].get(k, '')
    if current_para and any(tag in h for tag in ['<p', '<hr>', '<dt>', "<section"]):
      paragraphs.append(current_para)
      current_para = []
    current_para.append(k)
  if current_para:
    paragraphs.append(current_para)

  ret = ''
  footnotes = []
  for p_idx, para in enumerate(paragraphs):
    if p_idx > 0:
      ret += '\n'
    pali_lines = []
    for k in para:
      if vb_json['root_text'].get(k, '').strip():
        pali_lines.append("> " + render_pali_line_with_variants(_get_root_text(vb_json, k), k, vb_json, footnotes))
    if pali_lines:
      ret += "\n".join(pali_lines) + "\n\n"
    for k in para:
      raw_line = vb_json['translation_text'].get(k, '').strip()
      if not raw_line:
        continue
      line = _render_translation_line(raw_line)
      if 'comment_text' in vb_json and k in vb_json['comment_text']:
        footnotes.append(render_note_as_markdown(vb_json['comment_text'][k], fpath.parent))
        line += f"[^{len(footnotes)}]"
      ret += f"{line}\n"
  ret += f"\n~ [Ajahn Brahmali's translation]({sc_link_for_ref(seg_keys[0], doc_id)})\n"
  ret += _render_footnotes(footnotes)
  return ret

def render_derived_offenses_and_procedure_for_rule(
  vb_json: dict,
  is_sekhiya: bool,
) -> tuple[str | None, tuple[str, str] | None]:
  derived_keys, proc_spec = get_derived_offenses_and_procedure_refs(vb_json, is_sekhiya)
  derived_scid = None
  if derived_keys:
    first_scid = derived_keys[0]
    fpath = vb_folder_for_scid(first_scid).joinpath(
      f"Derived offenses for {rule_shortname(first_scid)}.md"
    )
    ret = _render_pali_english_blocks(vb_json, derived_keys, fpath)
    write_md_file(fpath, first_scid, derived_keys[-1], ret)
    derived_scid = first_scid
  proc_result = None
  if proc_spec:
    link_label, file_prefix, proc_keys = proc_spec
    first_scid = proc_keys[0]
    fpath = vb_folder_for_scid(first_scid).joinpath(
      f"{file_prefix} for {rule_shortname(first_scid)}.md"
    )
    ret = _render_pali_english_blocks(vb_json, proc_keys, fpath)
    write_md_file(fpath, first_scid, proc_keys[-1], ret)
    proc_result = (link_label, first_scid)
  return (derived_scid, proc_result)

def render_permutations_for_rule(vb_json: dict) -> str | None: # returns scid
  try:
    permutations_scids = get_keys_where_html_contains(vb_json, "<section class='cakka'>")
  except ValueError:
    return None
  if len(permutations_scids) > 1:
    raise Exception(f"Multiple permutations sections found: {permutations_scids}")
  permutations_scid = permutations_scids[0]
  try:
    nonoffense_scid = get_key_where_translation_contains(vb_json, 'Non-offenses')
  except ValueError:
    nonoffense_scid = None
  if not nonoffense_scid:
    nonoffense_scid = get_key_where_roottext_contains(vb_json, ' aniyato niṭṭhito')
  try:
    nonoffense_scid = get_key_where_translation_contains(vb_json, 'More Definitions')
  except ValueError:
    pass
  nonoffense_scid_index = vb_json['keys_order'].index(nonoffense_scid)
  fpath = vb_folder_for_scid(permutations_scid).joinpath(
    f"Permutations for {rule_shortname(permutations_scid)}.md"
  )
  ret = ''
  footnotes = []
  key_index = vb_json['keys_order'].index(permutations_scid)
  if '<h2' in vb_json['html_text'][permutations_scid]:
    key_index += 1
  key = permutations_scid
  while key_index < nonoffense_scid_index:
    key = vb_json['keys_order'][key_index]
    line = vb_json['html_text'][key]
    text = vb_json['translation_text'].get(key, '')
    if 'comment_text' in vb_json and key in vb_json['comment_text'] and len(vb_json['comment_text'][key].strip()) > 1:
      footnotes.append(render_note_as_markdown(vb_json['comment_text'][key], fpath.parent))
      text += f"[^{len(footnotes)}] "
    ret += line.replace("{}", text)
    key_index += 1
  ret = "\nTranslated by Ajahn Brahmali\n\nSource: <" + \
    sc_link_for_ref(permutations_scid) + \
    ">\n\n" + markdownify.markdownify(ret)
  ret += _render_footnotes(footnotes, heading="Note" if len(footnotes) == 1 else "Notes")
  write_md_file(fpath, permutations_scid, key, ret)
  return permutations_scid

def render_category_metafile(category: dict):
  fpath = file_for_category(category)
  markdown = "\n" + markdownify.markdownify(category['blurb'])
  markdown = markdown.replace(
    "*Samathakkhandhaka*",
    "[*Samathakkhandhaka*](https://suttacentral.net/pli-tv-kd14/en/brahmali)",
  )
  if category['uid'].endswith('-as'):
    as_file = pm_file_for_as(category['uid'])
    markdown += "\n\nNext: [" + as_file.stem
    markdown += abs_path_to_obsidian_link_text(as_file, fpath)
    markdown += "\n"
  else:
    markdown += "\n\nNext: ["
    if '-bi-' in category['uid']:
      markdown += "Bhikkhunī "
    else:
      markdown += "Bhikkhu "
    markdown += category['root_name'] + " 1 (" + RULENAMES[category['uid']+'1'] + ")"
    markdown += abs_path_to_obsidian_link_text(pm_file_for_scid(category['uid']+'1'), fpath)
    markdown += "\n"
  write_md_file(fpath, category['uid'], None, markdown)

def render_pali_line_with_variants(line: list[str], key: str, vb_json: dict, footnotes: list[str]) -> str:
  """Renders a tokenized Pali line with inline variant footnotes."""
  variant_map = build_variant_map(line, key, vb_json)
  rendered = []
  for j, word in enumerate(line):
    if j in variant_map:
      footnotes.append(" → ".join(variant_map[j]))
      word += f"[^{len(footnotes)}]"
    rendered.append(word)
  return " ".join(rendered)

def render_adhikaranasamatha(category: dict, vb_json: dict):
  vb_json = clean_vb_json(vb_json)
  vb_prefix = category['uid']
  pm_prefix = vb_prefix.replace('-vb-', '-pm-')
  doc_id = f"{vb_prefix}1-7"
  fpath = pm_file_for_as(vb_prefix)
  nigamana_file = pm_file_for_nigamana(vb_prefix)

  keys = vb_json['keys_order']
  endsutta_key = get_keys_where_html_contains(vb_json, "class='endsutta'")[0]
  endsutta_idx = keys.index(endsutta_key)
  as_keys = keys[:endsutta_idx + 1]

  intro_keys = [k for k in as_keys if k.endswith(':1.1') or k.endswith(':2.1')][:2]
  rule_keys = [k for k in as_keys if "class='rule'" in vb_json['html_text'][k]]
  assert len(rule_keys) == 7, f"Expected 7 Adhikaranasamatha rules, found {len(rule_keys)}"

  footnotes = []
  ret = "## The Seven Principles\n\n"
  for k in intro_keys:
    ret += "> " + render_pali_line_with_variants(_get_root_text(vb_json, k), k, vb_json, footnotes) + "\n"
  for idx, k in enumerate(rule_keys, start=1):
    ret += f"> {idx}. " + render_pali_line_with_variants(_get_root_text(vb_json, k), k, vb_json, footnotes) + "\n"
  ret += "\n"
  for i, k in enumerate(intro_keys):
    ret += _render_translation_line(vb_json['translation_text'][k]) + ("  \n" if i == 0 else "\n")
  for idx, k in enumerate(rule_keys, start=1):
    ret += f"{idx}. {_render_translation_line(vb_json['translation_text'][k])}\n"
  ret += f"\n~ [Ajahn Brahmali's translation]({sc_link_for_ref(intro_keys[0], doc_id)})\n\n"
  ret += "## Vibhaṅga\n\n"
  ret += "There is no Vibhaṅga for the *adhikaraṇasamathadhammas*. "
  ret += "The detailed explanation is found in the [*Samathakkhandhaka*](https://suttacentral.net/pli-tv-kd14/en/brahmali).\n"
  ret += "\n\n**Next:** [" + nigamana_file.stem
  ret += abs_path_to_obsidian_link_text(nigamana_file, fpath)
  ret += "\n"
  ret += _render_footnotes(footnotes)

  extra_aliases = [f"{pm_prefix}{n}" for n in range(1, 8)]
  write_md_file(fpath, doc_id, None, ret, extra_aliases=extra_aliases)

  for n in range(1, 8):
    SCUID_SEGMENT_PATHS.add(f"{pm_prefix}{n}", None, fpath)
    SCUID_SEGMENT_PATHS.add(f"{vb_prefix}{n}", None, fpath)

  # Register per-appid segment ranges (IDRangePathStore requires matching appids)
  appid_groups: dict[str, list[str]] = {}
  for k in as_keys:
    appid = k.split(':')[0]
    appid_groups.setdefault(appid, []).append(k)
  for group in appid_groups.values():
    SCUID_SEGMENT_PATHS.add(group[0], group[-1], fpath)

def render_nigamana(category: dict, vb_json: dict):
  vb_json = clean_vb_json(vb_json)
  vb_prefix = category['uid']
  doc_id = f"{vb_prefix}1-7"
  fpath = pm_file_for_nigamana(vb_prefix)

  keys = vb_json['keys_order']
  endsutta_key = get_keys_where_html_contains(vb_json, "class='endsutta'")[0]
  nigamana_keys = [
    k for k in keys[keys.index(endsutta_key) + 1:]
    if not vb_json['root_text'].get(k, '').strip().endswith(('niṭṭhito.', 'niṭṭhitā.'))
  ]
  assert len(nigamana_keys) > 0, f"No Nigamana keys found in {doc_id}"

  ret = "## Nigamana\n\n" + _render_pali_english_blocks(vb_json, nigamana_keys, fpath, doc_id=doc_id)
  write_md_file(fpath, nigamana_keys[0], nigamana_keys[-1], ret)

def render_rule(category: dict, rule_meta: dict, number: int, vb_json: dict, next_file: Path | None):
  vb_json = clean_vb_json(vb_json)
  ascii_rulename = f" {unidecode(category['root_name'])} {number} "
  sangha = "Bhikkhu"
  if rule_meta['uid'].startswith('pli-tv-bi'):
    sangha = "Bhikkhuni"
  origin_story_scid = render_origin_story_for_rule(vb_json)
  allowance_scid = None
  if rule_meta['uid'] in ALLOWANCE_STORIES:
    allowance_scid = render_allowance_for_rule(vb_json, ALLOWANCE_STORIES[rule_meta['uid']])
  derived_offenses_scid, procedure_info = render_derived_offenses_and_procedure_for_rule(
    vb_json, category['root_name'] == 'Sekhiya'
  )
  permutations_scid = render_permutations_for_rule(vb_json)
  if ' Sekhiya ' not in ascii_rulename and sangha == "Bhikkhu":
    vb_file = path_to_suddhaso_file_starting_with(f"VB{ascii_rulename}")
    SCUID_SEGMENT_PATHS.add(rule_meta['uid'], None, vb_file)
  uid = rule_meta['uid'].replace('-vb-', '-pm-')
  rule_file = pm_file_for_scid(rule_meta['uid'])
  rule_keys = get_final_ruling_refs_from_vb_json(vb_json)
  ret = "## The Rule\n"
  root_text = get_root_text(vb_json, rule_keys)
  if not root_text[-1][-1].endswith("”ti."):
    raise Exception(f"Unexpected root ending: {root_text[-1][-1]}")
  # Remove the ending quote particle from the last root word
  root_text[-1][-1] = root_text[-1][-1][:-3]
  if root_text[-1][-1].endswith("pācittiyan”"):
    root_text[-1][-1] = root_text[-1][-1][:-2] + "ṁ”"
  if root_text[-1][-1].endswith("paṭidesemī’”"):
    root_text[-1][-1] = root_text[-1][-1][:-1] + "ti”"
  if root_text[-1][-1].endswith("saṅghādisesan”"):
    root_text[-1][-1] = root_text[-1][-1][:-2] + "ṁ”"
  
  if category['root_name'] == 'Aniyata':
    nonoffenses_scid = None
  else:
    nonoffenses_scid = get_key_where_translation_contains(vb_json, 'Non-offenses')
    render_nonoffenses(vb_json, nonoffenses_scid)

  if category['root_name'] == 'Sekhiya':
    word_defs = []
  else:
    word_defs = render_word_definitions(vb_json, root_text)
  rendered_root = ''
  footnotes = []
  k = 0
  for i, line in enumerate(root_text):
    def _get_def(k):
      current_def = word_defs[k] if k < len(word_defs) else None
      def_in_scope = current_def and current_def[0][0] == i
      start_of_link = current_def[0][1] if def_in_scope else None
      end_of_link = current_def[0][2] if def_in_scope else None
      return (current_def, def_in_scope, start_of_link, end_of_link)
    (current_def, def_in_scope, start_of_link, end_of_link) = _get_def(k)
    key = rule_keys[i]
    variant_map = build_variant_map(line, key, vb_json)
    rendered_root += "\n> "
    defered_footnotes = deque()
    for j, word in enumerate(line):
      # Handle def link start
      if j == start_of_link:
        assert len(defered_footnotes) == 0, "Defered footnotes should be rendered before next link start"
        rendered_root += "["
      
      # Render the word itself
      rendered_root += word
      
      # Add variant to footnotes if present
      if j in variant_map:
        footnotes.append(" → ".join(variant_map[j]))
      
      # Add link end and variant footnotes as needed
      if j == end_of_link:
        rendered_root += abs_path_to_obsidian_link_text(current_def[1], rule_file.parent)
        k += 1
        (current_def, def_in_scope, start_of_link, end_of_link) = _get_def(k)
        while len(defered_footnotes) > 0:
          rendered_root += f"[^{defered_footnotes.popleft()}]"
        if j in variant_map:
          # Render footnotes at the end of a link outside the link
          rendered_root += f"[^{len(footnotes)}]"
      elif j in variant_map:
        overlaps_link = def_in_scope and (start_of_link <= j < end_of_link)
        # Render footnotes inside a link as unicode superscripts
        if overlaps_link:
          rendered_root += superscript_number(len(footnotes))
          defered_footnotes.append(len(footnotes))
        else:
          rendered_root += f"[^{len(footnotes)}]"
      
      # Add space between words
      if j < len(line) - 1:
        rendered_root += " "

  ret += rendered_root
  ret += '\n\n'
  num_variants = len(footnotes)
  for k in rule_keys:
    ret += _render_translation_line(vb_json['translation_text'].get(k, ''))
    if k in vb_json.get('comment_text', {}):
      footnotes.append(render_note_as_markdown(vb_json['comment_text'][k], rule_file.parent) + " (AjBr)")
      ret += f"[^{len(footnotes)}]"
    ret += '\n'
  ret += f"~ [Ajahn Brahmali's translation]({sc_link_for_ref(rule_keys[0])})\n\n"
  ret += "## Vibhaṅga\n\n"
  if origin_story_scid:
    ret += f"  - [Origin Story{abs_path_to_obsidian_link_text(SCUID_SEGMENT_PATHS.get(origin_story_scid), rule_file)}\n"
  if allowance_scid:
    ret += f"  - [Allowance{abs_path_to_obsidian_link_text(SCUID_SEGMENT_PATHS.get(allowance_scid), rule_file)}\n"
  if derived_offenses_scid:
    ret += f"  - [Derived Offenses{abs_path_to_obsidian_link_text(SCUID_SEGMENT_PATHS.get(derived_offenses_scid), rule_file)}\n"
  if procedure_info:
    proc_label, proc_scid = procedure_info
    ret += f"  - [{proc_label}{abs_path_to_obsidian_link_text(SCUID_SEGMENT_PATHS.get(proc_scid), rule_file)}\n"
  if permutations_scid:
    ret += f"  - [Permutations{abs_path_to_obsidian_link_text(SCUID_SEGMENT_PATHS.get(permutations_scid), rule_file)}\n"
  if nonoffenses_scid:
    ret += "  - [Non-offenses" + abs_path_to_obsidian_link_text(SCUID_SEGMENT_PATHS.get(nonoffenses_scid), rule_file.parent)
    ret += "\n"
  if ' Sekhiya ' not in ascii_rulename and sangha == "Bhikkhu":
    ret += (f"  - [Bhante Suddhaso's translation{abs_path_to_obsidian_link_text(SCUID_SEGMENT_PATHS.get(rule_meta['uid']), rule_file)}"
      " (pdf)\n")
  ret += "\n"
  if next_file:  
    ret += "\n**Next:** [" + next_file.stem
    ret += abs_path_to_obsidian_link_text(next_file, rule_file)
    ret += "\n"
  if footnotes:
    ret += "\n## Footnotes\n\n"
    if num_variants > 0:
      for i, footnote in enumerate(footnotes):
        if i >= num_variants:
          break
        ret += f"[^{i+1}]: {footnote}\n"
    if len(footnotes) > num_variants:
      for i, footnote in enumerate(footnotes):
        # This doesn't go in the render_note_as_markdown function because
        # it relies on this metadata and these links only appear in the rules
        if "Appendix on Individual Bhikkhunī Rules" in footnote:
          appendix_link = "[Appendix on Individual Bhikkhunī Rules]"
          appendix_link += "(../../../../Ajahn%20Brahmali/"
          appendix_link += "Specific%20Bhikkhuni%20Rules/Bhikkhunī%20"
          appendix_link += category['root_name'].lower() + '%20'
          appendix_link += str(number) + ".md)"
          footnote = footnote.replace(
            "Appendix on Individual Bhikkhunī Rules",
            appendix_link
          )
        if i < num_variants:
          continue
        ret += f"[^{i+1}]: {footnote}\n"
  write_md_file(rule_file, uid, None, ret)
  SCUID_SEGMENT_PATHS.add(rule_keys[0], rule_keys[-1], rule_file)
