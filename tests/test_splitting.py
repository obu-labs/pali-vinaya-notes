from khandhakas.atoms import atomize
from khandhakas.splitting import (
  Limits,
  group_atoms,
  is_fresh_start,
  is_mid_speech,
  modifies,
  should_split,
  split_units,
)

from tests.helpers import FRESH, P, RULE, keys, make_text, rules_of

COMMON = "anujānāmi bhikkhave bhikkhuniyā"
# Don't fold anything away for being short
NO_FOLDING = Limits(short_ending=0, short_opening=0)


def split(text, limits=Limits(), common_words=COMMON):
  return split_units(text, rules_of(text, common_words), text.keys, limits)


def story(number, pali=FRESH, english="Something happened."):
  return (number, P, english, pali)


def rule(number, pali, english="“A rule.”"):
  return (number, RULE, english, f"“{pali}”ti.")


def test_is_fresh_start():
  text = make_text(("1.1", P, "", ""), ("1.2", P, "At that time", FRESH), ("2.1", P, "Then", "Atha kho bhikkhū"))
  atoms = atomize(text, text.keys)
  assert [is_fresh_start(text, atom) for atom in atoms] == [True, False]


def test_is_mid_speech():
  text = make_text(
    ("1.1", P, "", "“Anujānāmi, bhikkhave, sammannituṁ."),
    ("1.2", P, "", "Evañca pana, bhikkhave, sammannitabbo”ti."),
  )
  assert is_mid_speech(text, keys("1.1"))
  assert not is_mid_speech(text, keys("1.1", "1.2"))


def test_each_rule_gets_a_unit_with_its_origin_story_and_its_amendment():
  # The example from https://github.com/obu-labs/pali-vinaya-notes/issues/7
  text = make_text(
    story("27.1.1", f"{FRESH} bhikkhuniyo kukkuccāyantiyo na sādiyanti."),
    rule("27.1.3", "Anujānāmi, bhikkhave, sāditun"),
    story("27.2.1", f"{FRESH} bhikkhuniyo pallaṅkena nisīdanti."),
    rule("27.2.3", "Na, bhikkhave, bhikkhuniyā pallaṅkena nisīditabbaṁ"),
    story("27.2.5", f"{FRESH} aññatarā bhikkhunī gilānā hoti."),
    rule("27.2.8", "Anujānāmi, bhikkhave, bhikkhuniyā aḍḍhapallaṅkan"),
    story("27.3.1", f"{FRESH} bhikkhuniyo vaccakuṭiyā vaccaṁ karonti."),
    rule("27.3.4", "Na, bhikkhave, bhikkhuniyā vaccakuṭiyā vacco kātabbo"),
  )
  assert split(text) == [
    keys("27.1.1", "27.1.3"),
    keys("27.2.1", "27.2.3", "27.2.5", "27.2.8"),
    keys("27.3.1", "27.3.4"),
  ]


def test_a_procedure_stays_with_its_rule():
  text = make_text(
    story("5.1.1"),
    ("5.1.5", RULE, "“You should appoint a receiver.", "“Anujānāmi, bhikkhave, cīvarapaṭiggāhakaṁ sammannituṁ."),
    story("5.2.1", "Evañca pana, bhikkhave, sammannitabbo.", "And he should be appointed like this."),
    ("5.2.2", "<section class='kamma'><p>{}</p></section>", "‘Please, venerables.’”", "‘Suṇātu me, bhante, saṅgho’”ti."),
    story("6.1.1"),
    rule("6.1.3", "Anujānāmi, bhikkhave, cīvaranidahakaṁ sammannitun"),
  )
  assert split(text) == [keys("5.1.1", "5.1.5", "5.2.1", "5.2.2"), keys("6.1.1", "6.1.3")]


def test_a_line_ending_in_a_dash_introduces_whatever_follows():
  text = make_text(
    story("1.1.1"), story("1.1.2"), story("1.1.3"),
    story("1.1.4", "Atha kho bhagavā bhikkhū āmantesi—", "He addressed the monks:"),
    story("2.1.1", f"{FRESH} bārāṇasiyaṁ", "“At one time in Benares"),
  )
  assert split(text) == [text.keys]


def test_a_new_story_under_a_new_number_ends_text_without_a_rule():
  text = make_text(
    story("4.1.1", "Atha kho mahāpajāpati gotamī"), story("4.1.2", ""), story("4.1.3", ""), story("4.1.4", ""),
    story("5.1.1"),
    rule("5.1.2", "Na, bhikkhave, pātimokkhaṁ uddisitabbaṁ"),
  )
  assert split(text) == [keys("4.1.1", "4.1.2", "4.1.3", "4.1.4"), keys("5.1.1", "5.1.2")]


