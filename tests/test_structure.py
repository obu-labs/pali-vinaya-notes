from khandhakas.atoms import atomize
from khandhakas.markup import (
  heading_level,
  is_counted,
  is_end_marker,
  is_end_of_chapter,
  is_end_of_passage,
  is_homage,
  is_ruled_off,
  rule_tag,
  starts_story,
)
from khandhakas.model import Section
from khandhakas.rules import find_rules, index_rules, rule_end, rules_share_a_word
from khandhakas.sections import chapter_bounds, last_section, parse_sections

from tests.helpers import H2, H3, P, RULE, keys, make_text, rules_of


##
# markup
##

def test_heading_level():
  assert heading_level("<h2>{}</h2>") == 2
  assert heading_level("<section class='padabhajaniya'><h3 class='inserted-heading'>{}</h3>") == 3
  assert heading_level("<h2 class=inserted-heading’>{}</h2>") == 2 # a typo in the source


def test_titles_and_labels_arent_dividing_headings():
  assert heading_level("<h1 class='sutta-title'>{}</h1></header>") is None
  assert heading_level("<h5 class='inserted-heading help-heading'>{}</h5>") is None
  assert heading_level(P) is None


def test_rule_tag():
  assert rule_tag("<p class='rule'>{}").group(1) == 'p'
  assert rule_tag("<hr><p class='rule' data-counter='3'>{}</p>").group(0) == "<p class='rule' data-counter='3'>"
  assert rule_tag("<ol><li class='rule'>{}</li>").group(1) == 'li'
  assert rule_tag(P) is None
  assert rule_tag("<section class='kamma'><p>{}") is None


def test_end_markers():
  assert is_end_of_passage("<p class='end'>{}</p>")
  assert not is_end_of_passage("<p class='endsutta'>{}</p>")
  assert not is_end_of_passage("<p class='end'>{}</p></section>")
  assert is_end_of_chapter("<p class='endsutta'>{}</p>")
  assert is_end_of_chapter("<p class='endbook'>{}</p></article>")
  assert not is_end_of_chapter("<p class='end'>{}</p>")
  assert all(is_end_marker(f"<p class='{c}'>{{}}</p>") for c in ['end', 'endsutta', 'endbook'])
  assert not is_end_marker(P)


def test_other_markup():
  assert is_homage("<p class='namo'>{}</p>")
  assert is_counted("<p data-counter='4–15'>{}")
  assert starts_story("<hr><section class='suttanta'><p>{}")
  assert starts_story("<section class='jataka'><p>{}")
  assert not starts_story("<section class='kamma'><p>{}")


def test_is_ruled_off():
  assert is_ruled_off("<hr><p>{}")
  assert not is_ruled_off("<hr><p data-counter='3'>{}")
  assert not is_ruled_off(P)


##
# rules
##

def rule_text():
  return make_text(
    ("1.1", P, "Story.", "Tena kho pana samayena..."),
    ("1.2", "<p class='rule'>{}", "“You shouldn’t eat garlic.", "“Na, bhikkhave, lasuṇaṁ khāditabbaṁ."),
    ("1.3", "{}", "If you do,", "Yo khādeyya,"),
    ("1.4", "{}</p>", "it’s an offense.”", "āpatti dukkaṭassā”ti."),
    ("1.5", P, "He was sick.", "Tena kho pana samayena..."),
    ("1.6", "<ol><li class='rule'>{}</li>", "I allow garlic if sick.", "Anujānāmi, bhikkhave, ābādhapaccayā lasuṇaṁ khāditun"),
    ("1.7", "<li class='rule'>{}</li></ol>", "I allow sunshades.", "Anujānāmi, bhikkhave, chattan"),
  )


def test_rule_end():
  text = rule_text()
  assert rule_end(text.html, text.keys, 1, rule_tag(text.html[text.keys[1]])) == 3
  assert rule_end(text.html, text.keys, 5, rule_tag(text.html[text.keys[5]])) == 5


