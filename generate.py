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
      suttacentral.render_rule(category, rule, j+1, vb_json)
  
  bi_categories = suttacentral.get_rule_categories('pli-tv-bi-vb')
  for i, category in enumerate(bi_categories):
    if category['uid'] == "pli-tv-bi-vb-as":
      continue
    suttacentral.render_category_metafile(category)
    category['root_name'] = category['root_name'].replace('aP', 'a P')
    print(f"  Fetching Bhikkhuni {category['root_name']} rules...")
    vibhangas = suttacentral.get_rules_for_category(
      category['uid'].replace('-bu-', '-bi-')
    )
    vibhangas = {
      vibhanga['uid']: vibhanga for vibhanga in vibhangas
    }
    rules = suttacentral.get_bhikkhuni_rules_in_category(
      category['uid'].replace('-bu-', '-bi-').replace('-vb-', '-pm-')
    )
    for j, rule in enumerate(rules):
      print(f"    Writing {category['root_name']} rule {j+1}...")
      vb_id = rule['uid'].replace('-pm-', '-vb-')
      if vb_id in vibhangas:
        vb_json = suttacentral.get_vb_json(vb_id)
        suttacentral.render_rule(category, vibhangas[vb_id], j+1, vb_json)
      else:
        suttacentral.render_copied_bi_rule(bhikkhuni_patimokkha, category, rule, j+1)

  PALI_FOLDER.joinpath("README.md").write_text(f"""# The Vinaya of the Pāli Canon

This folder contains notes of the Vinaya of the Pāli Canon,
primarily featuring translations by Ajahn Brahmali.
For more information about the texts and his translations, see
[his general introduction](../Ajahn%20Brahmali/General/General%20introduction%20to%20the%20Monastic%20Law.md).

This folder was automatically generated from SuttaCentral data
on **{datetime.now().strftime('%Y-%m-%d')}** by:
https://github.com/obu-labs/pali-vinaya-notes

For feedback on the translations, please write to
[the SuttaCentral Forum's "Feedback" Category](https://discourse.suttacentral.net/c/feedback/19).
For issues with these markdown files, please open
[an Issue on GitHub](https://github.com/obu-labs/pali-vinaya-notes/issues).
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
