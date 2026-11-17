from khandhakas.rendering import (
  RenderOptions,
  lists_that_skip_numbers,
  render_heading,
  render_segments,
)

from tests.helpers import H2, P, RULE, keys, make_text


def render(*rows, options=RenderOptions()):
  text = make_text(*rows)
  return render_segments(text, text.keys, options)


def markdown(*rows, options=RenderOptions()):
  return render(*rows, options=options)[0]


def test_plain_text_is_just_the_translation_in_its_paragraphs():
  assert markdown(
    ("1.1", "<p>{}", "They told ", "Bhagavato"),
    ("1.2", "{}</p>", "the Buddha. ", "ārocesuṁ."),
    ("1.3", P, "“Is it true?”", "“Saccaṁ kira”ti?"),
  ) == "They told the Buddha.\n\n“Is it true?”"


def test_a_rule_gets_its_pali_in_a_blockquote_and_its_english_in_bold():
  # The example from https://github.com/obu-labs/pali-vinaya-notes/issues/7
  assert markdown(
    ("27.2.7", P, "They told the Buddha.", "Bhagavato etamatthaṁ ārocesuṁ."),
    ("27.2.8", RULE, "“I allow a nun to sit half-cross-legged.”", "“Anujānāmi, bhikkhave, bhikkhuniyā aḍḍhapallaṅkan”ti."),
  ) == "\n\n".join([
    "They told the Buddha.",
    "> “Anujānāmi, bhikkhave, bhikkhuniyā aḍḍhapallaṅkan”ti.",
    "**“I allow a nun to sit half-cross-legged.”**",
  ])


def test_a_rule_over_several_segments_is_one_blockquote_and_one_bold_paragraph():
  assert markdown(
    ("1.1", "<p class='rule'>{}", "“A nun shouldn’t sit cross-legged. ", "“Na, bhikkhave, bhikkhuniyā pallaṅkena nisīditabbaṁ. "),
    ("1.2", "{}</p>", "If she does, she commits an offense.” ", "Yā nisīdeyya, āpatti dukkaṭassā”ti. "),
    ("1.3", P, "On one occasion.", "Tena kho pana samayena"),
  ) == "\n\n".join([
    "> “Na, bhikkhave, bhikkhuniyā pallaṅkena nisīditabbaṁ.  \n> Yā nisīdeyya, āpatti dukkaṭassā”ti.",
    "**“A nun shouldn’t sit cross-legged. If she does, she commits an offense.”**",
    "On one occasion.",
  ])


def test_comments_become_footnotes():
  body, footnotes = render(
    ("1.1", P, "She disrobed. ", "Vibbhami.", "For <i lang='pi' translate='no'>vibbhamati</i>, see the appendix."),
    ("1.2", RULE, "“She is no longer a nun.”", "“Abhikkhunī”ti.", "That is, she can’t <b>reordain</b>."),
  )
  assert body == "She disrobed.[^1]\n\n> “Abhikkhunī”ti.\n\n**“She is no longer a nun.”[^2]**"
  assert footnotes == ["For *vibbhamati*, see the appendix.", "That is, she can’t **reordain**."]


def test_comments_are_rendered_by_the_given_function():
  options = RenderOptions(render_comment=str.upper)
  assert render(("1.1", P, "Text.", "", "a note"), options=options)[1] == ["A NOTE"]


def test_variants_are_footnoted_at_the_end_of_the_line_if_we_cant_place_them():
  body, footnotes = render(
    ("1.1", "<p class='rule'>{}", "“I allow", "“Anujānāmi, bhikkhave,", "", "bhikkhave → bhikkhavo (sya-all) "),
    ("1.2", "{}</p>", "you to consent.”", "sāditun”ti.", "A note."),
  )
  assert body == "> “Anujānāmi, bhikkhave,[^1]  \n> sāditun”ti.\n\n**“I allow you to consent.”[^2]**"
  assert footnotes == ["bhikkhave → bhikkhavo (sya-all)", "A note."]