def test_a_short_opening_goes_with_what_follows():
  text = make_text(
    story("4.1.1", "Atha kho bhagavā yena vesālī tena cārikaṁ pakkāmi."),
    story("5.1.1"),
    rule("5.1.2", "Na, bhikkhave, pātimokkhaṁ uddisitabbaṁ"),
  )
  assert split(text) == [text.keys]
  assert split(text, NO_FOLDING) == [keys("4.1.1"), keys("5.1.1", "5.1.2")]


def test_a_new_story_under_the_same_number_continues_text_without_a_rule():
  text = make_text(
    story("4.1.1"), story("4.1.2", ""), story("4.1.3", ""), story("4.1.4", ""),
    story("4.2.1"),
    rule("4.2.2", "Na, bhikkhave, pātimokkhaṁ uddisitabbaṁ"),
  )
  assert split(text) == [text.keys]


def test_long_text_without_a_rule_is_split_where_a_new_story_starts():
  text = make_text(story("4.1.1"), story("4.1.2", ""), story("4.2.1"), story("4.3.1", "Atha kho"), story("4.4.1"))
  limits = Limits(soft=2, short_ending=0, short_opening=0)
  assert split(text, limits) == [keys("4.1.1", "4.1.2"), keys("4.2.1", "4.3.1"), keys("4.4.1")]


def test_continuations_are_only_split_off_once_the_unit_is_long():
  text = make_text(
    story("1.1.1"), story("1.2.1", "Atha kho"), story("1.3.1", "Atha kho"), story("1.4.1", "Atha kho"),
  )
  assert split(text, NO_FOLDING) == [text.keys]
  limits = Limits(hard=2, short_ending=0, short_opening=0)
  assert split(text, limits) == [keys("1.1.1", "1.2.1"), keys("1.3.1", "1.4.1")]


def test_a_speech_is_allowed_to_run_on_for_twice_as_long():
  text = make_text(
    story("1.1.1", "“Bhūtapubbaṁ, bhikkhave"),
    story("1.2.1", "Atha kho"), story("1.3.1", "Atha kho"), story("1.4.1", "Atha kho"), story("1.5.1", "Atha kho”ti"),
  )
  limits = Limits(hard=2, short_ending=0, short_opening=0)
  assert split(text, limits) == [keys("1.1.1", "1.2.1", "1.3.1", "1.4.1"), keys("1.5.1")]


def test_the_rule_a_long_story_leads_up_to_stays_with_it():
  text = make_text(
    story("1.1.1"), story("1.2.1", "Atha kho"), story("1.3.1", "Atha kho"),
    story("1.4.1", "Atha kho bhagavā dhammiṁ kathaṁ katvā"),
    rule("1.4.2", "Na, bhikkhave, maṁsaṁ paribhuñjitabbaṁ"),
    story("1.5.1", "Atha kho"),
  )
  limits = Limits(hard=2, short_ending=0, short_opening=0)
  assert split(text, limits) == [
    keys("1.1.1", "1.2.1"), keys("1.3.1", "1.4.1", "1.4.2"), keys("1.5.1"),
  ]


def test_a_story_about_being_afraid_of_wrongdoing_amends_the_rule_before_it():
  text = make_text(
    story("34.1.1"),
    rule("34.1.2", "Na, bhikkhave, lasuṇaṁ khāditabbaṁ"),
    story("34.2.1", f"{FRESH} bhikkhū kukkuccāyantā na paribhuñjanti"),
    rule("34.2.2", "Anujānāmi, bhikkhave, ābādhappaccayā"),
  )
  assert split(text) == [text.keys]


def test_a_rule_sharing_a_distinctive_word_amends_the_rule_before_it():
  text = make_text(
    story("34.1.1"),
    rule("34.1.2", "Na, bhikkhave, lasuṇaṁ khāditabbaṁ"),
    story("34.2.1"),
    rule("34.2.2", "Anujānāmi, bhikkhave, ābādhappaccayā lasuṇaṁ khāditun"),
  )
  assert split(text) == [text.keys]
  assert split(text, common_words=f"{COMMON} lasuṇaṁ khāditabbaṁ") == [
    keys("34.1.1", "34.1.2"), keys("34.2.1", "34.2.2"),
  ]


