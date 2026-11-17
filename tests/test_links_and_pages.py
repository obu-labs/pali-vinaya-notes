from pathlib import Path

from khandhakas.links import complete_bare_links, link_rule_mentions, rule_uid_for_mention
from khandhakas.model import Note
from khandhakas.pages import (
  link_to,
  render_breadcrumbs,
  render_contents,
  render_footnotes,
  render_note_page,
  render_toc_page,
)

RULE_NOTES = {"pli-tv-bu-vb-ss13": "../Pm/Bu%20Ss%2013.md", "pli-tv-bi-vb-pc21": "../Pm/Bi%20Pc%2021.md"}
SEGMENTS_WITH_NOTES = {"pli-tv-bu-vb-ss13:1.2.3", "pli-tv-bi-vb-pc21:1.16.1"}
SC = "https://suttacentral.net"


def link(note: str) -> str:
  return link_rule_mentions(note, RULE_NOTES.get, SEGMENTS_WITH_NOTES.__contains__)


##
# links
##

def test_complete_bare_links():
  assert complete_bare_links(f"<a href='{SC}/pli-tv-kd7#6.1.1'>Kd 7:6.1.1</a>") \
    == f"<a href='{SC}/pli-tv-kd7/en/brahmali#6.1.1'>Kd 7:6.1.1</a>"


def test_complete_bare_links_leaves_complete_links_alone():
  for href in [f"{SC}/pli-tv-kd7/en/brahmali#6.1.1", f"{SC}/pli-tv-kd7", f"{SC}/an8.16#1.1", "No links here"]:
    assert complete_bare_links(href) == href


def test_rule_uid_for_mention():
  assert rule_uid_for_mention("Bu", "Ss", "13") == "pli-tv-bu-vb-ss13"
  assert rule_uid_for_mention("Bi", "Pc", "21") == "pli-tv-bi-vb-pc21"


def test_plain_mentions_of_rules_are_linked():
  assert link("See Bu Ss 13 and Bi Pc 21.") == (
    'See <a href="../Pm/Bu%20Ss%2013.md">Bu Ss 13</a>'
    ' and <a href="../Pm/Bi%20Pc%2021.md">Bi Pc 21</a>.'
  )


def test_mentions_of_rules_we_have_no_note_for_are_left_alone():
  for note in ["See Bu Pc 999.", "Bu Ss 130", "Kd 13", "Subu Ss 13"]:
    assert link(note) == note


def test_links_to_a_rule_go_to_its_note():
  assert link(f"See <a href='{SC}/pli-tv-bu-vb-ss13/en/brahmali'>Bu Ss 13</a>.") \
    == 'See <a href="../Pm/Bu%20Ss%2013.md">Bu Ss 13</a>.'


def test_links_to_a_segment_we_have_a_note_for_are_left_for_later():
  href = f"{SC}/pli-tv-bu-vb-ss13/en/brahmali#1.2.3"
  assert link(f"<a href='{href}'>Bu Ss 13:1.2.3</a>") == f'<a href="{href}">Bu Ss 13:1.2.3</a>'


def test_links_to_any_other_segment_of_a_rule_go_to_its_note():
  assert link(f'<a href="{SC}/pli-tv-bu-vb-ss13/en/brahmali#0.5">Bu Ss 13:0.5</a>') \
    == '<a href="../Pm/Bu%20Ss%2013.md">Bu Ss 13:0.5</a>'


def test_mistyped_links_are_corrected():
  assert link(f"<a href='{SC}/Bi Pc 21/en/brahmali#1.16.1'>Bi Pc 21</a>") \
    == f'<a href="{SC}/pli-tv-bi-vb-pc21/en/brahmali#1.16.1">Bi Pc 21</a>'
  assert link(f"<a href='{SC}/Bi Pc 21/en/brahmali'>Bi Pc 21</a>") == '<a href="../Pm/Bi%20Pc%2021.md">Bi Pc 21</a>'


def test_other_links_are_left_alone():
  for note in [
    f"<a href='{SC}/an8.16/en/brahmali#1.1'>AN 8.16</a>",
    f"<a href='{SC}/pli-tv-kd1/en/brahmali#1.2.3'>Kd 1:1.2.3</a>",
    f"<a href='{SC}/pli-tv-bu-vb-pc999/en/brahmali'>Bu Pc 999</a>",
  ]:
    assert link(note) == note


##
# pages
##

FOLDER = Path("/vault/Canon (Pali)/Khandhaka/Kd 20 Bhikkhuni")


def note(number, stem, **kwargs) -> Note:
  return Note(number, stem, stem=stem, path=FOLDER / f"{stem}.md", **kwargs)