def test_variants_are_footnoted_on_their_word_if_we_can_place_them():
  def locate(words, key):
    assert words == ["“Anujānāmi,", "bhikkhave,", "sāditun”ti."]
    assert key == keys("1.1")[0]
    return {1: ["bhikkhave", "bhikkhavo (sya-all)"], 2: ["sāditun”ti", "sādiyitunti (bj)"]}
  body, footnotes = render(
    ("1.1", RULE, "“I allow it.”", "“Anujānāmi, bhikkhave, sāditun”ti.", "", "whatever"),
    options=RenderOptions(locate_variants=locate),
  )
  assert body == "> “Anujānāmi, bhikkhave,[^1] sāditun”ti.[^2]\n\n**“I allow it.”**"
  assert footnotes == ["bhikkhave → bhikkhavo (sya-all)", "sāditun”ti → sādiyitunti (bj)"]


def test_only_rules_get_their_variants():
  body, footnotes = render(("1.1", P, "Text.", "Pāḷi.", "", "pāḷi → pāli"))
  assert (body, footnotes) == ("Text.", [])


def test_dashes_in_the_pali_are_left_as_they_were():
  assert "passitvā—nassantete" in markdown(("1.1", RULE, "", "“passitvā—nassantete”ti"))
  assert "passitvā— nassantete" in markdown(("1.1", RULE, "", "“passitvā— nassantete”ti"))


def test_a_rule_in_a_list_stays_in_the_list():
  assert markdown(
    ("1.1", "<ol><li class='rule'>{}</li>", "Abstention from killing,", "pāṇātipātā veramaṇī,"),
    ("1.2", "<li class='rule'>{}</li></ol>", "Abstention from stealing.", "adinnādānā veramaṇī."),
  ) == "\n".join([
    "1. > pāṇātipātā veramaṇī,",
    "",
    "   **Abstention from killing,**",
    "2. > adinnādānā veramaṇī.",
    "",
    "   **Abstention from stealing.**",
  ])


def test_an_untranslated_rule_joins_the_blockquote_of_the_rule_before_it():
  assert markdown(
    ("1.1", RULE, "“I allow beds and benches.”", "“Anujānāmi, bhikkhave, mañcan”ti."),
    ("1.2", RULE, "", "“Anujānāmi, bhikkhave, pīṭhan”ti."),
  ) == "> “Anujānāmi, bhikkhave, mañcan”ti.  \n> “Anujānāmi, bhikkhave, pīṭhan”ti.\n\n**“I allow beds and benches.”**"


def test_an_untranslated_rule_after_anything_else_stands_alone():
  assert markdown(
    ("1.1", P, "A monk with eight qualities may be appointed.", ""),
    ("1.2", RULE, "", "“Anujānāmi, bhikkhave, sammannitun”ti."),
  ) == "A monk with eight qualities may be appointed.\n\n> “Anujānāmi, bhikkhave, sammannitun”ti."


def test_margin_numbers_become_labels():
  assert markdown(
    ("1.1", "<p data-counter='5'>{}</p>", "When a monk has five qualities."),
    ("1.2", "<hr><p data-counter='10'>{}</p>", "When he has another five."),
    ("1.3", "<p data-counter='4–15'>{}</p>", "And so on."),
    ("1.4", "<p class='rule' data-counter='16'>{}</p>", "“You shouldn’t.”", "“Na, bhikkhave”ti."),
  ) == "\n\n".join([
    "(5) When a monk has five qualities.",
    "---",
    "(10) When he has another five.",
    "(4–15) And so on.",
    "> “Na, bhikkhave”ti.",
    "**(16) “You shouldn’t.”**",
  ])


def test_the_margin_number_of_a_lists_introduction_is_dropped():
  assert markdown(
    ("1.1", "<p data-counter='1'>{}</p>", "These are the eight principles:"),
    ("1.2", "<ol><li>{}</li>", "The first."),
    ("1.3", "<li data-counter='2'>{}</li></ol>", "The second."),
  ) == "These are the eight principles:\n\n1. The first.\n2. The second."


def test_lists_that_skip_numbers():
  text = make_text(
    ("1.1", "<ol><li>{}</li>"), ("1.2", "<li>{}</li></ol>"),
    ("1.3", P),
    ("1.4", "<ol><li>{}"), ("1.5", "{}</li>"), ("1.6", "<li value='55'>{}</li></ol>"),
    ("1.7", P),
  )
  assert lists_that_skip_numbers(text.html, text.keys) == {3, 4, 5}
  assert lists_that_skip_numbers(text.html, text.keys[:3]) == set()


