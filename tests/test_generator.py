"""Tests of the part that does the fetching and the writing,
with a stand-in for the `suttacentral` module it does those through."""

import importlib
import sys
import types

import pytest

from tests.helpers import FRESH, H2, P, RULE, UID, keys, make_json

SC = "https://suttacentral.net"
PLEX = {
  'uid': UID,
  'acronym': 'Kd 99',
  'original_title': 'Parikappakkhandhaka',
  'translated_title': 'The chapter of examples ',
  'blurb': 'The <i>Parikappakkhandhaka</i> is made up.',
}


def chapter() -> dict:
  return make_json(
    ("0.1", "<article id='x'><header><ul><li class='collection'>{}</li>", "Collection"),
    ("0.2", "<li class='division'>{}</li></ul>", "Division"),
    ("0.3", "<h1 class='sutta-title'>{}</h1></header>", "The chapter of examples"),
    ("0.4", H2, "1. Garlic", "1. Lasuṇavatthu"),
    ("1.1.1", P, f"At that time (<a href='{SC}/pli-tv-kd7#6.1.1'>Kd 7:6.1.1</a>).", FRESH, "See Bu Ss 13."),
    ("1.1.2", RULE, "“You shouldn’t eat garlic.”", "“Na, bhikkhave, lasuṇaṁ khāditabban”ti.", "", "lasuṇaṁ → lasunaṁ"),
    ("2.1.0", H2, "2. Sunshades", "2. Chattavatthu"),
    ("2.1.1", P, "At that time.", FRESH),
    ("2.1.2", RULE, "“I allow sunshades.”", "“Anujānāmi, bhikkhave, chattan”ti.", "", "can't parse this"),
    ("2.1.3", "<p class='endsutta'>{}</p>", "The chapter is finished."),
    ("2.1.4", "<section class='uddana'><p class='uddana-intro'>{}</p></section>", "This is the summary:"),
    ("2.1.5", "<p class='endsutta'>{}</p></article>", "The chapter is finished."),
  )


@pytest.fixture
def generator(tmp_path, monkeypatch):
  """The khandhakas.generator module, working through a fake `suttacentral`"""
  fake = types.ModuleType("suttacentral")
  fake.disk_memoizer = types.SimpleNamespace(cache=lambda: lambda function: function)
  fake.KD_FOLDER = tmp_path / "Canon (Pali)" / "Khandhaka"
  fake.RULENAMES = {"pli-tv-bu-vb-ss13": "Corrupting Families"}
  fake.pm_file_for_scid = lambda uid: tmp_path / "Canon (Pali)" / "Patimokkha" / f"{uid}.md"
  fake.render_note_as_markdown = lambda note, cwd, strict=True: f"NOTE<{note}>\n\nstrict={strict}"
  fake.sc_link_for_ref = lambda ref: f"https://sc.example/{ref}"
  fake.get_vb_json = lambda uid: chapter()
  fake.written = []

  def build_variant_map(words, key, data):
    if "can't parse" in data['variant_text'][key]:
      raise Exception("Couldn't find it")
    return {2: ["lasuṇaṁ", "lasunaṁ"]}
  fake.build_variant_map = build_variant_map

  def write_md_file(path, start, end, content):
    path.write_text(content, encoding='utf-8')
    fake.written.append((path.name, start, end))
  fake.write_md_file = write_md_file

  monkeypatch.setitem(sys.modules, "suttacentral", fake)
  sys.modules.pop("khandhakas.generator", None)
  yield importlib.import_module("khandhakas.generator")
  sys.modules.pop("khandhakas.generator", None)


def read(folder, stem):
  return (folder / f"{stem}.md").read_text(encoding='utf-8')


def test_a_khandhaka_plans_its_notes(generator):
  kd = generator.Khandhaka(PLEX, chapter())
  assert kd.folder == generator.suttacentral.KD_FOLDER / "Kd 99 Parikappa"
  assert (kd.toc.title, kd.toc.stem) == ("The chapter of examples", "0 - The chapter of examples")
  assert [note.stem for note in kd.all_notes()] == [
    "0 - The chapter of examples", "1 - Garlic", "2 - Sunshades", "3 - Uddana of Kd 99",
  ]
  assert all(note.path is None for note in kd.all_notes())
  kd.set_paths()
  assert kd.notes[0].path == kd.folder / "1 - Garlic.md"


def test_a_khandhaka_completes_the_links_in_its_translation(generator):
  kd = generator.Khandhaka(PLEX, chapter())
  assert f"{SC}/pli-tv-kd7/en/brahmali#6.1.1" in kd.text.en(keys("1.1.1")[0])


def test_a_khandhaka_that_cant_be_planned_says_which_it_is(generator):
  data = chapter()
  data['html_text'] = {key: html.replace("h2", "h5") for key, html in data['html_text'].items()}
  with pytest.raises(AssertionError, match=f"{UID}: Found no headings"):
    generator.Khandhaka(PLEX, data)


def test_render_writes_a_file_for_every_note(generator):
  kd = generator.Khandhaka(PLEX, chapter())
  kd.set_paths()
  kd.render()
  assert generator.suttacentral.written == [
    ("0 - The chapter of examples.md", UID, None),
    ("1 - Garlic.md", f"{UID}:0.4", f"{UID}:1.1.2"),
    ("2 - Sunshades.md", f"{UID}:2.1.0", f"{UID}:2.1.2"),
    ("3 - Uddana of Kd 99.md", f"{UID}:2.1.3", f"{UID}:2.1.5"),
  ]
  assert sorted(path.name for path in kd.folder.iterdir()) == sorted(name for name, _, _ in generator.suttacentral.written)


