from utils.bilara import BilaraText
from utils.html import block_tags, update_open_elements
from utils.pali import open_quotes, opens_new_story, split_words, word_parts
from utils.segments import first_number, paragraph_of, segment_numbers
from utils.text import (
  append_phrase,
  ends_sentence,
  filename_title,
  first_sentence,
  indent_later_paragraphs,
  join_phrases,
  plain_text,
  strip_number_prefix,
)


##
# utils.text
##

def test_plain_text_strips_tags_and_extra_whitespace():
  assert plain_text("47. <i lang='pi' translate='no'>Paṇḍakas</i>  \n") == "47. Paṇḍakas"
  assert plain_text("") == ""


def test_strip_number_prefix():
  assert strip_number_prefix("3. The account") == "The account"
  assert strip_number_prefix("14.1. Abhiññātānaṁpabbajjā") == "Abhiññātānaṁpabbajjā"
  assert strip_number_prefix("17–18. The account of Ambapālī") == "The account of Ambapālī"


def test_strip_number_prefix_leaves_other_numbers_alone():
  assert strip_number_prefix("500 monks") == "500 monks"
  assert strip_number_prefix("The 3. thing") == "The 3. thing"


def test_ends_sentence():
  assert ends_sentence("I allow a storehouse.”")
  assert ends_sentence("Is it true, monks?")
  assert not ends_sentence("The Buddha then said,")


def test_first_sentence():
  assert first_sentence("I allow a storehouse. The storehouse was too small.") == "I allow a storehouse"
  assert first_sentence("“You shouldn’t.” They told him.") == "“You shouldn’t"


def test_first_sentence_keeps_text_whose_first_sentence_is_too_short():
  assert first_sentence("No. That is not allowed.") == "No. That is not allowed."
  assert first_sentence("No. That is not allowed.", min_length=2) == "No"


def test_first_sentence_isnt_fooled_by_decimals():
  assert first_sentence("Within 3.5 centimeters of it") == "Within 3.5 centimeters of it"


def test_first_sentence_of_one_sentence():
  assert first_sentence("Only one sentence.”") == "Only one sentence"
  assert first_sentence("No sentence at all") == "No sentence at all"


def test_append_phrase():
  assert append_phrase("", "Hello") == "Hello"
  assert append_phrase("The Buddha said,", "“Monks”") == "The Buddha said, “Monks”"


def test_append_phrase_adds_no_space_after_a_dash():
  assert append_phrase("legal procedures—", "censure") == "legal procedures—censure"


def test_join_phrases():
  assert join_phrases(["(3)", "one—", "two", "three"]) == "(3) one—two three"
  assert join_phrases([]) == ""


def test_filename_title_makes_text_safe_for_filenames():
  assert filename_title("The account of Mahāpajāpati Gotamī", 100) == "The account of Mahapajapati Gotami"
  assert filename_title("“A nun shouldn’t sit cross-legged.”", 70) == "A nun shouldn't sit cross-legged"
  assert filename_title("<i>Paṇḍakas</i>?", 70) == "Pandakas"
  assert filename_title("Bu Pj 1 (Sexual Intercourse)", 70) == "Bu Pj 1 (Sexual Intercourse)"


def test_filename_title_turns_clause_breaks_into_commas():
  assert filename_title("luxurious skins: lionskins, tiger skins", 70) == "luxurious skins, lionskins, tiger skins"
  assert filename_title("legal procedures—censure", 70) == "legal procedures, censure"
  assert filename_title("Spiritual support, etc.", 70) == "Spiritual support, etc"


def test_filename_title_keeps_decimal_points():
  assert filename_title("within 3.5 centimeters.", 70) == "within 3.5 centimeters"


def test_filename_title_truncates_at_a_word():
  assert filename_title("one two three four five", 13) == "one two three"
  assert filename_title("one two three four five", 12) == "one two"


def test_filename_title_doesnt_end_a_truncated_title_on_a_function_word():
  title = "I allow you to wear sandals in the monastery"
  assert filename_title(title, 34) == "I allow you to wear sandals"
  assert filename_title(title, 100) == title


def test_filename_title_of_nothing():
  assert filename_title("“…”", 70) == "Untitled"


def test_indent_later_paragraphs():
  assert indent_later_paragraphs("one\n\ntwo\n \nthree") == "one\n\n    two\n\n    three"
  assert indent_later_paragraphs("just the one\nparagraph") == "just the one\nparagraph"


##
# utils.html
##

def test_block_tags():
  assert block_tags("<section class='kamma'><p>{}") == [(False, 'section', 'kamma'), (False, 'p', '')]
  assert block_tags("{}</p></section>") == [(True, 'p', ''), (True, 'section', '')]
  assert block_tags("<p class='rule' data-counter='3'>{}") == [(False, 'p', 'rule')]


def test_block_tags_ignores_inline_tags():
  assert block_tags("<span class='verse-line'>{}</span>") == []
  assert block_tags("<blockquote class='gatha'><p><span class='verse-line'>{}</span>") == [
    (False, 'blockquote', 'gatha'), (False, 'p', ''),
  ]


