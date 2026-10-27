"""Tests for the editorial tools: impersonal-voice counting,
check_officialese, and check_term_consistency.

These pin the behaviour against a real Estonian R&D report paragraph and
the plain-language rewrite a native speaker produced from it: the
bureaucratic original must flag and the human rewrite must come back
clean. That pair is also what the thresholds in server.py are calibrated
on, so a threshold change that breaks the separation fails here.

Runs without fastText; the WordNet rule in check_term_consistency
degrades to off when the resource is missing (asserted via `degraded`
rather than assumed).

Run via:

    uv run python tests/test_officialese.py
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server

failures: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  PASS {label}")
    else:
        failures.append(f"{label}: {detail}")
        print(f"  FAIL {label} {detail}")


# The bureaucratic original (an EMTA-facing R&D report) and the rewrite a
# native Estonian speaker produced from it.
ORIG_P1 = (
    "Aruandeperioodil koguti, annoteeriti, valideeriti ja avaldati "
    "ettevõttesiseselt teadusandmestik, mis koosneb 27 137 "
    "kinnisvarakuulutuse pildist. Kogu korpus märgendati ühe läbimisega "
    "Claude'i mudeliga sonnet-4-6 pärast metoodika väljatöötamist, mille "
    "käigus võrreldi mitme teenusepakkuja multimodaalseid mudeleid ning "
    "kasutati nende lahknevusi taksonoomia ja viiba täiustamiseks."
)

ORIG_P2 = (
    "Märgendid on mudeli loodud ja inimesed ei kontrollinud neid "
    "ükshaaval, mistõttu mõõdavad kõik täpsusnäitajad kooskõla "
    "annoteerimisprotsessiga, mitte inimeste antud etalonmärgenditega. "
    "Lukustatud hindamisosas lahendasid projektimeeskonna liikmed "
    "pimehindamise korras 179 lahknevust mudeli ennustuse ja märgendi "
    "vahel, mis pärinesid kahe märgendusvaldkonna kõige vaieldavamatest "
    "klastritest; vastusevõtmeid hindajatele ei avaldatud ning hindamist "
    "täiendas eraldi 60 pildi sisuaudit. Selles sihilikult keerulises "
    "valimis oli korpuse märgend 32% juhtudest vale ja veel 25% juhtudest "
    "tegelikult mitmeti tõlgendatav; kogu korpust hõlmava veamäära kohta "
    "väidet ei esitata. Märgendite määratlusi muudeti ning käimas on "
    "uuesti annoteerimine."
)

HUMAN_REWRITE = (
    "Märgendid lõi mudel ise. Inimesed ei kontrollinud neid ükshaaval. "
    "Seetõttu ei näita täpsusnäitajad, kui õiged märgendid tegelikult on, "
    "vaid ainult seda, kui hästi need annoteerimisprotsessiga kokku "
    "lähevad. Selle kontrollimiseks valiti ette kindlaks eraldi valim: "
    "kahe märgendusvaldkonna kõige vaieldavamad rühmad. Selles valimis "
    "lahendasid projektimeeskonna liikmed pimehindamise korras 179 "
    "juhtumit, kus mudeli ennustus ja märgend erinesid. Hindajad ei "
    "näinud õigeid vastuseid ette. Lisaks vaadati eraldi üle 60 pildi "
    "sisu. Sellest teadlikult raskest valimist osutus 32% märgenditest "
    "valeks ja veel 25% tegelikult mitut moodi tõlgendatavaks. Märgendite "
    "määratlusi täpsustati ja andmestikku annoteeritakse praegu uuesti."
)


def _imp(text: str) -> dict:
    Text = server._Text()
    t = Text(text)
    t.tag_layer(["morph_analysis"])
    return server._impersonal_voice(list(t.morph_analysis))


def impersonal_voice_corrections() -> None:
    """The four counting bugs, each pinned by the construction that
    exposed it on real text."""
    print("impersonal voice: counting corrections")

    # (1) `ei` is tagged pos=V form=neg; counting it inflated total_verbs
    # and deflated the ratio.
    r = _imp("Inimesed ei kontrollinud neid.")
    check("`ei` not counted as a verb", r["total_verbs"] == 1,
          f"total_verbs={r['total_verbs']}")

    # (2) `ta` form after a negation is the impersonal present negative.
    r = _imp("Veamäära kohta väidet ei esitata.")
    check("`ei esitata` counted as impersonal", r["passive_count"] == 1,
          str(r))
    # …but a bare da-infinitive is NOT impersonal.
    r = _imp("Meeskond otsustas esitada aruande.")
    check("bare da-infinitive not counted", r["passive_count"] == 0, str(r))

    # (3) `ei avaldatud` gets tagged pos=A, not V, so it was skipped entirely.
    r = _imp("Vastusevõtmeid hindajatele ei avaldatud.")
    check("`ei avaldatud` counted despite pos=A tag",
          r["passive_count"] == 1, str(r))

    # (4) attributive -tud participle is a modifier, not a predicate.
    r = _imp("Lukustatud hindamisosas lahendasid liikmed juhtumeid.")
    check("attributive -tud not counted as impersonal",
          r["passive_count"] == 0, str(r))
    check("attributive -tud reported separately",
          "Lukustatud" in r["attributive_excluded"], str(r))
    # …but with an olema-form in front it IS an impersonal predicate.
    r = _imp("Andmeid on kasutatud mitmel korral.")
    check("`on kasutatud` counted as impersonal", r["passive_count"] == 1,
          str(r))

    # `mitte` negates a noun phrase, not a verb, so it must not trigger.
    r = _imp("Mõõdeti kooskõla, mitte inimeste antud märgenditega.")
    check("`mitte X antud` not counted as impersonal predicate",
          "antud" not in r["examples"], str(r))

    # Core case: the report paragraph is overwhelmingly impersonal.
    r = _imp(ORIG_P1)
    check("bureaucratic paragraph reads as heavily impersonal",
          r["ratio"] >= 0.8, str(r))


def officialese_separation() -> None:
    """The gates must separate the bureaucratic original from the human
    rewrite: that separation IS the calibration."""
    print("check_officialese: original vs human rewrite")

    o1 = server.check_officialese(ORIG_P1)
    o2 = server.check_officialese(ORIG_P2)
    human = server.check_officialese(HUMAN_REWRITE)

    check("original P1 flags issues", len(o1["issues"]) > 0,
          str(o1["summary_estonian"]))
    check("original P2 flags issues", len(o2["issues"]) > 0,
          str(o2["summary_estonian"]))
    check("human rewrite comes back clean", len(human["issues"]) == 0,
          str([i["rule"] for i in human["issues"]]))

    rules1 = {i["rule"] for i in o1["issues"]}
    check("P1 flags impersonal voice", "impersonal-voice" in rules1, str(rules1))
    check("P1 flags nominalisation", "nominalisation" in rules1, str(rules1))
    check("P1 flags a long sentence", "long-sentence" in rules1, str(rules1))

    # Metrics move in the direction the human edit moved them.
    check("nominalisation density drops across the rewrite",
          human["metrics"]["nominalisations_per_100_words"]
          < o1["metrics"]["nominalisations_per_100_words"],
          f"{o1['metrics']['nominalisations_per_100_words']} → "
          f"{human['metrics']['nominalisations_per_100_words']}")
    check("impersonal ratio drops across the rewrite",
          human["metrics"]["impersonal_voice"]["ratio"]
          < o1["metrics"]["impersonal_voice"]["ratio"],
          f"{o1['metrics']['impersonal_voice']['ratio']} → "
          f"{human['metrics']['impersonal_voice']['ratio']}")

    # Every issue carries an Estonian label (no English-only output).
    for label, res in (("P1", o1), ("P2", o2)):
        check(f"{label}: every issue has rule_estonian",
              all(i.get("rule_estonian") for i in res["issues"]),
              str([i.get("rule_estonian") for i in res["issues"]]))
        check(f"{label}: every issue has a suggestion",
              all(i.get("suggestion") for i in res["issues"]))

    # -mine nouns come back with the verb to swap in. A particle verb is
    # written apart (EKI reegel 31): 'välja töötama', not *väljatöötama.
    noms = {n["lemma"]: n.get("verb") for n in o1["metrics"]["nominalisations"]}
    check("nominalisation carries its verb (väljatöötamine → välja töötama)",
          noms.get("väljatöötamine") == "välja töötama", str(noms))

    # The result carries findings only: no echo of the input, no static
    # note, and the verb count once (metrics.verb_count), not twice.
    check("no input echo or static note",
          "text" not in o1 and "note" not in o1, str(sorted(o1)))
    imp = o1["metrics"]["impersonal_voice"]
    check("impersonal_voice drops its duplicate verb count",
          "total_verbs" not in imp, str(sorted(imp)))
    check("impersonal_voice keeps ratio, counts and examples",
          {"passive_count", "ratio", "examples", "attributive_excluded"}
          <= set(imp), str(sorted(imp)))
    check("verb_count carries the impersonal-voice denominator",
          o1["metrics"]["verb_count"] == _imp(ORIG_P1)["total_verbs"],
          str(o1["metrics"]["verb_count"]))

    # Position semantics the tool description states: the two
    # document-wide rules sit at 0, nominalisation at its first -mine noun.
    by_rule = {i["rule"]: i for i in o1["issues"]}
    check("impersonal-voice is document-wide (position 0)",
          by_rule["impersonal-voice"]["position"] == 0,
          str(by_rule["impersonal-voice"]))
    check("nominalisation is positioned at the first -mine noun",
          by_rule["nominalisation"]["position"]
          == o1["metrics"]["nominalisations"][0]["position"] > 0,
          str(by_rule["nominalisation"]))

    # A long-sentence issue states the count against the limit, once, with
    # no static rationale repeated per flagged sentence.
    longs = [i for res in (o1, o2) for i in res["issues"]
             if i["rule"] == "long-sentence"]
    check("long-sentence explanation is the count and the limit",
          longs and all(
              i["explanation"].startswith("Lauses on ")
              and i["explanation"].endswith(
                  f"(piir {server._OFFICIALESE_LONG_SENTENCE_WORDS}).")
              for i in longs),
          str([i["explanation"] for i in longs]))


def officialese_lexicons() -> None:
    print("check_officialese: filler, phrases, poolt-calque, clause stacking")
    probe = (
        "Projekti raames viidi läbi analüüs, mis kujutab endast olulist "
        "etappi. Mudeli poolt loodud märgendid omavad tähtsust. "
        "Analüüs teostati lähtuvalt metoodikast."
    )
    r = server.check_officialese(probe)
    rules = {i["rule"] for i in r["issues"]}
    sugg = {(i.get("word") or i.get("phrase", "")).lower(): i["suggestion"]
            for i in r["issues"]}

    check("flags 'viidi läbi'", "viidi läbi" in sugg, str(sorted(sugg)))
    check("flags 'kujutab endast'", "kujutab endast" in sugg, str(sorted(sugg)))
    check("flags the poolt-calque", "poolt-calque" in rules, str(rules))
    check("flags 'omama'", any(k.startswith("oma") for k in sugg), str(sorted(sugg)))
    check("flags 'teostama'", any(k.startswith("teosta") for k in sugg),
          str(sorted(sugg)))

    # Surface-matched filler: the inflected form is the marker, while the
    # lemma (eesmärk / vahendus) is an ordinary word that must stay quiet.
    r = server.check_officialese(
        "Analüüsi eesmärgil kasutati andmeid. Süsteemi vahendusel saadeti teade."
    )
    words = {(i.get("word") or "").lower() for i in r["issues"]}
    check("flags 'eesmärgil'", "eesmärgil" in words, str(sorted(words)))
    check("flags 'vahendusel'", "vahendusel" in words, str(sorted(words)))
    r = server.check_officialese("Meie eesmärk on selge ja vahendus toimis hästi.")
    check("plain 'eesmärk' / 'vahendus' not flagged",
          not [i for i in r["issues"] if i["rule"] == "officialese-filler"],
          str([i.get("word") for i in r["issues"]]))

    # 'hääletas poolt' is "in favour", not the passive-agent calque.
    r = server.check_officialese("Enamik liikmeid hääletas poolt ja ettepanek kinnitati.")
    check("'hääletas poolt' not flagged as a calque",
          "poolt-calque" not in {i["rule"] for i in r["issues"]},
          str([i["rule"] for i in r["issues"]]))

    # Clause stacking beats raw length as the reason for the flag.
    stacked = (
        "Töötati välja metoodika, mille käigus võrreldi mudeleid, mis "
        "erinesid taksonoomia poolest, kuna varasem lahendus ei sobinud."
    )
    r = server.check_officialese(stacked)
    check("clause stacking flagged",
          "clause-stacking" in {i["rule"] for i in r["issues"]},
          str([i["rule"] for i in r["issues"]]))

    # Plain, short Estonian must stay silent.
    r = server.check_officialese("Eile käisin kinos. Film oli hea ja näitlejad mängisid hästi.")
    check("plain prose flags nothing", len(r["issues"]) == 0,
          str([i["rule"] for i in r["issues"]]))

    # impersonal-voice needs 4+ verbs as well as the ratio: two of three
    # verbs impersonal is over 0.4 but too few verbs to call.
    r = server.check_officialese("Andmed koguti. Tulemus valideeriti. Mina kirjutan.")
    imp = r["metrics"]["impersonal_voice"]
    check("under 4 verbs, a high impersonal ratio raises no issue",
          imp["ratio"] >= server._OFFICIALESE_IMPERSONAL_RATIO
          and r["metrics"]["verb_count"] < 4
          and "impersonal-voice" not in {i["rule"] for i in r["issues"]},
          str((imp["ratio"], r["metrics"]["verb_count"],
               [i["rule"] for i in r["issues"]])))


# 'läbi viima' in the conduct sense: every form, and the nouns. A style
# hint (EKI ühendsõnastik gives it no label; AMSS calls it kantseliit).
LABI_VIIMA_FLAG = [
    "Iga investor viis läbi põhjaliku kontrolli.",
    "Ettevõte viib läbi uuringu.",
    "Nad viisid läbi küsitluse.",
    "Meeskond on läbi viinud kaks katset.",
    "Ta on läbi viinud mitu koolitust.",
    "Projekti raames viidi läbi analüüs.",
    "Uuring tuleb läbi viia enne suve.",
    "Läbi viidud uuring näitas head tulemust.",
    "Kontrolli viiakse läbi kord aastas.",
    "Ettevõte viis uuringu läbi eelmisel aastal.",
    "Viisime küsitluse läbi märtsis.",
    "Arenguvestlust viiakse mõnikord läbi ka mitmes osas.",
    "Meeskond, kes küsitluse läbi viis, kirjutas aruande.",
    "Uuringu läbi viinud meeskond kirjutas aruande.",
    "Küsitlust läbi viies märkasime viga.",
    "Uuringu viib läbi ülikool.",
    "Ülikool viib uuringuid läbi igal aastal.",
    "Kevadel viime läbi konverentsi.",
    "Uuringud viidi läbi küsitluse abil.",
    "Uuring viidi läbi viies riigis.",
    "Hindamine viidi läbi vastavalt juhendile.",
    "Audit viidi läbi.",
    "Firma viis läbi rahuloluküsitluse.",
    "Kirikuõpetaja viib laulatuse läbi.",
    "Me peame läbi viima uue hanke.",
    "Uuringu läbiviimine võttis aega.",
    "Konverentsi edukaks läbiviimiseks palume esinejatel saata teesid.",
    "Koolituse läbiviija oli kogenud.",
    "Uuringu läbi viimine võttis kuu.",
    "Läbiviidav küsitlus on anonüümne.",
]

# Routes, postpositions, the numeral viis, being led through something,
# and the fugue term: all quiet.
LABI_VIIMA_QUIET = [
    "Ta viis lapse läbi metsa koju.",
    "Lapsed viidi läbi metsa koju.",
    "Tee viib läbi küla.",
    "Rada viib läbi metsa järve äärde.",
    "Matkarada viib läbi raba ja kahe metsatuka.",
    "Kraav, mis viib läbi surnuaia, on kinni kasvanud.",
    "Külast viib läbi kitsas metsatee.",
    "Tee, mis viib läbi Monte Grigio küla, on kitsas.",
    "Metsa läbi viis kitsas rada.",
    "Metsa läbi viiv tee on kitsas.",
    "Selle läbi viis ta oma plaani ellu.",
    "Rajatav kergtee viidi metsast läbi.",
    "Vii niit nõelasilmast läbi ja tõmba pingule.",
    "Nõelasilmast läbi viidud niit tõmmati pingule.",
    "Vii nõel siit läbi ja tõmba niit pingule.",
    "Toru viiakse läbi seina.",
    "Kaabel viidi läbi seinast.",
    "Kaablite läbiviimisel seinast tuleb ava tihendada.",
    "Vool viiakse läbi takisti.",
    "Juht viis ettevõtte läbi kriisi.",
    "Koolitaja viis osalejad läbi kogu protsessi.",
    "Juhendaja viis rühma läbi kõigi harjutuste.",
    "Giid viis meid läbi vanalinna.",
    "Ta viis meid läbi raskuste võidule.",
    "Lugu viib läbi ootamatute keerdkäikude õnneliku lõpuni.",
    "Lapsed viidi läbi metsa uuringu käigus koju.",
    "Ta luges teksti läbi viis korda.",
    "Komisjon vaatas läbi viis taotlust.",
    "Etendus oli läbi viis minutit enne keskööd.",
    "Viis läbi aegade kõige kallimat viiulit on erakogudes.",
    "Need on viisid, läbi mille ta oma eesmärgi täide viib.",
    "Kõik oli läbi viimaks.",
    "Ta kukkus eksamil läbi viiendal katsel.",
    "Kui pidu oli läbi, viis isa lapsed koju.",
    "Uuringu tulemused viisid läbimurdeni.",
    "Fuugas toimub teema läbiviimine kõigis häältes.",
]


def _labi_viima(text: str) -> list[dict]:
    return [i for i in server.check_officialese(text)["issues"]
            if i["rule"] in ("officialese-phrase", "officialese-filler")
            and "läbi" in (i.get("phrase") or i.get("word") or "").lower()]


def labi_viima() -> None:
    print("check_officialese: 'läbi viima' in the conduct sense")
    for text in LABI_VIIMA_FLAG:
        found = _labi_viima(text)
        check(f"flags: {text}", len(found) == 1, str(found))
    for text in LABI_VIIMA_QUIET:
        found = _labi_viima(text)
        check(f"quiet: {text}", not found, str(found))

    check("the four surface pairs left the phrase lexicon",
          not any("läbi" in pair for pair in server._OFFICIALESE_PHRASES_ET),
          str(list(server._OFFICIALESE_PHRASES_ET)))

    # The matched surface, its start, and korraldama / tegema in the
    # verb's own form; pidama leads for a meeting-type event. A split
    # phrase keeps the words between, so the suggestion replaces it whole.
    expected = [
        ("Projekti raames viidi läbi analüüs.", "officialese-phrase",
         "viidi läbi", "korraldati / tehti"),
        ("Meeskond on läbi viinud kaks katset.", "officialese-phrase",
         "läbi viinud", "korraldanud / teinud"),
        ("Ettevõte viis uuringu läbi eelmisel aastal.", "officialese-phrase",
         "viis uuringu läbi", "korraldas uuringu / tegi uuringu"),
        ("Kontrolli viiakse läbi kord aastas.", "officialese-phrase",
         "viiakse läbi", "korraldatakse / tehakse"),
        ("Uuring tuleb läbi viia enne suve.", "officialese-phrase",
         "läbi viia", "korraldada / teha"),
        ("Läbi viidud uuring näitas head tulemust.", "officialese-phrase",
         "Läbi viidud", "korraldatud / tehtud"),
        ("Küsitlust läbi viies märkasime viga.", "officialese-phrase",
         "läbi viies", "korraldades / tehes"),
        ("Kevadel viime läbi konverentsi.", "officialese-phrase",
         "viime läbi", "peame / korraldame"),
        ("Arenguvestlust viiakse mõnikord läbi ka mitmes osas.", "officialese-phrase",
         "viiakse mõnikord läbi", "peetakse mõnikord / korraldatakse mõnikord"),
        ("Konverentsi edukaks läbiviimiseks palume esinejatel saata teesid.",
         "officialese-filler", "läbiviimiseks", "korraldamiseks / tegemiseks"),
        ("Koolituse läbiviija oli kogenud.", "officialese-filler",
         "läbiviija", "korraldaja"),
        ("Uuringu läbi viimine võttis kuu.", "officialese-filler",
         "läbi viimine", "korraldamine / tegemine"),
        ("Läbiviidav küsitlus on anonüümne.", "officialese-filler",
         "Läbiviidav", "korraldatav / tehtav"),
        ("Läbiviidud uuringute tulemused on avalikud.", "officialese-filler",
         "Läbiviidud", "korraldatud / tehtud"),
    ]
    for text, rule, surface, suggestion in expected:
        found = _labi_viima(text)
        got = [(i["rule"], i.get("phrase") or i.get("word"), i["position"], i["suggestion"])
               for i in found]
        check(f"{surface} → {suggestion}",
              got == [(rule, surface, text.index(surface), suggestion)], str(got))

    found = _labi_viima("Uuring viidi läbi ja koolituse läbiviija oli kogenud. "
                        "Ettevõte viis läbi küsitluse.")
    check("several hits come back in text order",
          [i["position"] for i in found] == sorted(i["position"] for i in found)
          and len(found) == 3, str(found))
    check("every 'läbi viima' issue is a style hint, not an error",
          all("stiilisoovitus" in i["explanation"] and "mitte viga" in i["explanation"]
              for text, *_ in expected for i in _labi_viima(text)))


# The verb behind a -mine noun (metrics.nominalisations[*].verb and the
# nominalisation suggestion). Particle verbs are written apart (EKI
# reegel 31), noun + verb compounds give their head verb, true compound
# verbs stay joined, and an unknown verb is left out.
MINE_VERBS = [
    ("riskihindamine", "hindama"),
    ("läbivaatamine", "läbi vaatama"),
    ("heakskiitmine", "heaks kiitma"),
    ("ettevalmistamine", "ette valmistama"),
    ("kvaliteedikontrollimine", "kontrollima"),
    ("andmetöötlemine", "töötlema"),
    ("ümberkorraldamine", "ümber korraldama"),
    ("elluviimine", "ellu viima"),
    ("vastuvõtmine", "vastu võtma"),
    ("taaskasutamine", "taaskasutama"),
    ("alahindamine", "alahindama"),
    ("väärkasutamine", "väärkasutama"),
    ("eeltöötlemine", "eeltöötlema"),
    ("kasutuselevõtmine", "kasutusele võtma"),
    ("arvessevõtmine", "arvesse võtma"),
    ("väljatöötamine", "välja töötama"),
    ("allakirjutamine", "alla kirjutama"),
    ("tähelepanemine", "tähele panema"),
    ("kokkuleppimine", "kokku leppima"),
    ("juurdepääsemine", "juurde pääsema"),
    ("projektijuhtimine", "juhtima"),
    ("tööotsimine", "otsima"),
    ("ühisrahastamine", "ühisrahastama"),
    ("kindlakstegemine", "kindlaks tegema"),
    ("isikuandmetöötlemine", "töötlema"),
    ("andmekaitsemõjuhindamine", "hindama"),
    ("ülehindamine", "üle hindama"),
    ("läbiviimine", "korraldama / tegema"),
    ("hindamine", "hindama"),
]


def mine_verbs() -> None:
    print("check_officialese: the verb behind a -mine noun")
    r = server.check_officialese(" ".join(word for word, _verb in MINE_VERBS))
    got = {n["lemma"]: n.get("verb") for n in r["metrics"]["nominalisations"]}
    for word, verb in MINE_VERBS:
        check(f"{word} → {verb}", got.get(word) == verb, str(got.get(word)))

    r = server.check_officialese(
        "Riskihindamine, andmete läbivaatamine ja lepingu heakskiitmine kestsid kuu.")
    sugg = [i["suggestion"] for i in r["issues"] if i["rule"] == "nominalisation"]
    check("the nominalisation suggestion names the real verbs",
          len(sugg) == 1 and all(pair in sugg[0] for pair in (
              "riskihindamine → hindama", "läbivaatamine → läbi vaatama",
              "heakskiitmine → heaks kiitma")), str(sugg))

    # No verb is better than an invented one: the key is left out.
    r = server.check_officialese("Tema blorgimine kestis kaua.")
    noms = r["metrics"]["nominalisations"]
    check("an unknown verb is omitted, not guessed",
          len(noms) == 1 and "verb" not in noms[0], str(noms))

    r = server.check_officialese("Hindamine, hindamine ja veel kord hindamine.")
    sugg = [i["suggestion"] for i in r["issues"] if i["rule"] == "nominalisation"]
    check("the suggestion names each noun once",
          sugg == ["hindamine → hindama"], str(sugg))


# Review round: the physical sense of 'läbi viima' and the other false
# flags found by the adversarial review, one or more per cause.
LABI_VIIMA_REVIEW_QUIET = [
    # läbi + viima form with a route subject, a source or 'kaudu' after.
    "Kaabel tuleb läbi viia seinast.",
    "Juhtmed on läbi viidud seina kaudu.",
    "Kui kaabel on läbi viidud, tihenda ava silikooniga.",
    "Kaablid on läbi viidud põranda alt.",
    "Lapsed tuli läbi viia rahvamassist.",
    "Niit tuleb läbi viia kõigist aasadest.",
    "Tööde käigus tuleb kaablid läbi viia seinast ja lae kaudu.",
    # 'pärast' as a preposition, 'abil' with nothing one conducts.
    "Lapsed viidi läbi metsa pärast lõunat.",
    "Kaabel viidi läbi seina pärast krohvimist.",
    "Rongkäik viidi läbi linna pärast jumalateenistust.",
    "Niit viiakse läbi nõela abil.",
    # A route subject through a camp or festival grounds.
    "Rada viib läbi laagri järve äärde.",
    "Tee viib läbi pioneerilaagri.",
    "Ülekäik viib läbi festivali territooriumi.",
    "Rada viib läbi talgute ala.",
    "Toru viiakse läbi laagri territooriumi.",
    "Kraav, mis viib läbi laagri, on kinni kasvanud.",
    # A genitive + 'läbi' of means before an impersonal viima with a goal.
    "Projekti läbi viidi ellu mitu kogukonna algatust.",
    "Koolituse läbi viidi töötajad kurssi uute nõuetega.",
    "Reformi läbi viidi riik kiiresti turumajandusele üle.",
    "Halva planeerimise läbi viidi projekt ummikusse.",
    "Tema läbi viidi raha välismaale.",
    "Meie läbi viiakse kaup lõpptarbijani.",
    # A time span owns 'läbi'.
    "Terve päev läbi viisime kaste laost autosse.",
    "Kogu nädal läbi viidi kaupa sadamasse.",
    "Päev läbi viis ta lapsi ühest kohast teise.",
    "Kuu aega läbi viidi ehitusmaterjali objektile.",
    "Mitu tundi läbi viisime mööblit uude korterisse.",
    # Threaded objects, and a -mine noun that is only a time adverbial.
    "Niit viiakse läbi ja tõmmatakse pingule.",
    "Nöör viiakse läbi ja seotakse kinni.",
    "Tihvt lüüakse auku ja polt viiakse läbi.",
    "Kaabel viiakse paigaldamisel läbi.",
    "Toru viiakse ehitamise käigus läbi.",
    # läbiviimine of cables and pipes.
    "Kaabli läbiviimisel tuleb kasutada tihendit.",
    "Kanalisatsioonitoru läbiviimiseks puuritakse seina ava.",
    "Toru läbiviimine läbi tulemüüri nõuab tulekindlat mansetti.",
    "Juhtmete läbiviimine katuselt keldrisse oli keeruline.",
    # The fugue term with one music word, or 'fuuga' alone.
    "Fuuga teine läbiviimine algab dominanthelistikus.",
    "Teema läbiviimine bassis kõlab pidulikult.",
    "Läbiviimisel kõlab teema sopranis.",
    # The numeral after a finite verb whose particle 'läbi' is.
    "Kontrollisime läbi viis väga erinevat stsenaariumi.",
    "Sõelast tuli läbi viies ja kuues katsetaja.",
    "Kvalifikatsioonis murdis läbi viies, kuues ja seitsmes paat.",
    # A nominative event subject going along a named route.
    "Ekspeditsioon viis läbi Siberi.",
    "Retk viis läbi Lõuna-Eesti metsade.",
]

# The conduct sense next to each new guard still flags.
LABI_VIIMA_REVIEW_FLAG = [
    "Koolitus tuleb läbi viia ülikooli kaudu.",
    "Kui see on läbi viidud, saadame tulemused.",
    "Küsitlus tuleb läbi viia kõigist osakondadest.",
    "Kui see on läbi viidud üle kogu riigi, teatame.",
    "Tee remont tuleb läbi viia suvel.",
    "Kaabli vahetus tuleb läbi viia kiiresti.",
    "Mõõtmised viidi läbi seadme abil.",
    "Küsitlus viidi läbi koosoleku pärast.",
    "See viidi läbi küsitluse abil.",
    "Raudteel viidi läbi kontroll.",
    "Tee ääres viidi läbi talgud.",
    "Ülikool viib läbi laagri.",
    "Eesti Raudtee viib läbi küsitluse.",
    "Ettevõte viis läbi küsitluse Tartu koolides.",
    "Tee ehitus viiakse läbi laagri ajal.",
    "Kui analüüsi läbi viidi, ilmnes viga.",
    "Kui projekti läbi viisime, märkasime viga.",
    "Tema läbi viidi uuring.",
    "Kaks nädalat läbi viidud küsitlus näitas kasvu.",
    "Kontroll viiakse paigaldamisel läbi.",
    "Uuring viidi ehitamise käigus läbi.",
    "Toru paigaldamisel viiakse läbi survekatse.",
    "Tee ehitamise käigus viidi läbi remont.",
    "Raudtee ohutuse uuringu läbiviimine võttis aega.",
    "Kaablitööde läbiviimisel tuleb olla ettevaatlik.",
    "Küsitluse läbiviimine läbi veebi oli lihtne.",
    "Teema läbiviimine nõudis palju aega.",
    "Küsitlust läbi viies ja tulemusi analüüsides märkasime viga.",
    "Uuringu viib läbi Tartu Ülikool.",
    "Uuring viidi läbi Tartu Ülikoolis.",
    "Uuringud viis läbi Tartu Ülikool.",
    "Talgud viidi läbi päev läbi.",
]


def labi_viima_review_false_flags() -> None:
    print("check_officialese: 'läbi viima' review round, false flags")
    for text in LABI_VIIMA_REVIEW_QUIET:
        found = _labi_viima(text)
        check(f"quiet: {text}", not found, str(found))
    for text in LABI_VIIMA_REVIEW_FLAG:
        found = _labi_viima(text)
        check(f"flags once: {text}", len(found) == 1, str(found))


def labi_viima_review_suggestions() -> None:
    print("check_officialese: 'läbi viima' review round, suggestions")
    # A duration does not select pidama; a meeting still does. A split
    # phrase keeps the words between, so it can replace the phrase whole.
    expected = [
        ("Kaks tundi läbi viidud küsitlus näitas kasvu.", "läbi viidud",
         "korraldatud / tehtud"),
        ("Mitu tundi läbi viidud koosolek väsitas kõiki.", "läbi viidud",
         "peetud / korraldatud"),
        ("Ülikool viis eelmisel aastal küsitluse läbi.",
         "viis eelmisel aastal küsitluse läbi",
         "korraldas eelmisel aastal küsitluse / tegi eelmisel aastal küsitluse"),
        ("Me viisime uuringu läbi kiiresti.", "viisime uuringu läbi",
         "korraldasime uuringu / tegime uuringu"),
        ("Talgud viidi läbi päev läbi.", "viidi läbi", "korraldati / tehti"),
    ]
    for text, surface, suggestion in expected:
        got = [(i.get("phrase"), i["position"], i["suggestion"]) for i in _labi_viima(text)]
        check(f"{surface} → {suggestion}",
              got == [(surface, text.index(surface), suggestion)], str(got))


def labi_viima_review_linear_time() -> None:
    """The new guards (route subject, time span, goal after an impersonal
    verb, the genitive-shift lookups for -mine verbs) add a bounded amount
    of work per word."""
    print("check_officialese: review-round guards stay linear")
    heads = ["risk", "fail", "projekt", "parool", "server", "kood", "veeb", "tekst",
             "pilv", "arv", "kaabel", "toru", "juhe", "niit", "rada", "trass", "plaan",
             "turg", "mets", "linn"]

    def word(n: int) -> str:
        return "".join(heads[(n * 7919 // 20 ** k) % 20] for k in range(3))

    texts = {
        "case 3 guards": ("Terve päev läbi viisime kaste autosse, kaabel on läbi viidud "
                          "seina kaudu ja projekti läbi viidi ellu mitu algatust. "
                          "Rada viib läbi laagri järve äärde. " * 800)[:100_000],
        "new -mine compounds": "".join(
            f"Kaabel tuleb läbi viia seinast ja {word(n)}ihaldamine ning "
            f"{word(n + 3)}emigreerimine kestis. " for n in range(3000))[:100_000],
    }
    for label, text in texts.items():
        start = time.perf_counter()
        t = server._Text()(text)
        t.tag_layer(["sentences", "morph_analysis"])
        tagging = time.perf_counter() - start
        start = time.perf_counter()
        r = server.check_officialese(text)
        elapsed = time.perf_counter() - start
        check(f"{label}: {elapsed:.1f} s against {tagging:.1f} s of tagging",
              elapsed < 2.5 * tagging + 2 and r["metrics"]["word_count"], f"{elapsed:.1f} s")


# Review round for the verb behind a -mine noun: a genitive cut one
# letter late, a noun form taken for a verb, more particle verbs, and the
# boundary cases that must not move.
MINE_VERBS_REVIEW = [
    ("riskihaldamine", "haldama"),
    ("pilvemigreerimine", "migreerima"),
    ("andmekaitseriskihaldamine", "haldama"),
    ("tulemusavaldamine", "avaldama"),
    ("massemigreerimine", "emigreerima"),
    ("sisuloomine", "looma"),
    ("väärtusloomine", "looma"),
    ("taasloomine", "taaslooma"),
    ("tagaajamine", "taga ajama"),
    ("altvedamine", "alt vedama"),
    ("täideviimine", "täide viima"),
    ("silmaspidamine", "silmas pidama"),
    ("kohalolemine", "kohal olema"),
    ("koosviibimine", "koos viibima"),
    ("kooskõlastamine", "kooskõlastama"),
]


def mine_verbs_review_verbs() -> None:
    print("check_officialese: -mine verbs, review round")
    r = server.check_officialese(" ".join(word for word, _verb in MINE_VERBS_REVIEW))
    got = {n["lemma"]: n.get("verb") for n in r["metrics"]["nominalisations"]}
    for word, verb in MINE_VERBS_REVIEW:
        check(f"{word} → {verb}", got.get(word) == verb, str(got.get(word)))


def mine_verbs_review_not_counted() -> None:
    print("check_officialese: -mine nouns that are not nominalisations")
    # 'vaikimisi' (by default) is an adverb, not a plural partitive.
    r = server.check_officialese(
        "Vaikimisi on logid välja lülitatud. Kui soovid neid näha, muuda seadet. "
        "Vaikimisi salvestab rakendus failid kausta Dokumendid. Teemat saad muuta "
        "menüüst, vaikimisi on see hele.")
    check("vaikimisi is not a nominalisation",
          not r["metrics"]["nominalisations"]
          and not [i for i in r["issues"] if i["rule"] == "nominalisation"],
          str(r["metrics"]["nominalisations"]))
    r = server.check_officialese(
        "Auditi käigus tuvastati mitmeid rikkumisi, korraldati kohtumisi ja peeti "
        "läbirääkimisi.")
    words = [n["word"] for n in r["metrics"]["nominalisations"]]
    check("real -misi plural partitives still count",
          words == ["rikkumisi", "läbirääkimisi"], str(words))

    # Lexicalised things: an offer, knowledge, a meeting.
    for text in ("Hinnapakkumine kehtib kaks nädalat. Saadame pakkumise teile homme. "
                 "Kui pakkumine sobib, allkirjastage see ja saatke tagasi.",
                 "Tal on head teadmised ja oskused. Ta jagab oma teadmisi hea meelega. "
                 "Kohtumised on meil igal esmaspäeval.",
                 "Ettevõtmine õnnestus ja tööpakkumine ning eelteadmised aitasid. "
                 "Tippkohtumine toimus."):
        r = server.check_officialese(text)
        check(f"lexicalised nouns are not counted: {text[:30]}",
              not r["metrics"]["nominalisations"]
              and not [i for i in r["issues"] if i["rule"] == "nominalisation"],
              str(r["metrics"]["nominalisations"]))
    r = server.check_officialese("Pakkumise esitamine toimub kuni reedeni.")
    noms = [(n["lemma"], n.get("verb")) for n in r["metrics"]["nominalisations"]]
    check("an action noun beside them still counts",
          noms == [("esitamine", "esitama")], str(noms))

    # The split spelling 'läbi viimine' takes läbiviimine's verb, unless
    # 'läbi' is a postposition.
    text = "Uuringu läbi viimine võttis kuu."
    noms = server.check_officialese(text)["metrics"]["nominalisations"]
    check("läbi viimine → korraldama / tegema",
          noms == [{"word": "läbi viimine", "lemma": "läbiviimine",
                    "position": text.index("läbi"), "verb": "korraldama / tegema"}],
          str(noms))
    noms = server.check_officialese("Metsa läbi viimine oli raske.")["metrics"]["nominalisations"]
    check("metsa läbi viimine keeps viima",
          [(n["word"], n.get("verb")) for n in noms] == [("viimine", "viima")], str(noms))


# 'Küsin täpsemalt, kas …' at the start of a sentence in a letter. Bare
# 'Küsin, kas', other persons and moods, and plans stay quiet.
KUSIN_FLAG = [
    "Küsin täpsemalt, kui palju pakett kuus maksab, millised on tingimused "
    "ja kui pikk on lepingu tähtaeg.",
    "Küsin täpsemalt, kas lepingut saab ennetähtaegselt lõpetada.",
    "Ma küsin täpsemalt, millal teenus kasutusele tuleb.",
    "Küsime täpsemalt, millised dokumendid tuleb taotlusele lisada.",
    "Küsin täpsemalt: kas hind sisaldab paigaldust?",
    "Küsin teilt täpsemalt, kuidas tagastamine käib.",
    "Tere, küsin täpsemalt, kui palju pakett maksab.",
    "Küsin täpsemalt, et kas pakett sisaldab ka reisitõrkekindlustust?",
    "Me küsime täpsemalt, kus koolitus toimub.",
    "Küsin täpsemalt, kui kaua taotluse menetlemine aega võtab.",
]

KUSIN_QUIET = [
    "Küsisin temalt täpsemalt, mis juhtus.",
    "Ta küsis täpsemalt, kas hind sisaldab käibemaksu.",
    "Küsisime täpsemalt, millal tööd algavad.",
    "Küsin täpsemalt järgmisel kohtumisel.",
    "Küsin täpsemalt üle ja annan teada.",
    "Homme küsin täpsemalt, milliseid pilte on vaja.",
    "Küsin täpsemalt, kas saal on vaba, ja annan teada.",
    "Küsin raamatupidajalt täpsemalt, millal arve tasuti.",
    "Küsin täpsemalt, kui vaja.",
    "Lähen homme arsti juurde ja küsin täpsemalt, mis ravi sobib.",
    "Ma ei küsi täpsemalt.",
    "Küsi täpsemalt, mis sind huvitab.",
    "Küsige täpsemalt, mida te silmas peate.",
    "Võite küsida täpsemalt, millist toodet soovite.",
    "Küsiksin täpsemalt, kas see on võimalik.",
    "Kui küsin täpsemalt, mis juhtus, ta ei vasta.",
    "Küsin täpsemat infot hinna kohta.",
    "Küsin täpsemalt hinna kohta.",
    "Küsin täpsemalt, et asjast paremini aru saada.",
    "Küsin siis täpsemalt, kuidas see toimib.",
    "Küsin, kas teil on vabu aegu.",
    "Uudishimust küsin, kui vana te olete.",
    "Kas teil on ka perepakett? Küsin täpsemalt, kui palju see maksab.",
    "„Küsin täpsemalt, kas sa olid seal?“ ütles uurija.",
    "Sooviksin täpsemalt teada, kui palju kindlustus maksab.",
]


def _kusin(text: str) -> list[dict]:
    return [i for i in server.check_officialese(text)["issues"]
            if i["rule"] == "kusin-tapsemalt"]


def kusin_tapsemalt() -> None:
    print("check_officialese: 'Küsin täpsemalt, kas …'")
    for text in KUSIN_FLAG:
        found = _kusin(text)
        check(f"flags: {text[:60]}", len(found) == 1, str(found))
    for text in KUSIN_QUIET:
        found = _kusin(text)
        check(f"quiet: {text}", not found, str(found))

    singular = "Palun täpsustage, … / Sooviksin täpsemalt teada, …"
    expected = [
        ("Ma küsin täpsemalt, millal teenus kasutusele tuleb.",
         "Ma küsin täpsemalt", singular),
        ("Tere, küsin täpsemalt, kui palju pakett maksab.",
         "küsin täpsemalt", singular),
        ("Küsin teilt täpsemalt, kuidas tagastamine käib.",
         "Küsin teilt täpsemalt", singular),
        ("Küsime täpsemalt, millised dokumendid tuleb taotlusele lisada.",
         "Küsime täpsemalt", "Palume täpsustada, … / Sooviksime täpsemalt teada, …"),
        ("Küsin sinult täpsemalt, kuidas see käib.",
         "Küsin sinult täpsemalt", "Palun täpsusta, … / Tahaksin täpsemalt teada, …"),
    ]
    for text, phrase, suggestion in expected:
        got = [(i["phrase"], i["position"], i["suggestion"]) for i in _kusin(text)]
        check(f"{phrase} → {suggestion[:20]}",
              got == [(phrase, text.index(phrase), suggestion)], str(got))
    found = _kusin(KUSIN_FLAG[1])
    check("labelled in Estonian, explained as a style hint",
          found and found[0]["rule_estonian"] == "'küsin täpsemalt'-palve"
          and "stiilisoovitus" in found[0]["explanation"], str(found))


# Translated stock phrases of letters. Each anchor is two or more words:
# every word alone is ordinary Estonian.
CALQUE_FLAG = {
    "Hinnas on kõik kulud, sealhulgas, kuid mitte ainult transport ja paigaldus.":
        "sealhulgas, kuid mitte ainult",
    "Toetame mitut valdkonda, näiteks, aga mitte üksnes haridust ja sporti.":
        "näiteks, aga mitte üksnes",
    "Leping hõlmab teenuseid (sealhulgas, kuid mitte ainult hooldust).":
        "sealhulgas, kuid mitte ainult",
    "Antud juhul ei ole lisatasu vaja maksta.": "Antud juhul",
    "Antud hetkel ei saa me tellimust kinnitada.": "Antud hetkel",
    "Kuid antud olukorras soovitame tähtaega pikendada.": "antud olukorras",
    "Uus kava adresseerib klientide probleeme.": "adresseerib",
    "Neid muresid ei ole veel adresseeritud.": "adresseeritud",
    "Palun ärge kõhelge minuga ühendust võtmast.": "ärge kõhelge minuga ühendust võtmast",
    "Kui teil on küsimusi, ärge kõhelge meiega ühendust võtmast.":
        "ärge kõhelge meiega ühendust võtmast",
    "Ära kõhkle küsimast, kui midagi jääb segaseks.": "Ära kõhkle küsimast",
    "Loodan, et see kiri leiab teid hästi.": "leiab teid hästi",
    "Loodan, et kiri leiab Teid heas tervises.": "leiab Teid heas",
    "Loodan, et minu sõnum leiab sind hästi.": "leiab sind hästi",
    "Tänan teid teie kiire vastuse eest.": "Tänan teid teie",
    "Täname Teid Teie kannatlikkuse eest.": "Täname Teid Teie",
    "Tänan sind sinu abi eest.": "Tänan sind sinu",
    "Vaatan edasi meie koostööle.": "Vaatan edasi meie koostööle",
    "Vaatame edasi kohtumisele teiega.": "Vaatame edasi kohtumisele",
    "Vaatan edasi teie vastusele.": "Vaatan edasi teie vastusele",
    "Palun leidke manuses hinnapakkumine.": "Palun leidke manuses",
    "Palun leia manusest kokkuvõte.": "Palun leia manusest",
    "Palun leidke lisatud dokument.": "Palun leidke lisatud",
}
CALQUE_QUIET = [
    "See ei puuduta mitte ainult meid, vaid ka partnereid.",
    "Kutsutud on kõik töötajad, sealhulgas praktikandid, kuid mitte ainult nemad.",
    "Talle antud juhised olid selged.", "Õpetaja antud teemal kirjutasid kõik essee.",
    "Kohtu antud hinnangul oli tegu eksimusega.",
    "Eelnevalt antud olukorras tuleb otsus uuesti teha.",
    "Hetkel ei saa me tellimust kinnitada.", "Tänasel päeval avati uus kontor.",
    "Kiri tuleb adresseerida juhatusele.", "Kellele see küsimus on adresseeritud?",
    "Probleem adresseeriti ministrile.", "Ärge kõhelge, võtke julgelt ühendust.",
    "Ta kõhkles, kas minna või jääda.", "Võtke meiega julgelt ühendust.",
    "Kuller leiab teid hästi üles, kui aadress on õige.",
    "Leidsime teid hästi varjatud nurgast.", "Arst leidis, et tunnete end hästi.",
    "Tänan teid kiire vastuse eest.", "Tänan teid, teie abi oli suur.",
    "Tänan teid ja teie meeskonda.", "Ootame teid teie kodus.",
    "Esialgu puhkan ja siis vaatan edasi, kas minna tööle.",
    "Vaatasin edasi, mis juhtub.", "Ma ei suutnud filmi edasi vaadata.",
    "Ootan huviga teie vastust.", "Hinnapakkumise leiate manusest.",
    "Manuses on hinnapakkumine.", "Lisainfo leiate meie kodulehelt.",
    "Leidke oma taotlusele vastav vorm.", "Mees vabandas meeskonnakaaslaste ees.",
    "Uurimus baseerub küsitlusel.", "Korter on koheselt vaba.",
    "Tellimuse saab esitada rakenduse kaudu.", "Kõndisime läbi metsa.",
]


def _calques(text: str) -> list[dict]:
    return [i for i in server.check_officialese(text)["issues"] if i["rule"] == "calque-phrase"]


def calque_phrase() -> None:
    print("check_officialese: translated stock phrases (calque-phrase)")
    for text, phrase in CALQUE_FLAG.items():
        got = [(i["phrase"], i["position"]) for i in _calques(text)]
        check(f"flags {phrase!r}", got == [(phrase, text.index(phrase))], str(got))
    for text in CALQUE_QUIET:
        got = _calques(text)
        check(f"quiet: {text}", not got, str(got))
    found = _calques("Loodan, et see kiri leiab teid hästi.")
    check("labelled in Estonian with an explanation and a suggestion",
          len(found) == 1 and found[0]["rule_estonian"] == "tõlkelaenuline väljend"
          and found[0]["explanation"] and found[0]["suggestion"], str(found))
    # The filler pair is officialese, not a calque; bare 'hetkel' is fine.
    got = [(i["rule"], i["phrase"]) for i in server.check_officialese(
        "Tänasel hetkel töötab meil kümme inimest. Praegusel hetkel ei ole see võimalik.")["issues"]
        if i["rule"] == "officialese-phrase"]
    check("tänasel / praegusel hetkel → praegu",
          got == [("officialese-phrase", "Tänasel hetkel"), ("officialese-phrase", "Praegusel hetkel")],
          str(got))


# Review round: ordinary Estonian the calque rules flagged. Each line is
# correct and natural, and none is the translated letter phrase.
CALQUE_REVIEW_QUIET = [
    # 'vaatas edasi' is 'kept looking', the allative an ordinary goal.
    "Kapten ei vastanud ja vaatas edasi merele.",
    "Laps vaikis ja vaatas edasi emale otsa.",
    "Ta pööras pilgu kõrvale ega vaadanud edasi kellelegi otsa.",
    "Ma istun pingil ja vaatan edasi merele, kuni päike loojub.",
    "Rahvas vaatas edasi lavale, kus etendus jätkus.",
    "Ta vaatas edasi kellale, nagu ootaks midagi.",
    # leidma in its own sense: make time, the parties involved, a genitive.
    "Palun leidke aega lisatud küsimustikule vastamiseks.",
    "Palun leidke võimalus lisatud dokumendid enne koosolekut läbi lugeda.",
    "Palun leidke kõigile kaasatud osapooltele sobiv kohtumisaeg.",
    "Palun leidke kaasatud ekspertidele sobiv ruum.",
    "Palun leidke manuse avamiseks sobiv programm.",
    "Palun leia manuse jaoks väiksem fail, praegune on liiga suur.",
    "Palun leidke aega manuses oleva kava läbivaatamiseks.",
    # Search instructions: the attachment is where to look.
    "Palun leidke manusest oma nimi ja kontrollige, kas andmed on õiged.",
    "Palun leidke lisas 3 toodud tabelist oma piirkonna kood.",
    "Palun leidke lisas olevalt kaardilt oma maja ja märkige see ristiga.",
    "Palun leia lisatud failist viga, mille tõttu programm kokku jookseb.",
    "Palun leia lisast üles õige vorm ja täida see.",
    "Palun leidke manuses toodud juhendi järgi õige seadistus.",
    "Palun leidke lisas viidatud dokument arhiivist üles.",
    # 'on antud' is the passive perfect of andma; the noun says when.
    "Nõusolek on tühine, kui see on antud olukorras, kus isik ei saanud otsust vabalt teha.",
    "Lubadus oli antud hetkel, mil keegi ei osanud kriisi ette näha.",
    "Korraldus oli antud hetkel, kui laev juba sadamast lahkus.",
    "Kõik volitused on antud juhul, kui juhatus on otsuse heaks kiitnud.",
    "Hinnang oli suuliselt antud olukorras, kus dokumente veel ei olnud.",
    "Kohtu poolt antud olukorras tuli otsus uuesti teha.",
    # The possessive is not the echo in 'thank you for your X'.
    "Tänan teid teie ja teie meeskonna panuse eest.",
    "Täname sind sinu ja su pere toetuse eest.",
    "Tänan teid teie nime all avaldatud artikli eest.",
    "Lubage mul tänada teid teie emakeeles.",
    "Ta tänas sind sinu enda sõnadega.",
    "Kas te tänasite teid teie kodus hooldanud õdesid?",
    "Tänan sind sinu kodus vastuvõtmise eest.",
    "Tänan teid teie eest.",
    # Someone else finds you; the letter noun is in another clause or case.
    "Kuller toob paki ja kirja ning leiab teid hästi, sest maja on tänavalt näha.",
    "Saatsin sulle sõnumi, et takso leiab sind hästi ka ilma täpse aadressita.",
    "Kirjas on kaart, nii et külalised leiavad teid hästi.",
    "Päästjad said teie sõnumi õigel ajal ja leidsid teid tervena.",
    "Kiri on laual ja kuller leiab teid hästi.",
    # adresseerima a mail item (Sõnaveeb sense 1).
    "Valesti adresseeritud saadetise puhul on risk, et see jõuab saatjale tagasi.",
    "Vajaduse korral adresseerib sekretär saadetised ümber, et vältida probleeme.",
    "Õigesti adresseeritud ümbrik vähendab riski, et pakk kaob.",
]

# The calques next to them, so the narrowing cannot spread.
CALQUE_REVIEW_FLAG = {
    "Vaatame edasi teie kommentaaridele.": "Vaatame edasi teie kommentaaridele",
    "Meeskond vaatab edasi koostööle teiega.": "vaatab edasi koostööle",
    "Palun leidke manuses olev hinnapakkumine.": "Palun leidke manuses",
    "Palun leidke lisatud failis hinnapakkumine.": "Palun leidke lisatud",
    "Palun leidke lisatud leping ja allkirjastage see.": "Palun leidke lisatud",
    "Palun leidke kaasa lisatud arve.": "Palun leidke kaasa lisatud",
    "Ettevõte on antud olukorras sunnitud koondama.": "antud olukorras",
    "Mis on antud hetkel olukord?": "antud hetkel",
    "Tegelikult antud hetkel on olukord parem.": "antud hetkel",
    "Tänan teid teie abi ja toetuse eest.": "Tänan teid teie",
    "Tänan teid teie tehtud töö eest.": "Tänan teid teie",
    "Loodan, et kiri ka seekord leiab teid hästi.": "leiab teid hästi",
    "Loodan, et minu eelmine kiri leidis teid heas tervises.": "leidis teid heas",
    "Riske on valesti adresseeritud.": "adresseeritud",
    "Teekaart adresseerib peamisi väljakutseid.": "adresseerib",
    "Programm on suunatud eelkõige, kuid mitte ainult noortele.":
        "eelkõige, kuid mitte ainult",
}


def calque_review_quiet_and_flags() -> None:
    print("check_officialese: calque-phrase review round, false flags")
    for text in CALQUE_REVIEW_QUIET:
        got = _calques(text)
        check(f"quiet: {text}", not got, str(got))
    for text, phrase in CALQUE_REVIEW_FLAG.items():
        got = [(i["phrase"], i["position"]) for i in _calques(text)]
        check(f"still flags {phrase!r}", got == [(phrase, text.index(phrase))], str(got))


def calque_review_suggestions() -> None:
    print("check_officialese: calque-phrase review round, suggestions")
    expected = [
        # 'at any given moment' in a rule: 'praegu' alone would change it.
        ("Igal mängijal võib antud hetkel olla käes kõige rohkem seitse kaarti.",
         "praegu (üldreeglis: korraga)"),
        ("Antud hetkel ei saa me tellimust kinnitada.", "praegu (üldreeglis: korraga)"),
        # The head that matched stays; only the tail goes.
        ("Programm on suunatud eelkõige, kuid mitte ainult noortele.",
         "eelkõige (ilma lisandita 'kuid mitte ainult')"),
        ("Toetust saavad eeskätt, aga mitte üksnes väikeettevõtted.",
         "eeskätt (ilma lisandita 'aga mitte üksnes')"),
        ("Hinnas on kõik kulud, sealhulgas, kuid mitte ainult transport ja paigaldus.",
         "sealhulgas (ilma lisandita 'kuid mitte ainult')"),
        # The -mast verb and the number of 'ära' / 'ärge'.
        ("Ära kõhkle küsimast, kui midagi jääb segaseks.", "Küsi julgelt"),
        ("Ärge kõhelge otsustamast, kui olete kindel.", "Otsustage julgelt"),
        ("Ära kõhkle meile kirjutamast.", "Kirjuta julgelt meile"),
        ("Palun ärge kõhelge minuga ühendust võtmast.", "võtke julgelt minuga ühendust"),
    ]
    for text, suggestion in expected:
        got = [i["suggestion"] for i in _calques(text)]
        check(f"{text[:40]} → {suggestion}", got == [suggestion], str(got))
    found = _calques("Programm on suunatud eelkõige, kuid mitte ainult noortele.")
    check("eelkõige is not explained as a list",
          len(found) == 1 and "sealhulgas" not in found[0]["explanation"]
          and "eelkõige" in found[0]["explanation"], str(found))


def calque_review_phrase_is_slice() -> None:
    """Every phrase is the text at its position, also across a line break
    or a double space, so a client can replace it in place."""
    print("check_officialese: phrase is the text at the position")
    texts = [
        "Tänasel\nhetkel on meil kümme töötajat.",
        "Praegusel  hetkel on liiga vara öelda.",
        "See\nkujutab  endast probleemi.",
        "Tekst on mudeli\npoolt loodud.",
        "Antud\nhetkel ei saa me tellimust kinnitada.",
        "Programm on suunatud eelkõige, kuid\nmitte ainult noortele.",
    ]
    for text in texts:
        issues = [i for i in server.check_officialese(text)["issues"] if "phrase" in i]
        rules = {i["rule"] for i in issues}
        bad = [i for i in issues
               if text[i["position"]:i["position"] + len(i["phrase"])] != i["phrase"]]
        check(f"slice: {text!r}", issues and not bad and rules & {
            "officialese-phrase", "poolt-calque", "calque-phrase"}, str(bad or issues))
    found = _calques("Programm on suunatud eelkõige, kuid\nmitte ainult noortele.")
    check("the suggestion quotes the tail on one line",
          [i["suggestion"] for i in found] == ["eelkõige (ilma lisandita 'kuid mitte ainult')"],
          str(found))


def calque_review_linear_time() -> None:
    """The narrowed scans stay bounded per word: the search-instruction
    look-ahead, the 'eest' look-ahead and the imperative synthesis."""
    print("check_officialese: calque-phrase review round, linear time")
    texts = {
        "Palun leidke manuses, no punctuation": ("Palun leidke manuses oma nimi " * 4000)[:100_000],
        "tänan teid teie, no eest": ("Tänan teid teie kodus ja " * 5000)[:100_000],
        "ära kõhkle, many verbs": ("Ära kõhkle küsimast. Ärge kõhelge helistamast. "
                                   "Ära kõhkle kirjutamast. " * 1500)[:100_000],
        "antud olukorras, kus": ("See on antud olukorras, kus " * 4000)[:100_000],
    }
    server.check_officialese("Palun leidke manuses hinnapakkumine.")
    for label, text in texts.items():
        start = time.perf_counter()
        t = server._Text()(text)
        t.tag_layer(["sentences", "morph_analysis"])
        tagging = time.perf_counter() - start
        start = time.perf_counter()
        server.check_officialese(text)
        elapsed = time.perf_counter() - start
        check(f"{label}: {elapsed:.1f} s against {tagging:.1f} s of tagging",
              elapsed < 2.5 * tagging + 2, f"{elapsed:.1f} s")


# Review round for 'Küsin täpsemalt': speech, narration, a research
# question and reporting back, none of them a request in a letter.
KUSIN_REVIEW_QUIET = [
    chr(0x2013) + " Küsin täpsemalt, kas sa olid seal? " + chr(0x2013) + " ütles uurija.",
    chr(0x2014) + " Küsin täpsemalt, kus te eile õhtul olite.",
    "Uurija istus.\n\n" + chr(0x2013) + " Küsin täpsemalt, kus te eile õhtul olite.",
    "> Küsin täpsemalt, kas pakkumine kehtib ka nädalavahetusel?",
    ">> Küsin täpsemalt, kas pakkumine kehtib ka nädalavahetusel?",
    "Ta noogutas. Küsin täpsemalt, kuhu ta läks, aga ta ainult kehitab õlgu.",
    "Küsin täpsemalt, mis juhtus, aga ta vaikib ja vaatab mööda.",
    "Artikli eesmärk on selgitada, kuidas noored uudiseid tarbivad. "
    "Küsime täpsemalt, kas sotsiaalmeedia on asendanud teleuudised.",
    "Meie uurimisküsimus on laiem. Küsime täpsemalt, kas sotsiaalmeedia on "
    "asendanud teleuudised.",
    "Küsin täpsemalt, kas raamatupidaja on kohal, ja võtan teiega ühendust.",
    "Küsin täpsemalt, kas teie pakkumine sisaldab ka transporti, ja võtan siis "
    "teiega ühendust.",
    "Küsin täpsemalt, kas teie pakkumine sisaldab transporti, ning teavitan teid "
    "tulemusest.",
    "Küsime täpsemalt, kas raamatupidaja on kohal, ja võtame teiega ühendust.",
]

# Letters next to them that stay flagged: a hyphen bullet, an adversative
# clause that is not a reaction, bare võtma, and võtta in the question.
KUSIN_REVIEW_FLAG = [
    "- Küsin täpsemalt, kas lepingut saab ennetähtaegselt lõpetada.",
    "Küsin täpsemalt, kas lepingut saab lõpetada, aga see pole kiire.",
    "Küsin täpsemalt, kas raamatupidaja on kohal, ja võtan dokumendid kaasa.",
    "Küsin täpsemalt, kas teiega saab ühendust võtta ka nädalavahetusel.",
]


def kusin_review_quiet_and_flags() -> None:
    print("check_officialese: 'Küsin täpsemalt' review round")
    for text in KUSIN_REVIEW_QUIET:
        found = _kusin(text)
        check(f"quiet: {text[:70]!r}", not found, str(found))
    for text in KUSIN_REVIEW_FLAG:
        found = _kusin(text)
        check(f"flags: {text[:60]}", len(found) == 1
              and found[0]["phrase"] == "Küsin täpsemalt", str(found))


def officialese_linear_time() -> None:
    """The new scans add a bounded amount of work per word: no rescan of
    the text per match or per sentence. Measured against the tagging
    every call already pays, so a slow machine slows both."""
    print("check_officialese: linear time on 100,000 characters")
    roots = ["maja", "kooli", "aia", "puu", "kivi", "vee", "tee", "linna", "metsa", "auto",
             "raamatu", "laua", "töö", "ilma", "maa", "kala", "lille", "saare", "ase", "osa"]

    def word(n: int) -> str:
        return "".join(roots[(n * 7919 // 20 ** k) % 20] for k in range(4))

    texts = {
        # Thousands of sentences, each with a hit, a new word after
        # 'läbi', a new -mine compound and a 'Küsin täpsemalt'. The
        # per-sentence span filter this replaced was quadratic: 19 s on
        # 3 s of tagging for 3,700 short sentences.
        "many sentences, new words": "".join(
            f"Uuring viidi läbi {word(n)} ja {word(n + 1)}hindamine. "
            f"Küsin täpsemalt, kui palju see maksab. " for n in range(3000))[:100_000],
        # One sentence with no end: the music-term test runs once per
        # sentence, not once per 'läbi'.
        "one endless sentence": ("Uuringu läbiviimisel viidi läbi küsitlus ja "
                                 * 3000)[:100_000],
    }
    server.check_officialese("Uuring viidi läbi.")
    for label, text in texts.items():
        start = time.perf_counter()
        t = server._Text()(text)
        t.tag_layer(["sentences", "morph_analysis"])
        tagging = time.perf_counter() - start
        start = time.perf_counter()
        r = server.check_officialese(text)
        elapsed = time.perf_counter() - start
        check(f"{label}: {elapsed:.1f} s against {tagging:.1f} s of tagging",
              elapsed < 2.5 * tagging + 2 and r["issues"], f"{elapsed:.1f} s")


def term_consistency() -> None:
    print("check_term_consistency")
    doc = (
        "Aruandeperioodil avaldati teadusandmestik. Pildiandmestik koosneb "
        "27137 pildist. Andmestik on ettevõttesisene. Treeningandmestik "
        "valmis mais."
    )
    r = server.check_term_consistency(doc)
    check("degraded is reported as a bool",
          isinstance(r.get("degraded"), bool), str(r.get("degraded")))
    check("no input echo, static note or rules_run",
          not {"text", "note", "rules_run"} & set(r), str(sorted(r)))

    head_groups = [g for g in r["groups"] if g["rule"] == "shared-compound-head"]
    check("the andmestik variants are grouped", len(head_groups) >= 1,
          str(r["groups"]))
    check("a compound-head group names its head", all(g.get("head") for g in head_groups),
          str(head_groups))
    # `head` does not apply to a synset group, and a field that does not
    # apply is omitted (the server instructions promise it).
    synset_doc = "Andmed koguti. Andmestik valideeriti. Andmed ja andmestik on olulised."
    synset_groups = [g for g in server.check_term_consistency(synset_doc)["groups"]
                     if g["rule"] == "shared-wordnet-synset"]
    if server._wordnet_available():
        check("a synset group is found", bool(synset_groups), synset_doc)
    check("a synset group carries no head key", all("head" not in g for g in synset_groups),
          str(synset_groups))
    if head_groups:
        g = head_groups[0]
        lemmas = {v["lemma"] for v in g["variants"]}
        check("group holds all four variants",
              {"andmestik", "teadusandmestik", "pildiandmestik",
               "treeningandmestik"} <= lemmas, str(lemmas))
        check("group has an Estonian rule label",
              g.get("rule_estonian") == "sama põhisõna", str(g.get("rule_estonian")))
        check("group names a dominant term", bool(g.get("dominant")), str(g))

    # Two compounds sharing a head, with no bare head, is deliberately
    # NOT enough: those are usually genuinely different things.
    r = server.check_term_consistency(
        "Tegevusvaldkond on lai. Märgendusvaldkond on kitsam."
    )
    check("two compounds sharing a head alone do not flag",
          not [g for g in r["groups"] if g["rule"] == "shared-compound-head"],
          str(r["groups"]))

    # Consistent prose stays quiet.
    r = server.check_term_consistency(
        "Andmestik valmis mais. Andmestik sisaldab pilte. Andmestik on avalik."
    )
    check("consistent terminology flags nothing", len(r["groups"]) == 0,
          str(r["groups"]))

    # The description states the WordNet cap as a number, so pin the two
    # together: changing the constant without the docstring fails here.
    tools = {t.name: t for t in asyncio.run(server.mcp.list_tools())}
    desc = " ".join(tools["check_term_consistency"].description.split())
    cap = server._TERM_CONSISTENCY_WORDNET_CAP
    check("description states the WordNet cap",
          f"the {cap} most frequent" in desc, desc[:160])


def familiarity_junk_neighbourhood() -> None:
    """A junk neighbourhood is no evidence, in either direction. Captured
    production fastText data."""
    print("familiarity: junk neighbourhood carries no verdict")

    # pildiandmestik: ordinary compound, top neighbour is its own head at
    # 0.71, but 5/8 of the tail is scrape junk. Must NOT flag.
    is_suspect, reasons, q = server._familiarity_verdict(
        False, 0.71, [
            ("andmestik", 0.71), ("andmestiku", 0.59), ("juhtmestik", 0.526),
            ("graafikaKunst", 0.506), ("kunstitarbedMõõdutabelidTellimise", 0.496),
            ("ÜhisgümnaasiumKudumidPolosärgidPüksid", 0.49),
            ("ErakoolKudumidPolosärgidPluusid", 0.48),
            ("kihtFliisidPluusidPüksid", 0.47),
        ], ["pildi", "andmestik"])
    check("pildiandmestik not flagged (real top neighbour vouches)",
          is_suspect is False, str(reasons))
    check("pildiandmestik: junk tail still counted",
          q["scrape_junk"] == 5 and q["signal"] == "usable", str(q))

    # sisuaudit: top neighbour is ITSELF junk. This case used to flag:
    # the junk tail was treated as decisive whenever the top neighbour was
    # junk too. It is not decisive. `lisakäive` and `otsingureklaam`, both
    # ordinary business Estonian, have exactly this shape at exactly this
    # score, and so does the coinage `klõpsusild`. When fastText falls
    # back to n-grams and lands in a hub of scrape tokens it has told us
    # nothing, so nothing is claimed.
    is_suspect, reasons, q = server._familiarity_verdict(
        False, 0.605, [
            ("ÜhisgümnaasiumKudumidPolosärgidPüksid", 0.605),
            ("põhjalTripAdvisori", 0.603), ("terviktekstRedaktsiooni", 0.603),
            ("SOTSIAALMEEDIASMOBIILIRAKENDUS", 0.598),
            ("ErakoolKudumidPolosärgidPluusid", 0.595),
            ("kihtFliisidPluusidPüksid", 0.59),
            ("graafikaKunst", 0.588), ("PortaalUudised", 0.585),
        ], ["sisu", "audit"])
    check("sisuaudit not flagged (top neighbour is junk, no signal)",
          is_suspect is False, str(reasons))
    check("sisuaudit: signal reported as none", q["signal"] == "none", str(q))


impersonal_voice_corrections()
officialese_separation()
officialese_lexicons()
labi_viima()
mine_verbs()
labi_viima_review_false_flags()
labi_viima_review_suggestions()
labi_viima_review_linear_time()
mine_verbs_review_verbs()
mine_verbs_review_not_counted()
kusin_tapsemalt()
calque_phrase()
calque_review_quiet_and_flags()
calque_review_suggestions()
calque_review_phrase_is_slice()
calque_review_linear_time()
kusin_review_quiet_and_flags()
officialese_linear_time()
term_consistency()
familiarity_junk_neighbourhood()

if failures:
    print(f"\n{len(failures)} failure(s):")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("\nall officialese / term-consistency tests passed")