def test_rule_end_stops_at_the_end_of_the_keys():
  text = rule_text()
  some = text.keys[:3]
  assert rule_end(text.html, some, 1, rule_tag(text.html[some[1]])) == 2


def test_find_rules():
  text = rule_text()
  assert find_rules(text.html, text.keys) == [keys("1.2", "1.3", "1.4"), keys("1.6"), keys("1.7")]
  assert find_rules(text.html, keys("1.1", "1.5")) == []


def test_index_rules():
  index = index_rules(rule_text())
  assert index.rule_keys == set(keys("1.2", "1.3", "1.4", "1.6", "1.7"))
  assert index.common_word_parts == set() # nothing's in more than three of the rules


def test_index_rules_finds_the_words_that_are_in_too_many_rules():
  text = make_text(*(
    (f"1.{i}", RULE, "", f"Na, bhikkhave, {word} dhāretabbaṁ")
    for i, word in enumerate(["chattaṁ", "lasuṇaṁ", "upāhanā", "pallaṅko"])
  ))
  index = index_rules(text)
  assert {'bhikk', 'dhāre'} <= index.common_word_parts
  assert not {'chatt', 'lasuṇ'} & index.common_word_parts


def test_rules_share_a_word():
  text = rule_text()
  index = rules_of(text, common_words="anujānāmi bhikkhave")
  assert rules_share_a_word(text, index, keys("1.2", "1.3", "1.4"), keys("1.5", "1.6"))
  assert not rules_share_a_word(text, index, keys("1.2", "1.3", "1.4"), keys("1.7"))


def test_rules_share_a_word_ignores_common_words_and_whats_not_a_rule():
  text = rule_text()
  assert rules_share_a_word(text, rules_of(text), keys("1.6"), keys("1.7"))
  assert not rules_share_a_word(text, rules_of(text, "anujānāmi bhikkhave"), keys("1.6"), keys("1.7"))
  assert not rules_share_a_word(text, rules_of(text), keys("1.1"), keys("1.5"))


##
# sections
##

def chapter_text():
  return make_text(
    ("0.1", "<article id='x'><header><ul><li class='collection'>{}</li>", "Collection"),
    ("0.2", "<li class='division'>{}</li></ul>", "Division"),
    ("0.3", "<h1 class='sutta-title'>{}</h1></header>", "The chapter"),
    ("0.4", H2, "1. First"),
    ("1.1.1", P, "One."),
    ("1.2.0", H3, "Sub"),
    ("1.2.1", P, "Two."),
    ("2.1.0", H2, "2. Second"),
    ("2.1.1", P, "Three."),
    ("2.1.2", "<p class='endsutta'>{}</p>", "The chapter is finished."),
    ("2.1.3", "<section class='uddana'><p class='uddana-intro'>{}</p></section>", "This is the summary:"),
    ("2.1.4", "<p class='endsutta'>{}</p></article>", "The chapter is finished."),
  )


def test_chapter_bounds():
  text = chapter_text()
  assert chapter_bounds(text.html, text.keys) == (3, 9)


def test_chapter_bounds_without_an_ending():
  text = chapter_text()
  assert chapter_bounds(text.html, text.keys[:9]) == (3, 9)


def test_parse_sections_nests_the_headings():
  text = chapter_text()
  root = parse_sections(text.html, text.keys[3:9])
  first, second = root.items
  assert (first.level, first.key) == (2, f"{text.keys[3]}")
  assert first.items[0] == keys("1.1.1")
  sub = first.items[1]
  assert (sub.level, sub.key, sub.items) == (3, keys("1.2.0")[0], [keys("1.2.1")])
  assert (second.level, second.items) == (2, [keys("2.1.1")])


def test_parse_sections_keeps_text_before_the_first_heading():
  text = make_text(("1.1", P), ("1.2", P), ("1.3.0", H2), ("1.3.1", P))
  root = parse_sections(text.html, text.keys)
  assert root.items[0] == keys("1.1", "1.2")
  assert root.items[1].key == keys("1.3.0")[0]


