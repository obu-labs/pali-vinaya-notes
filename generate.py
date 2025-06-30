#!/bin/python3

import argparse
from datetime import datetime
from pathlib import Path

import mdutils
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
  categories = suttacentral.get_rule_categories()
  bhikkhuni_patimokkha = suttacentral.get_vb_json('pli-tv-bi-pm')
  for category in categories:
    if category['uid'] == "pli-tv-bu-vb-as":
      continue # TODO: Handle the adhikaraṇasamathas
    print(f"  Fetching Bhikkhu {category['root_name']} rules...")
    rules = suttacentral.get_rules_for_category(category['uid'])
    for i, rule in enumerate(rules):
      print(f"    Writing {category['root_name']} rule {i+1}...")
      vb_json = suttacentral.get_vb_json(rule['uid'])
      suttacentral.render_rule(category, rule, i+1, vb_json)
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
    for i, rule in enumerate(rules):
      print(f"    Writing {category['root_name']} rule {i+1}...")
      vb_id = rule['uid'].replace('-pm-', '-vb-')
      if vb_id in vibhangas:
        vb_json = suttacentral.get_vb_json(vb_id)
        suttacentral.render_rule(category, vibhangas[vb_id], i+1, vb_json)
      else:
        suttacentral.render_copied_bi_rule(bhikkhuni_patimokkha, category, rule, i+1)

  # Write a real README?
  PALI_FOLDER.joinpath("README.md").write_text(f"""

Automatically generated on {datetime.now().strftime('%Y-%m-%d')}.

""")
  print("  Done.")

  print("Rewriting SuttaCentral Links in Generated Files...")
  mdutils.rewrite_suttacentral_links_in_folder(PALI_FOLDER)
  print("  Done.")
