import pytest

from khandhakas.planning import duplicated_stems, plan_notes, planned_keys, walk
from khandhakas.rules import index_rules
from khandhakas.titles import folder_name, heading_title, note_stem, toc_stem, unit_title

from tests.helpers import FRESH, H2, H3, P, RULE, keys, make_text

HEADER = [
  ("0.1", "<article id='x'><header><ul><li class='collection'>{}</li>", "Collection"),
  ("0.2", "<li class='division'>{}</li></ul>", "Division"),
  ("0.3", "<h1 class='sutta-title'>{}</h1></header>", "The chapter"),
]
UDDANA = [
  ("9.1", "<p class='endsutta'>{}</p>", "The chapter is finished.", "Khandhako niṭṭhito."),
  ("9.2", "<section class='uddana'><p class='uddana-intro'>{}</p>", "This is the summary:", "Tassuddānaṁ"),
  ("9.3", "<blockquote class='uddanagatha'><p><span class='verse-line'>{}</span></p></blockquote></section>", "“Verses.”", "Gāthā"),
  ("9.4", "<p class='endsutta'>{}</p></article>", "The chapter is finished.", "Khandhako niṭṭhito."),
]


def plan(*rows, uddana=UDDANA):
  text = make_text(*HEADER, *rows, *uddana)
  return text, plan_notes(text, index_rules(text), "Uddāna of Kd 99")


##
# titles
##

def test_folder_name():
  assert folder_name("Kd 4", "Pavāraṇākkhandhaka") == "Kd 4 Pavarana"
  assert folder_name("Kd 1", "Mahākhandhaka") == "Kd 1 Maha"
  assert folder_name("Kd 17", "Saṁghabhedakakkhandhaka") == "Kd 17 Samghabhedaka"
  assert folder_name("Kd 20", " Bhikkhunikkhandhaka ") == "Kd 20 Bhikkhuni"


def test_heading_title():
  text = make_text(
    ("1.0", H2, "47. <i lang='pi' translate='no'>Paṇḍakas</i> ", "47. Paṇḍakavatthu"),
    ("2.0", H2, "", "18. Licchavīvatthu"),
    ("3.0", H3, "", ""),
  )
  assert [heading_title(text, key) for key in text.keys] == ["Paṇḍakas", "Licchavīvatthu", ""]


def test_units_are_named_after_their_first_rule():
  text = make_text(
    ("1.1", P, "At that time the nuns were sitting cross-legged."),
    ("1.2", RULE, "“A nun shouldn’t sit cross-legged. If she does, it’s an offense.”"),
    ("1.3", RULE, "“I allow a nun to sit half-cross-legged.”"),
  )
  assert unit_title(text, text.keys) == "A nun shouldn’t sit cross-legged"


def test_units_without_a_translated_rule_are_named_after_their_opening():
  text = make_text(
    ("1.1", "<p class='namo'>{}</p>", "Homage to the Buddha."),
    ("1.2", "<p>{}", "The Buddha then said, "),
    ("1.3", "{}</p>", "“At one time in Benares there was a king. He was rich.”"),
    ("1.4", RULE, ""),
  )
  assert unit_title(text, text.keys) == "The Buddha then said, “At one time in Benares there was a king"


def test_unit_titles_dont_put_a_space_after_a_dash():
  text = make_text(("1.1", "<p class='rule'>{}", "“You shouldn’t do procedures—"), ("1.2", "{}</p>", "censure or demotion.”"))
  assert unit_title(text, text.keys) == "You shouldn’t do procedures—censure or demotion"


def test_unit_titles_stop_adding_lines_once_theyre_long_enough():
  text = make_text(("1.1", "<p>{}", "At that time the monks from the group of six"), ("1.2", "{}</p>", "were bathing."))
  assert unit_title(text, text.keys) == "At that time the monks from the group of six"


def test_units_are_named_after_what_the_text_says_has_finished():
  text = make_text(
    ("1.1", RULE, "“You shouldn’t eat garlic.”"),
    ("1.2", "<p class='end'>{}</p>", "The first wonder is finished. "),
  )
  assert unit_title(text, text.keys) == "The first wonder"
  assert unit_title(text, keys("1.1")) == "You shouldn’t eat garlic"


def test_units_arent_named_after_the_end_of_a_section_for_recitation():
  for ending in ["The first section for recitation is finished.", "These five contracted sections are finished."]:
    text = make_text(("1.1", P, "They told the Buddha."), ("1.2", "<p class='end'>{}</p>", ending))
    assert unit_title(text, text.keys) == "They told the Buddha"


def test_unit_title_of_nothing():
  assert unit_title(make_text(("1.1", P, "")), keys("1.1")) == "Untitled"
  assert unit_title(make_text(), []) == "Untitled"


def test_note_stem():
  assert note_stem((3, 17, 7), "A nun shouldn’t sit cross-legged", is_heading=False) == "3.17.7 - A nun shouldn't sit cross-legged"
  assert note_stem((2,), "The eight important principles", is_heading=True) == "2 - The eight important principles"


def test_note_stem_allows_headings_longer_names():
  title = "word " * 30
  assert len(note_stem((1,), title, is_heading=False)) == len("1 - ") + 69
  assert len(note_stem((1,), title, is_heading=True)) == len("1 - ") + 99


def test_toc_stem():
  assert toc_stem("The chapter on nuns ") == "0 - The chapter on nuns"


##
# planning
##