def test_render_writes_the_table_of_contents(generator):
  kd = generator.Khandhaka(PLEX, chapter())
  kd.set_paths()
  kd.render()
  assert read(kd.folder, "0 - The chapter of examples") == "\n".join([
    "",
    "## Summary",
    "",
    "The *Parikappakkhandhaka* is made up.",
    "",
    "## Table of Contents",
    "",
    "- [1 - Garlic](1%20-%20Garlic.md)",
    "- [2 - Sunshades](2%20-%20Sunshades.md)",
    "- [3 - Uddana of Kd 99](3%20-%20Uddana%20of%20Kd%2099.md)",
    "",
    f"Source: <{SC}/{UID}/en/brahmali>",
    "",
  ])


def test_render_writes_each_note_with_its_links_and_footnotes(generator):
  kd = generator.Khandhaka(PLEX, chapter())
  kd.set_paths()
  kd.render()
  rule_note = '<a href="../../Patimokkha/pli-tv-bu-vb-ss13.md">Bu Ss 13</a>'
  assert read(kd.folder, "1 - Garlic") == "\n".join([
    "",
    "[Kd 99: The chapter of examples](0%20-%20The%20chapter%20of%20examples.md)",
    "",
    "## Garlic",
    "",
    "*1. Lasuṇavatthu*",
    "",
    f"At that time ([Kd 7:6.1.1]({SC}/pli-tv-kd7/en/brahmali#6.1.1)).[^1]",
    "",
    "> “Na, bhikkhave, lasuṇaṁ[^2] khāditabban”ti.",
    "",
    "**“You shouldn’t eat garlic.”**",
    "",
    f"~ [Ajahn Brahmali's translation](https://sc.example/{UID}:0.4)",
    "",
    "**Next:** [2 - Sunshades](2%20-%20Sunshades.md)",
    "",
    "## Footnotes",
    "",
    f"[^1]: NOTE<See {rule_note}.>",
    "",
    "    strict=False",
    "[^2]: lasuṇaṁ → lasunaṁ",
    "",
  ])


def test_variants_that_cant_be_placed_go_at_the_end_of_the_line(generator):
  kd = generator.Khandhaka(PLEX, chapter())
  kd.set_paths()
  kd.render()
  sunshades = read(kd.folder, "2 - Sunshades")
  assert "> “Anujānāmi, bhikkhave, chattan”ti.[^1]\n" in sunshades
  assert "[^1]: can't parse this\n" in sunshades
  assert "**Next:** [3 - Uddana of Kd 99]" in sunshades


def test_the_last_note_has_no_next(generator):
  kd = generator.Khandhaka(PLEX, chapter())
  kd.set_paths()
  kd.render()
  assert "**Next:**" not in read(kd.folder, "3 - Uddana of Kd 99")


def test_rules_without_a_note_arent_linked(generator):
  kd = generator.Khandhaka(PLEX, chapter())
  assert kd._href_for_rule("pli-tv-bu-vb-pc999") is None
  assert kd._href_for_rule("pli-tv-bu-vb-ss13") == "../../Patimokkha/pli-tv-bu-vb-ss13.md"


def plexes(count=22):
  collection = {**PLEX, 'uid': 'pli-tv-kd', 'acronym': 'Kd'}
  return [collection] + [
    {**PLEX, 'uid': f"pli-tv-kd{i}", 'acronym': f"Kd {i}", 'translated_title': f"Chapter {i}"}
    for i in range(1, count + 1)
  ]


def test_plan_khandhakas_tells_apart_the_notes_with_the_same_name(generator, monkeypatch):
  monkeypatch.setattr(generator, "get_kd_plex", plexes)
  khandhakas = generator.plan_khandhakas()
  assert len(khandhakas) == 22
  first, second = khandhakas[:2]
  assert [note.stem for note in first.all_notes()] == [
    "0 - Chapter 1", "1 - Garlic (Kd 1)", "2 - Sunshades (Kd 1)", "3 - Uddana of Kd 1",
  ]
  assert second.notes[0].path == second.folder / "1 - Garlic (Kd 2).md"
  assert second.folder.name == "Kd 2 Parikappa"


def test_plan_khandhakas_expects_all_twenty_two(generator, monkeypatch):
  monkeypatch.setattr(generator, "get_kd_plex", lambda: plexes(21))
  with pytest.raises(AssertionError, match="Expected 22 Khandhakas but got 21"):
    generator.plan_khandhakas()


def test_render_khandhakas_writes_them_all(generator, monkeypatch, capsys):
  monkeypatch.setattr(generator, "get_kd_plex", plexes)
  generator.render_khandhakas()
  folders = sorted(path.name for path in generator.suttacentral.KD_FOLDER.iterdir())
  assert len(folders) == 22
  assert len(generator.suttacentral.written) == 22 * 4
  assert "Writing Kd 22 (Parikappakkhandhaka)..." in capsys.readouterr().out


def test_get_kd_plex_asks_suttacentral(generator, monkeypatch):
  asked = []
  def get(url):
    asked.append(url)
    return types.SimpleNamespace(json=lambda: plexes())
  monkeypatch.setattr(generator.requests, "get", get)
  assert len(generator.get_kd_plex()) == 23
  assert asked == [f"{SC}/api/suttaplex/pli-tv-kd?language=en"]