def test_parse_sections_leaves_labels_in_the_text():
  text = make_text(("1.0", H3), ("1.1", "<h5 class='inserted-heading help-heading'>{}</h5>"), ("1.2", P))
  root = parse_sections(text.html, text.keys)
  assert root.items[0].items == [keys("1.1", "1.2")]


def test_a_heading_which_opens_a_section_ends_where_that_closes():
  text = make_text(
    ("1.0", H2),
    ("1.1", P),
    ("1.2.0", "<section class='padabhajaniya'><h3 class='inserted-heading'>{}</h3>"),
    ("1.2.1", "<dl><dt>{}</dt>"),
    ("1.2.2", "<dd>{}</dd></dl></section>"),
    ("1.3", P),
  )
  root = parse_sections(text.html, text.keys)
  heading = root.items[0]
  assert heading.items[0] == keys("1.1")
  assert heading.items[1].wraps
  assert heading.items[1].items == [keys("1.2.1", "1.2.2")]
  assert heading.items[2] == keys("1.3")


def test_sections_opened_in_the_text_dont_end_a_heading():
  text = make_text(
    ("1.0", H2),
    ("1.1.0", H3),
    ("1.1.1", "<section class='kamma'><p>{}"),
    ("1.1.2", "{}</p></section>"),
    ("1.1.3", P),
  )
  root = parse_sections(text.html, text.keys)
  assert root.items[0].items[0].items == [keys("1.1.1", "1.1.2", "1.1.3")]


def test_last_section():
  inner = Section(3, "b", items=[["x"]])
  outer = Section(2, "a", items=[["w"], inner])
  root = Section(1, None, items=[outer])
  assert last_section(root) is inner
  inner.items.append(Section(4, "c"))
  assert last_section(root).key == "c"
  assert last_section(Section(1, None, items=[outer, ["z"]])).key is None


##
# atoms
##

def atom_keys(text, **kwargs):
  return [atom.keys for atom in atomize(text, text.keys, **kwargs)]


def test_atomize_splits_where_the_paragraph_number_changes():
  text = make_text(
    ("27.1.1", "<p>{}"), ("27.1.2", "{}</p>"), ("27.1.3", RULE),
    ("27.2.1", P), ("27.2.3", RULE), ("27.2.5", P), ("27.2.8", RULE),
    ("27.3.1", P),
  )
  atoms = atomize(text, text.keys)
  assert [atom.keys for atom in atoms] == [
    keys("27.1.1", "27.1.2", "27.1.3"),
    keys("27.2.1", "27.2.3", "27.2.5", "27.2.8"),
    keys("27.3.1"),
  ]
  assert [atom.has_rule for atom in atoms] == [True, True, False]
  assert [atom.number for atom in atoms] == ["27", "27", "27"]
  assert not any(atom.hard or atom.story or atom.counted or atom.ruled_off for atom in atoms)


def test_atomize_reads_four_part_ids_as_the_same_paragraph():
  text = make_text(("16.1.10", P), ("16.1.11.1", P), ("16.1.11.2", RULE), ("16.2.1", P))
  assert atom_keys(text) == [keys("16.1.10", "16.1.11.1", "16.1.11.2"), keys("16.2.1")]


def test_atomize_reads_two_part_ids_by_their_first_number():
  text = make_text(("7.1", P), ("7.2", P), ("8.1", P))
  assert atom_keys(text) == [keys("7.1", "7.2"), keys("8.1")]


def test_atomize_never_splits_inside_a_block():
  text = make_text(
    ("1.1.1", "<p>{}"),
    ("1.2.1", "{}</p>"),
    ("1.3.1", "<ol><li>{}</li>"),
    ("1.4.1", "<li>{}</li></ol>"),
    ("1.5.1", "<section class='kamma'><p>{}</p>"),
    ("1.6.1", "<p>{}</p></section>"),
    ("1.7.1", P),
  )
  assert atom_keys(text) == [
    keys("1.1.1", "1.2.1"), keys("1.3.1", "1.4.1"), keys("1.5.1", "1.6.1"), keys("1.7.1"),
  ]


