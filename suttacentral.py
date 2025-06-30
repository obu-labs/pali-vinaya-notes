#!/bin/python3

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
  global VB_STORY_FOLDER
  global VB_WORD_DEFS_FOLDER
  global VB_NONOFFENSES_FOLDER
  global VB_PERMUTATIONS_FOLDER

  PALI_FOLDER = pali_path
  HYPOTHETICAL_VAULT_ROOT = pali_path.parent
  BRAHMALI_GLOSSARY = {
    root: HYPOTHETICAL_VAULT_ROOT.joinpath(relpath)
    for root, relpath in
    json.load(BRAHMALI_GLOSSARY_FILE.open('rt', encoding='utf-8')).items()
  }
  PM_FOLDER = PALI_FOLDER.joinpath('Patimokkha')
  VB_FOLDER = PALI_FOLDER.joinpath('Vibhanga')
  VB_STORY_FOLDER = VB_FOLDER.joinpath('Origin Stories')
  VB_WORD_DEFS_FOLDER = VB_FOLDER.joinpath('Word Analysis')
  VB_NONOFFENSES_FOLDER = VB_FOLDER.joinpath('Nonoffenses')
  VB_PERMUTATIONS_FOLDER = VB_FOLDER.joinpath('Permutations')
  VB_WORD_DEFS_FOLDER.mkdir(exist_ok=True, parents=True)
  VB_NONOFFENSES_FOLDER.mkdir()
  VB_PERMUTATIONS_FOLDER.mkdir()
  VB_STORY_FOLDER.mkdir()
  PM_FOLDER.mkdir()

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

def sc_link_for_ref(ref: str) -> str:
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

COMMENT_INLINE_PALI = re.compile(r"<i lang=['\"]pi['\"] translate=['\"]no['\"]>(.*?)<\/i>")

@disk_memoizer.cache()
def get_rule_categories():
  r = requests.get(SC_MENU_URL.format('pli-tv-bu-vb'))
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