def family():
  toc = note((0,), "0 - The chapter on nuns")
  parent = note((3,), "3 - The allowance", heading_key="kd:2.1.0")
  child = note((3, 1), "3.1 - Various regulations (for nuns)", heading_key="kd:23.1.0", parent=parent)
  first = note((3, 1, 1), "3.1.1 - A nun shouldn't sit cross-legged", keys=["kd:27.2.1", "kd:27.2.8"], parent=child)
  second = note((3, 1, 2), "3.1.2 - A nun shouldn't defecate in a restroom", keys=["kd:27.3.1"], parent=child)
  parent.children = [child]
  child.children = [first, second]
  return toc, parent, child, first, second


def test_link_to():
  toc, parent, child, first, second = family()
  assert link_to(toc, FOLDER) == "[0 - The chapter on nuns](0%20-%20The%20chapter%20on%20nuns.md)"
  assert link_to(toc, FOLDER, "Kd 20") == "[Kd 20](0%20-%20The%20chapter%20on%20nuns.md)"
  assert link_to(child, FOLDER) \
    == "[3.1 - Various regulations (for nuns)](3.1%20-%20Various%20regulations%20%28for%20nuns%29.md)"


def test_link_to_from_another_folder():
  toc = family()[0]
  assert link_to(toc, FOLDER.parent / "Kd 1 Maha") \
    == "[0 - The chapter on nuns](../Kd%2020%20Bhikkhuni/0%20-%20The%20chapter%20on%20nuns.md)"


def test_render_breadcrumbs():
  toc, parent, child, first, second = family()
  assert render_breadcrumbs(first, toc, "Kd 20: The chapter on nuns", FOLDER) == "\n" + " › ".join([
    link_to(toc, FOLDER, "Kd 20: The chapter on nuns"), link_to(parent, FOLDER), link_to(child, FOLDER),
  ]) + "\n\n"
  assert render_breadcrumbs(parent, toc, "Kd 20", FOLDER) == f"\n{link_to(toc, FOLDER, 'Kd 20')}\n\n"


def test_render_contents():
  toc, parent, child, first, second = family()
  assert render_contents([parent], FOLDER) == "".join([
    f"- {link_to(parent, FOLDER)}\n",
    f"  - {link_to(child, FOLDER)}\n",
    f"    - {link_to(first, FOLDER)}\n",
    f"    - {link_to(second, FOLDER)}\n",
  ])
  assert render_contents([], FOLDER) == ""


def test_render_footnotes():
  assert render_footnotes(["One.", "Two."]) == "\n## Footnotes\n\n[^1]: One.\n[^2]: Two.\n"
  assert render_footnotes([]) == ""


def page(note, next_note=None, body="", footnotes=()):
  return render_note_page(
    note, next_note, FOLDER,
    breadcrumbs="\nCRUMBS\n\n", heading="## Heading\n\n",
    body=body, footnotes=footnotes, source_url="https://example.com/#1",
  )


def test_a_note_with_text_credits_it_and_links_to_the_next_note():
  toc, parent, child, first, second = family()
  assert page(first, second, "The text.[^1]", ["A note."]) == "".join([
    "\nCRUMBS\n\n## Heading\n\n",
    "The text.[^1]",
    "\n\n~ [Ajahn Brahmali's translation](https://example.com/#1)\n",
    f"\n**Next:** {link_to(second, FOLDER)}\n",
    "\n## Footnotes\n\n[^1]: A note.\n",
  ])


def test_the_last_note_has_no_next():
  second = family()[4]
  assert page(second, None, "The text.") == \
    "\nCRUMBS\n\n## Heading\n\nThe text.\n\n~ [Ajahn Brahmali's translation](https://example.com/#1)\n"


def test_an_index_lists_its_contents_and_its_source():
  toc, parent, child, first, second = family()
  assert page(child, first) == "".join([
    "\nCRUMBS\n\n## Heading\n\n",
    render_contents([first, second], FOLDER),
    "\nSource: <https://example.com/#1>\n",
  ])


def test_an_index_with_an_introduction_has_both():
  toc, parent, child, first, second = family()
  child.keys = ["kd:23.1.1"]
  assert page(child, first, "The introduction.") == "".join([
    "\nCRUMBS\n\n## Heading\n\n",
    "The introduction.",
    "\n\n~ [Ajahn Brahmali's translation](https://example.com/#1)\n",
    "\n### Contents\n\n",
    render_contents([first, second], FOLDER),
    f"\n**Next:** {link_to(first, FOLDER)}\n",
  ])


def test_render_toc_page():
  toc, parent, child, first, second = family()
  assert render_toc_page("The <i>Bhikkhunikkhandhaka</i> is about nuns.", [parent], FOLDER, "https://example.com/kd20") == "".join([
    "\n## Summary\n\n",
    "The *Bhikkhunikkhandhaka* is about nuns.",
    "\n\n## Table of Contents\n\n",
    render_contents([parent], FOLDER),
    "\nSource: <https://example.com/kd20>\n",
  ])


def test_render_toc_page_without_a_blurb():
  assert render_toc_page(None, [], FOLDER, "https://example.com/kd20") \
    == "\n## Summary\n\n\n\n## Table of Contents\n\n\nSource: <https://example.com/kd20>\n"