def test_amendments_have_to_be_under_the_same_number_and_fit():
  amended = [story("34.1.1"), rule("34.1.2", "Na, bhikkhave, lasuṇaṁ khāditabbaṁ")]
  elsewhere = make_text(*amended, story("35.1.1"), rule("35.1.2", "Anujānāmi, bhikkhave, lasuṇaṁ khāditun"))
  assert split(elsewhere) == [keys("34.1.1", "34.1.2"), keys("35.1.1", "35.1.2")]
  nearby = make_text(*amended, story("34.2.1"), rule("34.2.2", "Anujānāmi, bhikkhave, lasuṇaṁ khāditun"))
  assert split(nearby, Limits(hard=4)) == [nearby.keys]
  assert split(nearby, Limits(hard=3)) == [keys("34.1.1", "34.1.2"), keys("34.2.1", "34.2.2")]


def test_modifies():
  text = make_text(
    rule("1.1.1", "Na, bhikkhave, chattaṁ dhāretabbaṁ"),
    story("1.2.1", f"{FRESH} bhagavatā chattaṁ paṭikkhittaṁ hoti"), rule("1.2.2", "Anujānāmi, bhikkhave, gilānassa"),
    story("1.3.1"), rule("1.3.2", "Anujānāmi, bhikkhave, gilānassa"),
    story("1.4.1"), rule("1.4.2", "Anujānāmi, bhikkhave, ārāme chattan"),
  )
  rules = rules_of(text, COMMON)
  first, prohibited, unrelated, related = atomize(text, text.keys)
  assert modifies(text, rules, first.keys, prohibited)
  assert not modifies(text, rules, first.keys, unrelated)
  assert modifies(text, rules, first.keys, related)


def test_a_short_ending_without_a_rule_is_kept_with_what_came_before():
  text = make_text(story("1.1.1"), rule("1.1.2", "Na, bhikkhave, lasuṇaṁ khāditabbaṁ"), story("2.1.1"), story("2.1.2"))
  assert split(text) == [text.keys]
  assert split(text, Limits(short_ending=1)) == [keys("1.1.1", "1.1.2"), keys("2.1.1", "2.1.2")]


def test_an_ending_with_a_rule_is_never_folded_away():
  text = make_text(
    story("1.1.1"), rule("1.1.2", "Na, bhikkhave, lasuṇaṁ khāditabbaṁ"),
    story("2.1.1"), rule("2.1.2", "Anujānāmi, bhikkhave, chattan"),
  )
  assert split(text) == [keys("1.1.1", "1.1.2"), keys("2.1.1", "2.1.2")]


def test_an_embedded_sutta_starts_a_new_unit_unless_its_being_introduced():
  sutta = ("1.2.1", "<section class='suttanta'><p>{}</p></section>", "“Monks, there are two extremes.”", "“Dveme, bhikkhave, antā”ti.")
  text = make_text(story("1.1.1"), story("1.1.2", ""), story("1.1.3", ""), story("1.1.4", ""), sutta)
  assert split(text, NO_FOLDING) == [keys("1.1.1", "1.1.2", "1.1.3", "1.1.4"), keys("1.2.1")]
  introduced = make_text(
    story("1.1.1"), story("1.1.2", ""), story("1.1.3", ""), story("1.1.4", "bhikkhū āmantesi—"), sutta,
  )
  assert split(introduced, NO_FOLDING) == [introduced.keys]


def test_whats_after_a_passage_has_finished_starts_a_new_unit():
  text = make_text(
    story("1.1.1"),
    ("1.1.2", "<p class='end'>{}</p>", "The first wonder is finished.", "Paṭhamaṁ pāṭihāriyaṁ."),
    story("1.2.1", "Atha kho"),
  )
  assert split(text) == [keys("1.1.1", "1.1.2"), keys("1.2.1")]


def test_numbered_paragraphs_are_kept_together_however_long():
  text = make_text(*(
    (f"{i}.1.1", f"<p data-counter='{i}'>{{}}</p>", "A monk who has five qualities.", "Pañcahi, bhikkhave, aṅgehi")
    for i in range(1, 7)
  ))
  assert split(text, Limits(soft=1, hard=2, short_ending=0, short_opening=0)) == [text.keys]


def test_should_split_on_a_hard_atom_regardless():
  text = make_text(story("1.1.1", "bhikkhū āmantesi—"), story("1.1.2", "Atha kho"))
  first, second = atomize(text, keys("1.1.1")) + atomize(text, keys("1.1.2"))
  rules = rules_of(text)
  assert not should_split(text, rules, [first], second)
  second.hard = True
  assert should_split(text, rules, [first], second)


def test_group_atoms_of_nothing():
  text = make_text()
  assert group_atoms(text, rules_of(text), []) == []
  assert split(text) == []
