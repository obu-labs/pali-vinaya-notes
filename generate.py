#!/bin/python3

import argparse
from datetime import datetime
from pathlib import Path

from vnmutils import mdutils
import suttacentral

if __name__ == "__main__":
  arg_parser = argparse.ArgumentParser(
    description="Generates the Pali Canon Vinaya Folder from SuttaCentral data",
  )
  arg_parser.add_argument(
    'outputdir',
    type=Path,
    help="Output directory",
    default=Path("./Canon (Pali)"),
    nargs='?',
  )
  args = arg_parser.parse_args()

  PALI_FOLDER = args.outputdir
  if PALI_FOLDER.exists():
    print(f"{PALI_FOLDER} already exists! Please `rm -rf` it before running this script.")
    exit(1)
  PALI_FOLDER.mkdir()

  suttacentral.set_global_folders(PALI_FOLDER)

  print("Generating Pātimokkha Rule Notes...")
  print("  Fetching rule categories...")
  categories = suttacentral.get_rule_categories('pli-tv-bu-vb')
  bhikkhuni_patimokkha = suttacentral.get_vb_json('pli-tv-bi-pm')
  for i, category in enumerate(categories):
    if category['uid'] == "pli-tv-bu-vb-as":
      continue # TODO: https://github.com/obu-labs/pali-vinaya-notes/issues/1
    suttacentral.render_category_metafile(category)
    print(f"  Fetching Bhikkhu {category['root_name']} rules...")
    rules = suttacentral.get_rules_for_category(category['uid'])
    for j, rule in enumerate(rules):
      print(f"    Writing {category['root_name']} rule {j+1}...")
      vb_json = suttacentral.get_vb_json(rule['uid'])
      if j < len(rules) - 1:
        next_file = suttacentral.pm_file_for_scid(rules[j+1]['uid'])
      elif i < len(categories) - 2:
        next_file = suttacentral.file_for_category(categories[i+1])
      else:
        next_file = None
      suttacentral.render_rule(category, rule, j+1, vb_json, next_file)
  
  bi_categories = suttacentral.get_rule_categories('pli-tv-bi-vb')
  for i, category in enumerate(bi_categories):
    if category['uid'] == "pli-tv-bi-vb-as":
      continue
    rules = suttacentral.get_bhikkhuni_rules_in_category(
      category['uid'].replace('-bu-', '-bi-').replace('-vb-', '-pm-')
    )
    # Populate the rule names that come from the parallel monk's rule
    for j, rule in enumerate(rules):
      if rule['uid'].replace('-pm-', '-vb-') in suttacentral.RULENAMES:
        continue
      bu_parallel_id = suttacentral.get_bu_parallel_for_rule(rule)
      suttacentral.RULENAMES[rule['uid'].replace('-pm-', '-vb-')] = suttacentral.RULENAMES[bu_parallel_id.replace('-pm-', '-vb-')]
    suttacentral.render_category_metafile(category)
    category['root_name'] = category['root_name'].replace('aP', 'a P')
    print(f"  Fetching Bhikkhuni {category['root_name']} rules...")
    vibhangas = suttacentral.get_rules_for_category(
      category['uid'].replace('-bu-', '-bi-')
    )
    vibhangas = {
      vibhanga['uid']: vibhanga for vibhanga in vibhangas
    }
    for j, rule in enumerate(rules):
      print(f"    Writing {category['root_name']} rule {j+1}...")
      vb_id = rule['uid'].replace('-pm-', '-vb-')
      if j < len(rules) - 1:
        next_file = suttacentral.pm_file_for_scid(rules[j+1]['uid'].replace('-pm-', '-vb-'))
      elif i < len(bi_categories) - 2:
        next_file = suttacentral.file_for_category(bi_categories[i+1])
      else:
        next_file = None
      if vb_id in vibhangas:
        vb_json = suttacentral.get_vb_json(vb_id)
        suttacentral.render_rule(category, vibhangas[vb_id], j+1, vb_json, next_file)
      else:
        suttacentral.render_copied_bi_rule(bhikkhuni_patimokkha, category, rule, j+1, next_file)

  PALI_FOLDER.joinpath("README.md").write_text(f"""
This folder contains the Vinaya of the Pāli Canon as a collection of markdown notes generated from Ajahn Brahmali's translation on SuttaCentral.
For more information about the Vinaya and his translation, see [his general introduction](../Ajahn%20Brahmali/General/General%20introduction%20to%20the%20Monastic%20Law.md).

This folder was automatically generated from SuttaCentral data on **{datetime.now().strftime('%Y-%m-%d')}** by:
https://github.com/obu-labs/pali-vinaya-notes

For feedback on the translations, please write to
[the SuttaCentral Forum's "Feedback" Category](https://discourse.suttacentral.net/c/feedback/19).
For issues with these markdown files, feel free to open
[an Issue on GitHub](https://github.com/obu-labs/pali-vinaya-notes/issues).

To support SuttaCentra's work, consider [making a donation](https://suttacentral.net/donations?lang=en).
""")
  print("  Done.")

  print("Rewriting SuttaCentral Links in Generated Files...")
  mdutils.rewrite_suttacentral_links_in_folder(PALI_FOLDER)
  print("  Done.")

  print("Outputting the SCID Mapping to a json file for use by other modules...")
  suttacentral.DATA_FOLDER.joinpath("scidmap.json").write_text(
    mdutils.SCUID_SEGMENT_PATHS.to_json(PALI_FOLDER.parent)
  )
  print("  Done.")