def test_atomize_notes_horizontal_rules():
  text = make_text(("1.1.1", P, "a"), ("1.1.2", "<hr><p>{}</p>", "b"), ("1.1.3", P, "c"))
  atoms = atomize(text, text.keys)
  assert [atom.keys for atom in atoms] == [keys("1.1.1"), keys("1.1.2", "1.1.3")]
  assert [atom.ruled_off for atom in atoms] == [False, True]


def test_horizontal_rules_between_long_enough_blocks_are_hard():
  text = make_text(
    ("1.1.1", P, "a"), ("1.1.2", P, "b"),
    ("1.1.3", "<hr><p>{}</p>", "c"), ("1.1.4", P, "d"),
    ("1.1.5", "<hr><p>{}</p>", "e"),
  )
  assert [atom.hard for atom in atomize(text, text.keys, short_block=2)] == [False, True, False]
  assert [atom.hard for atom in atomize(text, text.keys, short_block=1)] == [False, True, True]
  assert [atom.hard for atom in atomize(text, text.keys)] == [False, False, False]


def test_untranslated_segments_dont_make_a_block_longer():
  text = make_text(("1.1.1", P, "a"), ("1.1.2", P, ""), ("1.1.3", "<hr><p>{}</p>", "c"), ("1.1.4", P, "d"))
  assert [atom.hard for atom in atomize(text, text.keys, short_block=2)] == [False, False]


def test_the_rules_spacing_out_numbered_paragraphs_arent_divisions():
  text = make_text(("1.1.1", "<p data-counter='1'>{}</p>"), ("1.1.2", "<hr><p data-counter='2'>{}</p>"))
  atoms = atomize(text, text.keys)
  assert len(atoms) == 1
  assert atoms[0].counted


def test_atomize_notes_which_atoms_start_with_a_numbered_paragraph():
  text = make_text(("1.1.1", P), ("1.2.1", "<p data-counter='1'>{}</p>"), ("1.2.2", P))
  assert [atom.counted for atom in atomize(text, text.keys)] == [False, True]


def test_whats_finished_stays_with_what_it_finishes_and_ends_it():
  text = make_text(
    ("1.1.1", P),
    ("1.2.1", "<p class='end'>{}</p>"),
    ("1.2.2", "<p class='end'>{}</p>"),
    ("1.2.3", P),
    ("1.2.4", P),
  )
  atoms = atomize(text, text.keys)
  assert [atom.keys for atom in atoms] == [keys("1.1.1", "1.2.1", "1.2.2"), keys("1.2.3", "1.2.4")]
  assert [atom.hard for atom in atoms] == [False, True]


def test_the_homage_stays_with_what_it_opens():
  text = make_text(("1.0.1", "<p class='namo'>{}</p>"), ("1.1.1", "<section class='suttanta'><p>{}</p></section>"))
  assert atom_keys(text) == [keys("1.0.1", "1.1.1")]


def test_atomize_sets_embedded_stories_apart():
  text = make_text(
    ("1.1.1", P),
    ("1.1.2", "<section class='suttanta'><p>{}</p>"),
    ("1.2.1", "<p>{}</p></section>"),
    ("1.2.2", P),
    ("1.2.3", P),
  )
  atoms = atomize(text, text.keys)
  assert [atom.keys for atom in atoms] == [keys("1.1.1"), keys("1.1.2", "1.2.1"), keys("1.2.2", "1.2.3")]
  assert [atom.story for atom in atoms] == [False, True, False]


def test_other_sections_arent_stories():
  text = make_text(("1.1.1", P), ("1.1.2", "<section class='kamma'><p>{}</p></section>"), ("1.1.3", P))
  assert atom_keys(text) == [text.keys]


def test_atomize_nothing():
  assert atomize(make_text(), []) == []