def test_a_heading_with_one_unit_under_it_is_one_note():
  text, notes = plan(
    ("0.4", H2, "1. First heading", "1. Paṭhama"),
    ("1.1.1", P, "At that time.", FRESH),
    ("1.1.2", RULE, "“A rule.”", "“Sikkhāpadan”ti."),
  )
  first, uddana = notes
  assert (first.number, first.title, first.stem) == ((1,), "First heading", "1 - First heading")
  assert first.heading_key == keys("0.4")[0]
  assert first.keys == keys("1.1.1", "1.1.2")
  assert first.children == []
  assert first.start_key == keys("0.4")[0]


def test_the_summary_verses_get_the_last_note():
  text, notes = plan(("0.4", H2, "1. First heading"), ("1.1.1", P, "At that time.", FRESH))
  uddana = notes[-1]
  assert (uddana.number, uddana.title, uddana.stem) == ((2,), "Uddāna of Kd 99", "2 - Uddana of Kd 99")
  assert uddana.heading_key is None
  assert uddana.keys == keys("9.1", "9.2", "9.3", "9.4")
  assert uddana.start_key == keys("9.1")[0]


def test_without_summary_verses_the_ending_goes_in_the_last_note():
  ending = [("9.1", "<p class='endsutta'>{}</p></article>", "The chapter is finished.")]
  text, notes = plan(
    ("0.4", H2, "1. First"), ("1.1.1", P, "One.", FRESH),
    ("1.2.0", H3, "Sub"), ("1.2.1", P, "Two.", FRESH),
    uddana=ending,
  )
  assert len(notes) == 1
  assert notes[0].children[0].keys == keys("1.2.1", "9.1")


def chapter():
  return plan(
    ("0.4", H2, "1. First heading"),
    ("1.1.1", P, "At that time.", FRESH),
    ("1.1.2", RULE, "“The first rule.”", "“Dātabban”ti."),
    ("2.1.0", H2, "2. Second heading"),
    ("2.1.1", P, "This is the proper conduct:", "Tatrāyaṁ sammāvattanā—"),
    ("2.2.0", H3, "Sub A"),
    ("2.2.1", P, "He should get up early.", "Kālasseva vuṭṭhāya"),
    ("2.3.0", H3, "Sub B"),
    ("2.3.1", P, "At that time.", FRESH),
    ("2.3.2", RULE, "“You shouldn’t sit cross-legged.”", "“Na pallaṅkena nisīditabban”ti."),
    ("2.4.1", P, "At that time.", FRESH),
    ("2.4.2", RULE, "“I allow restrooms.”", "“Anujānāmi vaccakuṭin”ti."),
  )


def test_a_chapter_becomes_a_tree_of_numbered_notes():
  text, notes = chapter()
  assert [(note.number, note.stem) for note in walk(notes)] == [
    ((1,), "1 - First heading"),
    ((2,), "2 - Second heading"),
    ((2, 1), "2.1 - Sub A"),
    ((2, 2), "2.2 - Sub B"),
    ((2, 2, 1), "2.2.1 - You shouldn't sit cross-legged"),
    ((2, 2, 2), "2.2.2 - I allow restrooms"),
    ((3,), "3 - Uddana of Kd 99"),
  ]


def test_a_headings_introduction_goes_in_its_own_note():
  text, notes = chapter()
  second = notes[1]
  assert second.keys == keys("2.1.1")
  assert [child.title for child in second.children] == ["Sub A", "Sub B"]


def test_a_heading_with_several_units_is_an_index_of_them():
  text, notes = chapter()
  sub_b = notes[1].children[1]
  assert sub_b.keys == []
  assert sub_b.heading_key == keys("2.3.0")[0]
  assert [child.keys for child in sub_b.children] == [keys("2.3.1", "2.3.2"), keys("2.4.1", "2.4.2")]
  assert all(child.heading_key is None for child in sub_b.children)


def test_notes_know_their_parents():
  text, notes = chapter()
  second = notes[1]
  sub_b = second.children[1]
  assert second.parent is None
  assert sub_b.parent is second
  assert all(child.parent is sub_b for child in sub_b.children)


def test_every_segment_is_planned_once_and_in_order():
  text, notes = chapter()
  assert planned_keys(notes) == text.keys[3:]


def test_text_before_the_first_heading_gets_a_note():
  text, notes = plan(
    ("1.1.1", P, "One hundred years later.", "Tena kho pana samayena vassasataparinibbute"),
    ("1.2.0", H2, "Why not"), ("1.2.1", P, "At that time.", FRESH),
  )
  assert [(note.number, note.title) for note in notes[:2]] == [((1,), "One hundred years later"), ((2,), "Why not")]


def test_a_blank_heading_is_named_after_its_text():
  text, notes = plan(("0.4", H3, "", ""), ("1.1.1", P, "At that time the nuns traveled.", FRESH))
  assert notes[0].title == "At that time the nuns traveled"
  assert notes[0].heading_key == keys("0.4")[0]


def test_a_chapter_needs_headings_and_text():
  text = make_text(*HEADER, ("1.1.1", P, "No headings here."))
  with pytest.raises(AssertionError, match="no headings"):
    plan_notes(text, index_rules(text), "Uddāna")
  text = make_text(*HEADER, *UDDANA)
  with pytest.raises(AssertionError, match="nothing between"):
    plan_notes(text, index_rules(text), "Uddāna")


def test_duplicated_stems():
  stems = ["1 - The first section", "1 - the First Section", "2 - Uddana", "0 - The chapter"]
  assert duplicated_stems(stems) == {"1 - the first section"}
  assert duplicated_stems([]) == set()