def test_lists_that_skip_numbers_are_numbered_explicitly():
  assert markdown(
    ("1.1", P, "He shouldn’t:"),
    ("1.2", "<ol><li>{}</li>", "give the full ordination,"),
    ("1.3", "<li>{} ", "give "),
    ("1.4", "{}</li>", "formal support,"),
    ("1.5", "<li value='55'>{}</li>", "stay in the same room,"),
    ("1.6", "<li>{}</li></ol>", "or walk on the same path."),
  ) == "\n\n".join([
    "He shouldn’t:",
    "1\\. give the full ordination,",
    "2\\. give formal support,",
    "55\\. stay in the same room,",
    "56\\. or walk on the same path.",
  ])


def test_ordinary_lists_are_left_to_markdown():
  assert markdown(
    ("1.1", "<ol><li>{}</li>", "One"), ("1.2", "<li>{}</li></ol>", "Two"),
    ("1.3", "<ul><li>{}</li>", "This"), ("1.4", "<li>{}</li></ul>", "That"),
  ) == "1. One\n2. Two\n\n* This\n* That"


def test_verses_keep_their_lines():
  assert markdown(
    ("1.1", "<blockquote class='gatha'><p><span class='verse-line'>{}</span>", "“Gotamī asked for the going forth, "),
    ("1.2", "<span class='verse-line'>{}</span></p>", "The Buddha did not allow it; ", "", "A note."),
    ("1.3", "<p><span class='verse-line'>{}</span></p></blockquote>", "Did the Leader go.” "),
  ) == "> “Gotamī asked for the going forth,  \n> The Buddha did not allow it;[^1]\n>\n> Did the Leader go.”"


def test_announcements_that_something_has_finished_are_in_italics():
  assert markdown(
    ("1.1", "<p class='end'>{}</p>", "The first wonder is finished. "),
    ("1.2", "<p class='endsutta'>{}</p>", "The chapter on nuns is finished."),
    ("1.3", "<p class='end'>{}</p>", ""),
  ) == "*The first wonder is finished.*\n\n*The chapter on nuns is finished.*"


def test_editorial_notes_are_in_italics():
  assert markdown(
    ("1.1", "<p><span class='pe'>{}</span></p>", "The permutation series is to be expanded."),
  ) == "*The permutation series is to be expanded.*"


def test_definition_lists_become_paragraphs():
  assert markdown(
    ("1.1", "<dl><dt>{}</dt>", "Monastic Code: "),
    ("1.2", "<dd>{}</dd></dl>", "this is the beginning."),
  ) == "**Monastic Code:**\n\nthis is the beginning."


def test_a_horizontal_rule_at_the_top_is_dropped():
  assert markdown(("1.1", "<hr><p>{}</p>", "One."), ("1.2", "<hr><p>{}</p>", "Two.")) == "One.\n\n---\n\nTwo."


def test_labels_in_the_text_are_small_headings():
  assert markdown(
    ("1.1", "<h5 class='inserted-heading help-heading'>{}</h5>", "Jātaka"),
    ("1.2", "<section class='jataka'><p>{}</p></section>", "“Once upon a time.”"),
  ) == "##### Jātaka\n\n“Once upon a time.”"


def test_untranslated_segments_leave_no_trace():
  assert markdown(("1.1", "<p>{}", "Text."), ("1.2", "{}</p>", ""), ("1.3", P, "")) == "Text."
  assert render() == ("", [])


def test_render_heading():
  text = make_text(
    ("1.0", H2, "47. <i lang='pi' translate='no'>Paṇḍakas</i> ", "47. Paṇḍakavatthu "),
    ("2.0", H2, "Bathing", ""),
    ("3.0", H2, "", "18. Licchavīvatthu"),
    ("4.0", H2, "", ""),
  )
  one, two, three, four = text.keys
  assert render_heading(text, one) == "## *Paṇḍakas*\n\n*47. Paṇḍakavatthu*\n\n"
  assert render_heading(text, two) == "## Bathing\n\n"
  assert render_heading(text, three) == "## 18. Licchavīvatthu\n\n"
  assert render_heading(text, four) == ""
  assert render_heading(text, None) == ""