def test_update_open_elements_tracks_nesting():
  still_open, closed = update_open_elements((), "<ol><li>{}")
  assert still_open == (('ol', ''), ('li', ''))
  assert closed == []
  still_open, closed = update_open_elements(still_open, "{}</li><li>{}")
  assert still_open == (('ol', ''), ('li', ''))
  assert closed == []
  still_open, closed = update_open_elements(still_open, "{}</li></ol>")
  assert still_open == ()
  assert closed == [('ol', '')]


def test_update_open_elements_ignores_closing_tags_that_match_nothing():
  assert update_open_elements((), "{}</p></section>") == ((), [])
  assert update_open_elements((('p', ''),), "{}</section>") == ((('p', ''),), [])


def test_update_open_elements_closes_whatever_was_left_open_inside():
  still_open, closed = update_open_elements((('section', 'suttanta'), ('p', '')), "{}</section>")
  assert still_open == ()
  assert closed == [('section', 'suttanta')]


##
# utils.segments
##

def test_segment_numbers():
  assert segment_numbers("pli-tv-kd20:27.2.8") == ['27', '2', '8']


def test_paragraph_of():
  assert paragraph_of("pli-tv-kd20:27.2.8") == ['27', '2']
  assert paragraph_of("pli-tv-kd15:16.1.11.2") == ['16', '1']
  assert paragraph_of("pli-tv-kd16:7.5") == ['7']


def test_first_number():
  assert first_number("pli-tv-kd20:27.2.8") == '27'
  assert first_number("pli-tv-kd16:7.5") == '7'


##
# utils.pali
##

def test_opens_new_story():
  assert opens_new_story("Tena kho pana samayena bhikkhuniyo pallaṅkena nisīdanti")
  assert opens_new_story("“Tena samayena buddho bhagavā sāvatthiyaṁ viharati")
  assert opens_new_story("Atha kho bhagavā rājagahe yathābhirantaṁ viharitvā yena vesālī tena cārikaṁ pakkāmi")


def test_continuations_dont_open_a_new_story():
  assert not opens_new_story("Atha kho bhikkhūnaṁ etadahosi")
  assert not opens_new_story("Evañca pana, bhikkhave, sammannitabbo")
  assert not opens_new_story("Idha pana, bhikkhave, aññatarasmiṁ āvāse")
  assert not opens_new_story("")


def test_open_quotes():
  assert open_quotes(["“Anujānāmi, bhikkhave, sammannituṁ", "yo jāneyya."]) == 1
  assert open_quotes(["“Anujānāmi, bhikkhave, sāditun”ti."]) == 0
  assert open_quotes([]) == 0


def test_open_quotes_starts_counting_again_at_each_new_story():
  assert open_quotes(["“never closed", "Tena kho pana samayena", "“a”ti"]) == 0
  assert open_quotes(["“never closed", "Tena kho pana samayena", "“still open"]) == 1


def test_split_words():
  assert split_words(" Na, bhikkhave,  pallaṅkena ") == ['Na,', 'bhikkhave,', 'pallaṅkena']
  assert split_words("passitvā—nassantete gacchati") == ['passitvā—', 'nassantete', 'gacchati']


def test_word_parts():
  assert word_parts("pallaṅkena") == {'palla', 'allaṅ', 'llaṅk', 'laṅke'}
  assert word_parts("“Lasuṇaṁ, chattan”ti") == {'lasuṇ', 'chatt'}
  assert word_parts("na ca yo vacco") == set()


def test_word_parts_only_starts():
  assert word_parts("pallaṅkena nisīditabbaṁ", only_starts=True) == {'palla', 'nisīd'}


def test_word_parts_find_a_word_inside_a_compound():
  assert word_parts("pallaṅkena", only_starts=True) <= word_parts("aḍḍhapallaṅkan")


##
# utils.bilara
##

def test_bilara_text_from_json_drops_blank_comments_and_variants():
  text = BilaraText.from_json({
    'keys_order': ['a:1.1', 'a:1.2'],
    'html_text': {'a:1.1': '<p>{}', 'a:1.2': '{}</p>'},
    'translation_text': {'a:1.1': 'One. ', 'a:1.2': ''},
    'root_text': {'a:1.1': 'Ekaṁ. ', 'a:1.2': 'Dve. '},
    'comment_text': {'a:1.1': 'A note', 'a:1.2': ' '},
    'variant_text': {'a:1.1': '', 'a:1.2': 'dve → duve'},
  })
  assert text.keys == ['a:1.1', 'a:1.2']
  assert text.comments == {'a:1.1': 'A note'}
  assert text.variants == {'a:1.2': 'dve → duve'}


def test_bilara_text_without_comments_or_variants():
  text = BilaraText.from_json({
    'keys_order': ['a:1.1'], 'html_text': {'a:1.1': '{}'},
    'translation_text': {'a:1.1': 'One'}, 'root_text': {},
  })
  assert text.comments == {}
  assert text.variants == {}
  assert text.en('a:1.1') == 'One'
  assert text.pali('a:1.1') == ''
  assert text.en('a:9.9') == ''


def test_bilara_text_size_counts_translated_segments():
  text = BilaraText(
    keys=['a:1', 'a:2', 'a:3'], html={},
    translation={'a:1': 'One', 'a:2': ' ', 'a:3': 'Three'}, root={},
  )
  assert text.size(text.keys) == 2
  assert text.size(['a:2']) == 0
  assert text.size(k for k in ['a:3', 'a:9']) == 1