def write_md_file(rule_file: Path, start_scuid: str, end_scuid: str | None, content: str) -> None:
  aliases = start_scuid
  if end_scuid and end_scuid != start_scuid:
    aliases += f"\n  - {end_scuid}"
  fname = str(rule_file.stem).lower()
  if fname in PREVIOUSLY_WRITTEN_FILES:
    raise Exception(f"ERROR: We already wrote a file named {fname}")
  PREVIOUSLY_WRITTEN_FILES.add(fname)
  rule_file.write_text(f"""---
aliases:
  - {aliases}
---
{content}

---

DO NOT MODIFY.
To add your thoughts, create a new note and link to this one.
Found a problem? [Open an issue on GitHub](https://github.com/obu-labs/pali-vinaya-notes/issues/new).
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
          del definitions[i][1][j+1:]
          break
      i += 1
    render_word_definition_file(filepath, definitions, vb_json)
  return ret

def build_variant_map(line: list[str], key: str, vb_json: dict) -> dict[int, list[str]]:
  """Given a `line` of Pali words at `key` in `vb_json`, return a map from word indexes to variant_text."""
  variant_map = {}
  if key in vb_json.get('variant_text', {}):
    sanitized_line = [sanitize(w) for w in line]
    line_variants = vb_json['variant_text'][key].strip().replace(' | ', '; ').split("; ")
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
  
  ret = ''
  footnotes = []
  for term_key, definition_keys in definitions:
    term = vb_json['root_text'][term_key].strip()
    # render the root definition with variants and pe links
    root_text = get_root_text(vb_json, definition_keys)
    definition = ''
    for i, line in enumerate(root_text):
      definition += '\n> '
      line_key = definition_keys[i]
      if line_key in ['pli-tv-bu-vb-pc71:2.1.9']:
        # In these exceptional cases where I can't parse the variant_text,
        # just stick the note on the end of the line
        footnotes.append(vb_json['variant_text'][line_key].strip())
        definition += vb_json['root_text'][line_key].strip()
        definition += f"[^{len(footnotes)}] "
        continue
      variant_map = build_variant_map(line, line_key, vb_json)
      for j, word in enumerate(line):
        definition += word
        if j in variant_map:
           footnotes.append(" → ".join(variant_map[j]))
           definition += f"[^{len(footnotes)}]"
        definition += ' '
    definition = apply_pe_references(term, definition)

    translation = [vb_json['translation_text'][k] for k in definition_keys if k in vb_json['translation_text']]
    ret += f"## {term}"
    if term_key in vb_json['translation_text']:
      ret += " ("
      ret += vb_json['translation_text'][term_key].replace(": ", "")
      ret += ")"
    ret += "\n"
    ret += definition
    ret += "\n"
    if translation:
      for i, line in enumerate(translation):
        ret += f"\n{line.strip()}"
        line_key = definition_keys[i]
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
          ret += f"[^{len(footnotes)}]"
      ret += "\n"
      ret += f"\n~ [Ajahn Brahmali's translation]({sc_link_for_ref(term_key)})\n\n"
  if footnotes:
    ret += "## Footnotes\n"
    for i, footnote in enumerate(footnotes):
      ret += f"\n[^{i + 1}]: {footnote}\n"
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

def render_note_as_markdown(note: str, cwd: Path) -> str:
  # We're currently not importing the Plant or Furniture Appendices, so link to them on the web
  note = note.replace(
    "see Appendix of Plants",
    "see [Appendix of Plants](https://suttacentral.net/edition/pli-tv-vi/en/brahmali/appendix-plants?lang=en)",
  )
  note = note.replace(
    "see Appendix of Furniture",
    "see [Appendix of Furniture](https://suttacentral.net/edition/pli-tv-vi/en/brahmali/appendix-furniture?lang=en)",
  )
  if "see the same appendix" in note:
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
      if len(pali_terms) == 0:
        raise Exception(f"Unable to find a Pali term in \"\"\"{part}\"\"\"")
      else:
        pali_terms.reverse() # we want to find the last linkable one
        matched = False
        for term in pali_terms:
          term = pali_stem(term.group(1))
          if " " in term:
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
          raise Exception(f"Unable to find glossary item match in \"\"\"{part}\"\"\"")
    note += split_note[-1]
  return markdownify.markdownify(note).strip()

def render_nonoffenses(vb_json: dict, heading_scid: str):
  if "<section class='anapatti'" not in vb_json['html_text'][heading_scid]:
    raise Exception(f"Expected {heading_scid} to be a nonoffense section start")
  fpath = VB_NONOFFENSES_FOLDER.joinpath(
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
      ret += f"\n{vb_json['translation_text'][scid].strip()}"
      if 'comment_text' in vb_json and scid in vb_json['comment_text']:
        footnotes.append(render_note_as_markdown(vb_json['comment_text'][scid], VB_NONOFFENSES_FOLDER))
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
  if footnotes:
    ret += '\n## Footnote'
    if len(footnotes) > 1:
      ret += 's'
    ret += '\n'
    for i, footnote in enumerate(footnotes):
      ret += f"\n[^{i + 1}]: {footnote}  \n"
  ret += "\nTranslation "
  if translator_note_count:
    ret += "and note"
    if translator_note_count > 1:
      ret += "s"
    ret += " "
  ret += f"by Ajahn Brahmali.\nSource URL: <{sc_link_for_ref(linkto)}>\n"
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

def render_copied_bi_rule(bhikkhuni_patimokkha: dict, category: dict, rule_meta: dict, number: int):
  bu_parallel_id = 'pli-tv-bi-pm-pc90'
  if rule_meta['uid'].startswith('pli-tv-bi-pm-pd'):
    bu_parallel_id = 'pli-tv-bi-pm-pd1'
  elif rule_meta['uid'] == 'pli-tv-bi-pm-sk30':
    bu_parallel_id = 'pli-tv-bu-pm-sk30'
  elif rule_meta['uid'] not in {'pli-tv-bi-pm-pc91', 'pli-tv-bi-pm-pc92', 'pli-tv-bi-pm-pc93'}:
    bu_parallel = rule_meta['uid'].replace('-bi-', '-bu-')[:15]
    bu_parallel = [p for p in rule_meta['parallels'] if (p['to']['uid'] or '').startswith(bu_parallel)]
    assert len(bu_parallel) == 1, f"Found {len(bu_parallel)} parallels for {rule_meta['uid']} {rule_meta['name']}: {bu_parallel}"
    bu_parallel = bu_parallel[0]
    bu_parallel_id = bu_parallel['to']['uid']
  rulename = RULENAMES[bu_parallel_id.replace('-pm-', '-vb-')]
  rule_keys = get_pm_rule_keys(bhikkhuni_patimokkha, f"{category['root_name']} {number}. ")
  ret = """
## The Rule
"""
  root_lines = [bhikkhuni_patimokkha['root_text'][k] for k in rule_keys]
  translation_lines = [bhikkhuni_patimokkha['translation_text'][k] for k in rule_keys]
  for line in root_lines:
    ret += f"\n> {line} "
  ret += "\n"
  for line in translation_lines:
    ret += f"\n{line} "
  ret += f"\n~ [Ajahn Brahmali's translation]({sc_link_for_ref(rule_keys[0])})"
  ret += "\n\n## Vibhaṅga\n\n"
  ret += "The Vibhaṅga for this rule doesn't exist. "
  filepath = PM_FOLDER.joinpath(
    f"Bhikkhuni {unidecode(category['root_name'])} {number} ({rulename}).md"
  )
  ret += "Please see " + full_obsidian_style_link_for_scuid(bu_parallel_id, filepath)
  ret += " for links to its analysis.\n"
  write_md_file(filepath, rule_meta['uid'], None, ret)


def render_origin_story_for_rule(vb_json: dict) -> str:
  origin_story_scid = get_key_where_translation_contains(vb_json, 'Origin story')
  final_ruling_key = get_key_where_translation_contains(vb_json, 'Final ruling')
  final_ruling_key_index = vb_json['keys_order'].index(final_ruling_key)
  fpath = VB_STORY_FOLDER.joinpath(
    f"Origin story for {rule_shortname(origin_story_scid)}.md"
  )
  ret = ''
  footnotes = []
  key_index = vb_json['keys_order'].index(origin_story_scid) + 1
  key = origin_story_scid
  while key_index < final_ruling_key_index:
    key = vb_json['keys_order'][key_index]
    line = vb_json['html_text'][key]
    text = vb_json['translation_text'].get(key, '')
    if 'comment_text' in vb_json and key in vb_json['comment_text']:
      footnotes.append(render_note_as_markdown(vb_json['comment_text'][key], VB_STORY_FOLDER))
      text += f"[^{len(footnotes)}] "
    ret += line.replace("{}", text)
    key_index += 1
  ret = "\nTranslated by [Ajahn Brahmali](" + \
    sc_link_for_ref(origin_story_scid) + \
    ")\n" + markdownify.markdownify(ret) + "...\n"
  if footnotes:
    ret += "\n## Footnotes\n"
    for i, footnote in enumerate(footnotes):
      ret += f"\n[^{i + 1}]: {footnote}\n"
  write_md_file(fpath, origin_story_scid, key, ret)
  return origin_story_scid

def render_permutations_for_rule(vb_json: dict) -> str | None: # returns scid
  try:
    permutations_scids = get_keys_where_html_contains(vb_json, "<section class='cakka'>")
  except ValueError:
    return None
  if len(permutations_scids) > 1:
    raise Exception(f"Multiple permutations sections found: {permutations_scids}")
  permutations_scid = permutations_scids[0]
  nonoffense_scid = get_key_where_translation_contains(vb_json, 'Non-offenses')
  nonoffense_scid_index = vb_json['keys_order'].index(nonoffense_scid)
  fpath = VB_PERMUTATIONS_FOLDER.joinpath(
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
      footnotes.append(render_note_as_markdown(vb_json['comment_text'][key], VB_PERMUTATIONS_FOLDER))
      text += f"[^{len(footnotes)}] "
    ret += line.replace("{}", text)
    key_index += 1
  ret = "\nTranslated by [Ajahn Brahmali](" + \
    sc_link_for_ref(permutations_scid) + \
    ")\n\n" + markdownify.markdownify(ret)
  if footnotes:
    ret += "\n## Note"
    if len(footnotes) > 1:
      ret += "s"
    ret += "\n"
    for i, footnote in enumerate(footnotes):
      ret += f"\n[^{i + 1}]: {footnote}\n"
  write_md_file(fpath, permutations_scid, key, ret)
  return permutations_scid

def render_rule(category: dict, rule_meta: dict, number: int, vb_json: dict):
  ascii_rulename = f" {unidecode(category['root_name'])} {number} "
  sangha = "Bhikkhu"
  origin_story_scid = None
  permutations_scid = None
  if rule_meta['uid'].startswith('pli-tv-bi'):
    sangha = "Bhikkhuni"
    origin_story_scid = render_origin_story_for_rule(vb_json)
    permutations_scid = render_permutations_for_rule(vb_json)
  if ' Sekhiya ' not in ascii_rulename and sangha == "Bhikkhu":
    vb_file = path_to_suddhaso_file_starting_with(f"VB{ascii_rulename}")
    SCUID_SEGMENT_PATHS.add(rule_meta['uid'], None, vb_file)
  uid = rule_meta['uid'].replace('-vb-', '-pm-')
  rule_file = PM_FOLDER.joinpath(
    f"{sangha}{ascii_rulename}({RULENAMES[rule_meta['uid']]}).md")
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
    for j, word in enumerate(line):
      # Handle def link start
      if j == start_of_link:
        rendered_root += "["
      
      # Render the word itself
      rendered_root += word
      
      # Add variant to footnotes if present
      if j in variant_map:
        footnotes.append(" → ".join(variant_map[j]))
      
      # Add link end and variant footnotes as needed
      if j == end_of_link:
        rendered_root += abs_path_to_obsidian_link_text(current_def[1], PM_FOLDER)
        k += 1
        (current_def, def_in_scope, start_of_link, end_of_link) = _get_def(k)
        if j in variant_map:
          # Render footnotes at the end of a link outside the link
          rendered_root += f"[^{len(footnotes)}]"
      elif j in variant_map:
        overlaps_link = def_in_scope and (start_of_link <= j < end_of_link)
        # Render footnotes inside a link as unicode superscripts
        rendered_root += superscript_number(len(footnotes)) if overlaps_link else f"[^{len(footnotes)}]"
      
      # Add space between words
      if j < len(line) - 1:
        rendered_root += " "

  ret += rendered_root
  ret += '\n\n'
  num_variants = len(footnotes)
  for k in rule_keys:
    ret += vb_json['translation_text'].get(k, '').strip()
    if k in vb_json.get('comment_text', {}):
      footnotes.append(render_note_as_markdown(vb_json['comment_text'][k], PM_FOLDER))
      ret += f"[^{len(footnotes)}]"
    ret += '\n'
  ret += f"~ [Ajahn Brahmali's translation]({sc_link_for_ref(rule_keys[0])})\n\n"
  ret += "## Vibhaṅga\n\n"
  if origin_story_scid:
    ret += (f"  - {full_obsidian_style_link_for_scuid(origin_story_scid, PM_FOLDER)}"
      " ~ Ajahn Brahmali's translation\n")
  if permutations_scid:
    ret += (f"  - {full_obsidian_style_link_for_scuid(permutations_scid, PM_FOLDER)}"
      " ~ Ajahn Brahmali's translation\n")
  if ' Sekhiya ' not in ascii_rulename and sangha == "Bhikkhu":
    ret += (f"  - {full_obsidian_style_link_for_scuid(rule_meta['uid'], PM_FOLDER)}"
      " ~ Bhante Suddhaso's translation (pdf)\n")
  if nonoffenses_scid:
    ret += "  - " + full_obsidian_style_link_for_scuid(nonoffenses_scid, PM_FOLDER)
    ret += " ~ Ajahn Brahmali's translation\n"
  ret += "\n"
  if footnotes:
    if num_variants > 0:
      ret += "## Variants\n\n"
      for i, footnote in enumerate(footnotes):
        if i >= num_variants:
          break
        ret += f"[^{i+1}]: {footnote}\n"
    if len(footnotes) > num_variants:
      ret += "\n## Translator's Notes\n\n"
      for i, footnote in enumerate(footnotes):
        # This doesn't go in the render_note_as_markdown function because
        # it relies on this metadata and these links only appear in the rules
        if "Appendix on Individual Bhikkhunī Rules" in footnote:
          appendix_link = "[Appendix on Individual Bhikkhunī Rules]"
          appendix_link += "(../../Ajahn%20Brahmali/"
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
