"""Tests for `check_punctuation`: two-part connectives and `nagu`.

0.8.0 flagged every et, kuna, sest, kuigi, kuid, vaid, nagu, mistõttu,
millepärast and kuhu that no comma, semicolon, colon, dash, opening
bracket or sentence end preceded. These tests pin the two places that
changed, against the EKI rules (EKI teatmik, "Koma": ühendsidendid,
kui- ja nagu-tarind), and pin 0.8.0's answer everywhere else:

1. A TWO-PART CONNECTIVE MAY TAKE ITS COMMA BEFORE THE WHOLE OF IT (Sadas
   vihma, nii et jäime koju; Tulin, selleks et aidata). One of those
   marks, an opening quotation mark, or the sentence start before
   the first part (nii, ilma, olgugi, selleks, sellepärast, seepärast,
   seetõttu, vaevalt, peaasi, ainult, mitte, selle asemel, hoolimata
   sellest, olenemata sellest, vaatamata sellele; nii before nagu) sets
   the connective off, and nothing is flagged. With no comma anywhere,
   ilma et and olgugi et, which EKI never splits, are flagged at the first
   part (`, ilma et`); the others keep 0.8.0's `, et`, as the comma goes
   between the parts when the first part is the main clause's (Tegin nii,
   et kõik said aru).

2. nagu TAKES A COMMA WHEN IT OPENS A CLAUSE WITH A FINITE VERB (Vaatas
   mind, nagu oleksin võõras), none in a verbless comparison (tugev nagu
   karu). nagu is flagged only when a word after it, before the next
   clause punctuation, coordinator or subordinator, has a finite verb
   reading in any of its analyses, so a homograph such as sõnas or tuli
   counts. A comma before a finite verb ends a verbless comparison, as
   one before a coordinator does (Laps, kes jooksis nagu tuul, võitis).

3. et RIGHT AFTER ja, ning, ega OR ehk TAKES NO COMMA: it opens a
   coordinated clause (EKI reegel 45 märkus: ..., et see on õige ja et me
   peaksime jätkama). või counts only after an earlier et in the
   sentence, as it is also a noun (Sulata või et see seguneks).

4. A CLAUSE INSIDE THE MAIN CLAUSE IS CLOSED BY A COMMA TOO (EKI õigekirja
   põhireeglid 2025, reegel 44: Mees, kes seal seisis, oli minu isa). A
   clause opened after a comma by a relative word or a subordinator, in
   a main clause that still owes its verb, is flagged at the second sure
   finite verb (`comma-after-subordinate-clause`, `, oli`), or at the
   main clause's subject right before it when that cannot be the
   clause's own (Hommikul, kui ärkasin päike juba paistis: `, päike`). Not
   a second verb: ei in ei ... ega, ei tea before a question word, a -vad
   participle after olema, on in an English name. A table cell edge (|,
   a tab), an HTML tag, an arrow or a single quotation mark ends the
   clause as other punctuation does. After a kes or
   mis clause with a 3rd person verb, ja or ning before a verb in the
   main verb's person and not the clause's is flagged
   (`comma-before-ja-after-subordinate-clause`, reegel 44 märkus 2:
   Juhtisin projekti, mis kestis kaks aastat, ja koolitasin). Each guard
   the two rules rest on has a correct sentence it keeps quiet.

Every flag's suggestion, applied, must give text the tool accepts (one
tokenizer exception is marked).

Run via:

    uv run python tests/test_punctuation.py
"""
from __future__ import annotations

import re
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


def issues(text: str) -> list[dict]:
    return server.check_punctuation(text)["issues"]


def clean(text: str) -> None:
    got = issues(text)
    check(f"no flag: {text}", got == [], str(got))


def one(text: str, word: str, at: str | None = None, refix: bool = True) -> None:
    """Exactly one issue, on `word`, starting where `at` (default `word`)
    first occurs in the text, suggesting `, word`, and, unless `refix` is
    off, the text with the suggestion applied passes."""
    got = issues(text)
    want_pos = text.index(at if at is not None else word)
    check(f"one flag on {word!r}: {text}",
          len(got) == 1
          and got[0]["word"] == word
          and got[0]["suggestion"] == f", {word}"
          and got[0]["position"] == want_pos
          and got[0]["rule"] == "comma-before-clause-conjunction"
          and got[0]["rule_estonian"] == "koma alistava sidesõna ees"
          and set(got[0]) == {"word", "position", "rule", "rule_estonian", "suggestion"},
          str(got))
    if refix and len(got) == 1:
        pos, length = got[0]["position"], len(got[0]["word"])
        fixed = text[:pos].rstrip() + got[0]["suggestion"] + text[pos + length:]
        again = issues(fixed)
        check(f"  its fix passes: {fixed}", again == [], str(again))


CLOSING = ("comma-after-subordinate-clause", "koma kõrvallause lõpus")
BEFORE_JA = ("comma-before-ja-after-subordinate-clause", "kõrvallause koma ja ees")


def closes(text: str, word: str, rule: tuple[str, str] = CLOSING,
           refix: bool = True) -> None:
    """Exactly one issue of `rule` on the first whole-word `word`,
    suggesting `, word`, and, unless `refix` is off, the text with the
    suggestion applied passes."""
    got = issues(text)
    want_pos = re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text).start()
    check(f"one {rule[0]} on {word!r}: {text!r}",
          len(got) == 1
          and got[0]["word"] == word
          and got[0]["suggestion"] == f", {word}"
          and got[0]["position"] == want_pos
          and (got[0]["rule"], got[0]["rule_estonian"]) == rule
          and set(got[0]) == {"word", "position", "rule", "rule_estonian", "suggestion"},
          str(got))
    if refix and len(got) == 1:
        pos, length = got[0]["position"], len(got[0]["word"])
        fixed = text[:pos].rstrip() + got[0]["suggestion"] + text[pos + length:]
        again = issues(fixed)
        check(f"  its fix passes: {fixed!r}", again == [], str(again))


print("a comma before the whole connective passes")
for text in (
    "Sadas vihma, nii et jäime koju.",
    "Tulin, selleks et aidata.",
    "Ta lahkus, ilma et oleks hüvasti jätnud.",
    "Kõik läks hästi, nii nagu me lootsime.",
    "Lõke ei süttinud, sellepärast et puud olid märjad.",
    "Ta jäi koju, seepärast et oli haige.",
    "Ta jäi koju, seetõttu et oli haige.",
    "Ta tegutses, selle asemel et kurta.",
    "Ta tuli tööle, hoolimata sellest et oli haige.",
    "Me jätkame, olenemata sellest et ilm on halb.",
    "Ta tuli, vaatamata sellele et oli väsinud.",
    "Sõime edasi, olgugi et kõht oli juba täis.",
    "Kõik oli hästi, ainult et raha oli vähe.",
    "Söö, mida tahad, peaasi et kõht saab täis.",
    "Ta jõudis koju, vaevalt et keegi märkas.",
    "Ma tulin, mitte et sind aidata.",
    "Mul on kõik olemas; ainult et raha on vähe.",
    "Ta tuli (selleks et aidata) varem.",
    "Sadas vihma \u2013 nii et jäime koju.",
    # The comma inside the closing quotation mark sets it off too.
    "Ta ütles „jah,“ nii et läksime koju.",
):
    clean(text)

print("a connective that opens a sentence or a quotation needs no comma")
for text in (
    "Olgugi et kõht oli juba täis, sõime edasi.",
    "Ilma et keegi teaks, lahkus ta.",
    "ILMA ET KEEGI TEAKS, LAHKUS TA.",
    "Selle asemel et kurta, tegutse.",
    "Selleks et aidata, tulin varem.",
    "Nii et me jäime koju.",
    "Vaevalt et ta tuleb.",
    "Nii nagu ma ütlesin, nii see läks.",
    "Ta ütles: „Nii et homme ei tule keegi.“",
    'Ta ütles: "Nii et homme ei tule keegi."',
    "«Nii et me jääme koju,» ütles ta.",
    "„Jah.“ Nii et läksime koju.",
    "- Nii et kõik on korras.",
):
    clean(text)

print("ilma et and olgugi et: the comma goes before the first part")
one("Ta lahkus ilma et oleks hüvasti jätnud.", "ilma et")
one("Ma jään siia ilma et keegi teaks.", "ilma et")
one("Sõime edasi olgugi et kõht oli täis.", "olgugi et")
one("Ta lahkus kodust ilma et keegi märkaks.", "ilma et")
one("Ta ostis uue ilma et oleks vana müünud.", "ilma et")
one("TA LAHKUS ILMA ET KEEGI MÄRKAKS.", "ILMA ET")
# A particle before the connective does not split it either.
one("Ta lahkus lihtsalt ilma et oleks hüvasti jätnud.", "ilma et")
one("Ta tuli ikka olgugi et oli haige.", "olgugi et")
# The word is the text as written, so applying the suggestion is exact.
one("Ta lahkus ilma  et keegi märkaks.", "ilma  et")

print("the other connectives with no comma: 0.8.0's `, et`")
# EKI: the manner nii et takes the comma between its parts (Tehke see töö
# ära nii, et keegi ei näe); the tool cannot tell manner from result.
one("Tehke see töö ära nii et keegi ei näe.", "et")
one("Tegin nii et kõik said aru.", "et")
one("Sadas vihma nii et jäime koju.", "et")
one("Tulin selleks et aidata.", "et")
one("Ta jäi koju seetõttu et oli haige.", "et", at="et oli")
one("Ta tegutses selle asemel et kurta.", "et")
one("Ta tuli tööle hoolimata sellest et oli haige.", "et")
one("Ma tahan ainult et sa oleksid õnnelik.", "et")
# peaasi as the predicative, vaevalt as the verb's adverb (EKI: ..., et).
one("Minu jaoks on peaasi et lapsed on terved.", "et")
one("Ta märkas vaevalt et keegi oli tuppa tulnud.", "et")
# A closing quotation mark glued to the word before it sets nothing off.
one("Ta ütles „jah“ nii et läksime koju.", "et")
one('Ta ütles "jah" nii et läksime koju.', "et")
one("Tee nii nagu tahad.", "nagu")

print("an existing comma is never flagged, as in 0.8.0")
for text in (
    "Ta lahkus ilma, et oleks hüvasti jätnud.",
    "Tegin nii, et kõik said aru.",
    "Tulin selleks, et aidata.",
    # ilma here is the noun ilm, and the comma before et is right.
    "Lootsime sooja ilma, et saaks ujuma minna.",
    "Ta rändas aastaid mööda ilma, et leida oma juuri.",
):
    clean(text)

print("a verbless nagu comparison takes no comma")
for text in (
    "Ta on tugev nagu karu.",
    "Ta jooksis nagu tuul.",
    "Ta on valge nagu lumi.",
    "Vaatas mind nagu võõrast.",
    "Ta käitus nagu laps.",
    "Ta on samasugune nagu ema.",
    "Ta on tugev nii nagu karu.",
    "Ta oli rahulik nagu tavaliselt.",
    "Ta käitub nagu kõik teised.",
    # The comparison ends at a coordinator, a subordinator or a comma.
    "Ta jooksis nagu tuul ja hüppas üle aia.",
    "Ta on tugev nagu karu, aga mitte nii tark.",
):
    clean(text)

print("a nagu clause that drops olema still takes the comma (EKI)")
one("Ta tegi nagu kokku lepitud.", "nagu")
one("Arve tasuti nagu kokku lepitud.", "nagu")

print("a nagu after a coordinated subject or before a relative clause is still asked for, as in 0.8.0")
one("Ta tegi kõik nagu ema ja isa olid õpetanud.", "nagu")
one("Tegin nagu ema, kes on kogenud kokk, soovitas.", "nagu")
one("Raskmetallid nagu plii ja elavhõbe on organismile mürgised.", "nagu")

print("a pair after a closing quote")
one("Ta hüüdis „Mine ära!“ nii et kõik kuulsid.", "et")
one("Ostsime puuvilju, köögivilju vms. nii et kõht sai täis.", "et")

print("a nagu clause with a finite verb takes the comma")
one("Kõik läks nagu võis arvata.", "nagu")
one("Tee nagu tahad.", "nagu")
one("„Tee nagu tahad,“ ütles ema.", "nagu")
one("Ta rääkis nagu oleks ta seal olnud.", "nagu")
one("Vaatas mind nagu oleksin võõras.", "nagu")
one("Ta käitus nagu ta ei teadnud midagi.", "nagu")
one("Ta käitus nagu poleks midagi juhtunud.", "nagu")
one("Ta vastas nagu kästi.", "nagu")
one("Tee nii nagu ema palus.", "nagu")
one("Tulemused olid paremad kui eelmisel aastal nagu juhataja märkis.", "nagu")
one("Hinnad tõusid (eriti toidukaupadel) nagu analüütikud olid ennustanud.", "nagu")
# The tokenizer glues a comma to the euro sign (`€,`), so the fixed text
# is flagged again, as in 0.8.0.
one("Pilet maksab 15 € nagu korraldajad teatasid.", "nagu", refix=False)
one("Ta ostis leiba ja piima nagu ema oli palunud.", "nagu")
one("Leping lõpeb nagu TLS § 97 ette näeb.", "nagu")
one("Ta ütles „jah“ nagu oleks see iseenesestmõistetav.", "nagu")
one("Lisa soola nagu retseptis on kirjas.", "nagu")
one("- Lisa munad ükshaaval nagu retseptis on kirjas", "nagu")
one("ok\ntee nagu tahad", "nagu")
one("Eesti majandus nagu analüütikud ennustasid kasvas kaks protsenti.", "nagu")
one("Hind tõusis nagu nii analüütikud kui ka ettevõtjad olid oodanud.", "nagu")

print("a verb that is also a noun counts: every reading is read")
one("Olukord on keeruline nagu peaminister sõnas.", "nagu")
one("Hinnad tõusevad nagu juhatuse esimees lisas.", "nagu")
one("Ta oli süütu nagu hiljem selgus.", "nagu")
one("Raport valmis nagu tellija soovis.", "nagu")
one("Töötus kasvas 7,2 protsendini nagu Eesti Pank prognoosis.", "nagu")
one("HIND LANGES NAGU VÕIS ARVATA.", "NAGU")

print("documented limits")
# The main clause's verb after a verbless comparison (EKI: no comma).
one("Kassid nagu kõik koduloomad vajavad hoolitsust.", "nagu")
# A noun that is also a verb form (tuli = came, jää = stay).
one("Ta oli punane nagu tuli.", "nagu")
# ilma as the noun ilm before an et clause, with no comma: the suggestion
# should be `, et`.
one("Ta ootas ilusat ilma et minna randa.", "ilma et")

print("the single subordinators keep 0.8.0's answer")
one("Ma tean et see on hea.", "et")
one("Ta ei tulnud sest oli haige.", "sest")
one("Ta tuli kuid lahkus kohe.", "kuid")
one("Ma ei käinud mitte Prahas vaid Viinis.", "vaid")
one("Ta jäi koju kuigi ilm oli ilus.", "kuigi")
one("Ta ei tulnud kuna oli haige.", "kuna")
one("Ta oli haige mistõttu ta ei tulnud.", "mistõttu")
one("Ta oli haige millepärast ta ei tulnud.", "millepärast")
one("Ma ei tea kuhu ta läks.", "kuhu")
one("Ta oli nii väsinud et jäi magama.", "et")
one("Mulle on täiesti ükskõik kuhu me sõidame.", "kuhu")
one("Sulata või et see seguneks paremini.", "et")
# Its fix still lacks the comma closing the et clause (EKI reegel 44:
# Tahtsin helistada, aga et oli hilja, kirjutasin kirja).
one("Tahtsin helistada aga et oli hilja kirjutasin kirja.", "et", refix=False)
closes("Tahtsin helistada aga, et oli hilja kirjutasin kirja.", "kirjutasin")
# After a closing quotation mark the comma is still missing.
one("Ta vastas „ei“ sest tal polnud aega.", "sest")
one("Minister nimetas eelnõu „ajalooliseks“ sest see lahendab probleemi.", "sest")
one('Lepingus nimetatakse tellijat "Tellija" kuna see lihtsustab teksti.', "kuna")
one("Firma nimetas uue toote «Vikerkaar» kuigi turundusosakond oli vastu.", "kuigi")
two = issues("Tööandja peab tagama et töötaja saab puhkust nagu töölepingu seaduse § 55 sätestab.")
check("et and nagu in one sentence", [i["word"] for i in two] == ["et", "nagu"], str(two))
for text in (
    "Ma arvan, et kõik on hästi.",
    "Ta ei tulnud, sest oli haige.",
    "Ta küsis: kuhu sa lähed?",
):
    clean(text)

print("et right after a coordinator opens a coordinated clause: no comma (EKI reegel 45 märkus)")
for text in (
    "Ta ütles, et see on õige ja et me peaksime jätkama.",
    "Ta ütles, et see, mida me tegime, on õige ja et me peaksime jätkama.",
    "Ta lubas, et tuleb ning et toob kaasa ka lapsed.",
    "Sadas vihma ja et kõik olid väsinud, jäime koju.",
    # või after an earlier et in the sentence is the coordinator.
    "Ta ütles, et tuleb homme või et helistab.",
):
    clean(text)
# With no et before it, või may be the noun (butter): still flagged.
one("Sulata või et see seguneks paremini.", "et")

print("a verbless nagu comparison closed by a comma before a finite verb takes no comma")
for text in (
    "Laps, kes jooksis nagu tuul, võitis võistluse.",
    "Ta jooksis nagu tuul, jõudis esimesena finišisse.",
    "Mees, kes rääkis nagu professor, ei teadnud tegelikult midagi.",
):
    clean(text)
# A participle after the comma is not a finite verb: still asked for.
one("Tegin nagu ema, kogenud kokk, soovitas.", "nagu")

print("comma-after-subordinate-clause: the comma closing a clause before the main verb")
closes("Mees, kes seal seisis oli minu isa.", "oli")
closes("Raamat, mida ma lugesin on huvitav.", "on")
closes("Inimene, kes ei tea pole süüdi.", "pole")
closes("Raha, mis on kulunud oli suur.", "oli")
closes("Projekt, mida juhtisin kestis kaks aastat.", "kestis")
closes("Meeskond, kellega töötasin koosnes viiest inimesest.", "koosnes")
closes("Ma arvan, et see, mida sa ütlesid on õige.", "on")
closes("Kas see, mida ta rääkis on tõsi?", "on")
closes("Mees, kes seal seisis ei olnud minu isa.", "ei")
closes("Ettevõte, kus ta töötab kasvab kiiresti.", "kasvab")
# soovivad is also the participle sooviv; nothing plural follows it.
closes("Kõik, kes soovivad osaleda peavad registreeruma.", "peavad")
closes("Tööd, mida tegime ja tulemused, mida saime olid head.", "olid")
closes("Õpilane, kes oleks pidanud tulema jäi haigeks.", "jäi")
closes("Mõte, et kõik on korras rahustas teda.", "rahustas")
closes("Küsimus, kas ta tuleb on endiselt lahtine.", "on")
# ja + verb is the clause's second predicate.
closes("Mees, kes seal seisis ja naeratas oli minu isa.", "oli")
closes("Mida see, mida ta ütles tähendab?", "tähendab")
closes("Raha, mis läks ära oli suur.", "oli")
closes("Mõned, kes olid kohal ei olnud nõus.", "ei")
closes("Kõik, mis ta tegi oli hästi tehtud.", "oli")
closes("Ettevõte, kus ta töötab kasvab kiiresti, ja palkab uusi inimesi.", "kasvab")
# ja ei, või ei and the verb after the ei are the clause's second predicate:
# the main verb is flagged, not the conditional after ei.
closes("Laenaja, kes on maksega hilinenud ja ei suudaks võlga tasuda peab pangaga ühendust võtma.",
       "peab")
closes("Kasutaja, kes on sisse loginud ja ei oskaks parooli muuta leiab juhendi abilehelt.", "leiab")
# ei with a verb before ega is the main clause's predicate, not ei ... ega.
closes("Mees, kes seal seisis ei tahtnud ega suutnud midagi teha.", "ei")
closes("Mees, kes seal seisis ei tea midagi.", "ei")
# After olema the -vad participle is the predicative; the sure verb after
# it is the main verb. An adverb after olema can be its predicative itself.
closes("Kandidaadid, kes olid sobivad kutsuti teise vooru.", "kutsuti")
closes("Kandidaadid, kes olid väga sobivad kutsuti teise vooru.", "kutsuti")
closes("Kliendid, kes on rahul soovitavad meid sõpradele.", "soovitavad")
# A capitalised name next to on is not English: on stays olema.
closes("Raamat, mille kirjutas Brennick on klassika.", "on")
closes("Tööriist, mida kasutame on Pixelon.", "on")
# Inside one table cell the clause still needs its closing comma.
closes("| Mees, kes seal seisis oli minu isa |", "oli")

print("the main clause's subject right before its verb takes the comma before it")
closes("Hommikul, kui ärkasin päike juba paistis.", "päike")
closes("Raamatu, mille sa mulle andsid ma lugesin läbi.", "ma")
closes("Pärast seda, kui lõpetasime nad tulid.", "nad")
# Not when the word can be the clause's own: a predicative after olema, a
# word that can be a genitive object (auto), a plural object (kingad), a
# nominative of time before another word (tund aega).
closes("Siis, kui olin laps meeldis mulle jäätis.", "meeldis")
closes("Eile, kui ostsin auto läks kõik hästi.", "läks")
closes("Eile, kui ostsin uued kingad läksin kohe koju.", "läksin")
closes("Eile, kui ootasin tund aega saabus buss lõpuks.", "saabus")

print("comma-before-ja-after-subordinate-clause: the clause's comma stays before ja (reegel 44 märkus 2)")
closes("Juhtisin projekti, mis kestis kaks aastat ja koolitasin uusi töötajaid.", "ja", BEFORE_JA)
closes("Kirjutasin õpetajale, kes oli mind aidanud ja tänasin teda.", "ja", BEFORE_JA)
closes("Töötasin ettevõttes, mis tegeleb müügiga ja juhtisin seal meeskonda.", "ja", BEFORE_JA)
closes("Õppisin ülikoolis, mis asub Tartus ja lõpetasin selle kiitusega.", "ja", BEFORE_JA)
closes("Leidsin vea, mis takistas maksete töötlemist ja parandasin selle kiiresti.", "ja", BEFORE_JA)
closes("Valmistasin ette aruande, mis näitas kulude kasvu ja esitasin selle juhatusele.", "ja",
       BEFORE_JA)
closes("Juhtisin projekti, mis kestis kaks aastat ning koolitasin uusi töötajaid.", "ning",
       BEFORE_JA)
# A plain adverb may stand between ja and the verb.
closes("Leidsin vea, mis takistas maksete töötlemist ja hiljem parandasin selle.", "ja", BEFORE_JA)
# A line break ends a list item; the verb that opens the line is the main verb.
lines = ("juhtisin projekti, mis kestis kaks aastat ja koolitasin uusi töötajaid\n"
         "leidsin vea, mis takistas maksete töötlemist ja parandasin selle")
got = issues(lines)
check("both list lines flagged before ja",
      [(i["rule"], i["position"]) for i in got]
      == [(BEFORE_JA[0], lines.index(" ja ") + 1), (BEFORE_JA[0], lines.rindex(" ja ") + 1)],
      str(got))

print("a closed clause, or one that ends the sentence, passes")
for text in (
    "Mees, kes seal seisis, oli minu isa.",
    # The main clause has its verb before the comma.
    "Nägin meest, kes seisis ukse ees ja naeratas.",
    "Ma ütlesin, et lähen vaatan, mis juhtus.",
    "Tunnen seda tööd kahest küljest: õpetajana, kes hindab kirjandeid, "
    "ja õpilasena, keda hinnatakse.",
    # tuli is also a noun (fire): only sure verbs count.
    "Mees, kelle majas tuli lahti pääses, oli õnnelik.",
    # ei and its verb are one predicate.
    "Mees, kes ei oleks tulnud, oli ometi kohal.",
    "Tööd, mida ei tehtaks õigel ajal, tuleks hiljem parandada.",
    "Laps, kes vastust ei teaks, vaikiks.",
    # sobivad qualifies kingad here: the participle, not a verb.
    "Inimesed, kes ostsid sobivad kingad, olid rahul.",
    "Elan majas, mille ehitas mu isa ja milles on kolm tuba.",
    "Räägin firmaga, mis teeb koostööd ülikooli ja haiglaga.",
    "Kohtusin mehega, kes oli tuttav mu isa ja emaga.",
    "Vestlesin õpetajaga, kes töötab koolis ja lastega.",
    "Puhkasin külas, mis asub järve kaldal ja metsas.",
    "Kohtusin tüdrukuga, kes tuli peole üksi ja jalgrattaga.",
    "Esinesin eksperdina, kes on töötanud õpetaja ja koolijuhina.",
    "Film, mille pealkiri on „Tulen homme“, jooksis kinos kaua.",
    # A number's glued full stop before a capital ends the sentence.
    "Leping sõlmiti 1. jaanuaril 2020. Kõik, mis sellele järgnes, on teada.",
    "Algatati veebiportaal ja protsess, mis tipnes arutelupäevaga 6. aprillil 2013. "
    "Arutelus pakutud ideede mõju jäi napiks.",
    # A line break ends a list item.
    "projektijuht, kes vastutab eelarve eest\njuhtisin viieliikmelist meeskonda",
    "Projektijuht, kes vastutab eelarve eest\nJuhtisin viieliikmelist meeskonda",
    "Laps, kes on pikem kui isa, on alles kümneaastane.",
    "Arvuti, mis on vanem kui mina, töötab endiselt.",
    "Dokument, mis tahes kujul esitatud, on kehtiv.",
    "Kõik, mis vaja oli tehtud.",
    "Kes tööd ei tee, see süüa ei saa.",
    "Mees, kes ütles: „Tulen homme“, ei tulnud.",
    "Ta ostis selle, mis oli odav, ja see, mis oli kallis, jäi poodi.",
):
    clean(text)

print("ja inside the clause, or after a clause that is not a kes or mis subject clause, passes")
for text in (
    "Juhtisin projekti, mis kestis kaks aastat ja lõppes edukalt.",
    "Töötasin ettevõttes, kus vastutasin müügi eest ja juhtisin meeskonda.",
    "Mäletan päeva, mil ema tuli koju ja jooksin talle vastu.",
    "Ostsin raamatu, mida ta soovitas ja ma hiljem lugesin.",
    "Ütlesin, et ta tuleb homme ja ma lähen ära.",
    "Juhtisin meeskonda, kes arendas tarkvara ja kellega saavutasime head tulemused.",
    "Kirjutasin õpetajale, kes oli mind aidanud, ja tänasin teda.",
    # The verb after ja can be the clause's own (same person).
    "Kohtusin inimestega, kes töötasid kontoris ja aitasid mind.",
    "Koolitasin töötajaid, kes alustasid tööd ja vajasid tuge.",
    "Mul on sõber, kes elab Tartus ja töötab õpetajana.",
    "Valisin lahenduse, mis oli odavam ja töötas kiiremini.",
    # ei says nothing about the person.
    "Rääkisin kolleegiga, kes oli haige ja ei saanud tulla.",
    "Kohtusin mehega, kes ütles, et tuleb ja aitab.",
):
    clean(text)

print("a closed clause with words that are not its second verb passes")
for text in (
    # ja ei, või ei, ning ei and a conditional: one second predicate.
    "Laenaja, kes on maksega hilinenud ja ei suudaks võlga tasuda, peab pangaga ühendust võtma.",
    "Ta kohtus naabriga, oma vana sõbraga, kes elab Tartus ja ei tahaks kunagi pealinna kolida.",
    "Isik, kes on alaealine või ei oleks muul põhjusel teovõimeline, ei saa lepingut sõlmida.",
    "Kasutaja, kes on sisse loginud ning ei oskaks parooli muuta, leiab juhendi abilehelt.",
    "Taotlus, mis on esitatud tähtaja järel ja ei vastaks nõuetele, jäetakse läbi vaatamata.",
    "Kolleeg, kes oli haige ja ei polnud kohale tulnud, saatis meile kirja.",
    # ei ... ega pairs two words.
    "Laps, kes ei söö ei liha ega kala, vajab tasakaalustatud toitu.",
    "Ravim, mis ei aita ei peavalu ega palavikku, on kasutu.",
    "Kulu, mis oli ei rohkem ega vähem kui miljon eurot, üllatas kõiki.",
    "Hind, mis on ei rohkem ega vähem kui sada eurot, on täiesti mõistlik.",
    # ei tea and jumal teab before a question word: an indefinite phrase.
    "Mees, kes rääkis ei tea kellest, oli ilmselt väsinud.",
    "Mees, kes oli käinud ei tea kus, naasis alles hommikul.",
    "Mees, kes oli käinud jumal teab kus, naasis alles hommikul.",
    # A -vad participle after olema is the predicative.
    "Kandidaadid, kes olid sobivad, kutsuti teise vooru.",
    "Kandidaadid, kes on sobivad, kutsutakse vestlusele.",
    "Kandidaadid, kes pole sobivad, saadetakse koju.",
    "Tulemused, mis on rahuldavad, avaldatakse veebis.",
    "Tingimused, mis olid ahvatlevad, meelitasid ligi palju huvilisi.",
    "Tulemused, mis olid väga rahuldavad, esitati juhatusele.",
    "Tingimused, mis on ahvatlevad noortele, meelitavad huvilisi.",
    # on inside an English name.
    "Arvuti, mis toetab Wake on LAN funktsiooni, käivitub võrgu kaudu.",
    "Platvorm, mis pakub video on demand teenust, kasvab kiiresti.",
    "Lisandmoodul, mis lisab add on funktsiooni, on tasuta.",
    # A table cell edge ends the clause: the verb is the next cell's.
    "| Kood | Selgitus | Millal |\n|---|---|---|\n| E01 | fail, mida ei leitud | tekib käivitamisel |",
    "| Parameeter | Tähendus | Mõju |\n|---|---|---|\n"
    "| retries | kordused, mida tehakse | suurendab töökindlust |",
    "| Roll | Ülesanne |\n|---|---|\n| koordinaator, kes vastutab ajakava eest | jälgib tähtaegu |",
    "Muutuja\tKirjeldus\tMõju\ntimeout\taeg, mille jooksul oodatakse\tkatkestab ühenduse",
    "Juhtisin projekti, mis kestis kaks aastat\tja koolitasin uusi töötajaid",
    # So do single quotation marks around a gloss, arrows and HTML tags.
    "Sõna, mis tähendab ‘on olemas’, on murretes haruldane.",
    "Verb, mille algne tähendus oli ‘läheb ära’, on aja jooksul muutunud.",
    "Sõna, mis tähendab ‚on olemas‘, on murretes haruldane.",
    "Kasutaja, kes pole sisse loginud → suunatakse avalehele",
    "Päring, mis aegub → logitakse hoiatusena",
    "Päring, mis aegub ⇒ logitakse hoiatusena",
    "Päring, mis aegub => logitakse hoiatusena",
    "<li>klient, kes tellib kauba</li><li>saab kinnituse e-postiga</li>",
):
    clean(text)

print("documented limits of the closing comma")
# The comma belongs before the fronted subject kuldne päike; with a word
# before the subject the tool only says it is due before paistis at the
# latest.
closes("Hommikul, kui ärkasin kuldne päike juba paistis.", "paistis", refix=False)
# ei tea before a question word may be the indefinite phrase (käinud ei
# tea kus) or the main clause's verb with a clause of its own, as here
# (the comma belongs before ei): with a sure verb after it, the rule
# abstains.
clean("Mees, kes seal seisis ei tea kus ta elab.")
# A capitalised word the lexicon does not know before on is read as a
# name (mille kirjutas Brennick on klassika), so this English on is still
# read as olema.
closes("Valik, mis lülitab sisse Always on top režiimi, asub menüüs Vaade.", "on", refix=False)
# A capitalised second verb is read as a title; all capitals skip the rule.
clean("MEES, KES SEAL SEISIS OLI MINU ISA.")
# A verb form that is also a noun or a postposition (tuli, kandis) is
# not a sure verb, so the missing comma before tuli is not found.
clean("Mees, kes kandis kotti tuli tuppa.")


def linear_time() -> None:
    """The clause scans read each stretch between commas a bounded number
    of times. The texts are tagged once and the check timed on the tagged
    spans: tagging alone takes 2 to 7 s here, the scans under 0.2 s, a
    quadratic scan minutes."""
    print("linear time on 100,000 characters")

    def cut(unit: str, size: int = 100_000) -> str:
        return (unit * (size // len(unit) + 1))[:size]

    def unknown(i: int) -> str:
        """Four consonants per number: a different word the lexicon does
        not know for each i."""
        letters = ""
        for _ in range(4):
            letters += "bcdfghjklmnpqrstvwxz"[i % 20]
            i //= 20
        return letters

    texts = {
        "both rules, many times": cut("Mees, kes seal seisis oli minu isa. Juhtisin projekti, "
                                      "mis kestis kaks aastat ja koolitasin uusi töötajaid. "),
        "one clause, no comma for 99,000 characters":
            "Mees, kes " + cut("seal ", 99_000) + ", kes seisis oli",
        "a ja clause 99,000 characters long":
            "Juhtisin projekti, mis kestis " + cut("kaks aastat ", 99_000) + " ja koolitasin",
        "ei after ei, then openers only":
            "Mees, kes " + cut("ei ", 49_000) + cut(", kes seal", 50_000),
        "ei ... ega 99,000 characters apart":
            "Mees, kes seisis ei " + cut("liha ", 99_000) + " ega kala, oli",
        "ei tea kus, then 99,000 characters":
            "Mees, kes seisis ei tea kus " + cut("seal ", 99_000) + " oli",
        "fronted subjects, participles, English on":
            cut("Hommikul, kui ärkasin päike juba paistis. Kandidaadid, kes olid sobivad "
                "kutsuti. Arvuti, mis toetab Wake on LAN funktsiooni käivitub. "),
        "on after 1,800 different unknown words": "".join(
            f"Arvuti, mis toetab q{unknown(i)} on demand teenust käivitub. "
            for i in range(1_800)),
    }
    real = server._Text

    class Tagged:
        def __init__(self, tagged) -> None:
            self.morph_analysis = tagged.morph_analysis

        def tag_layer(self, layers) -> None:
            pass

    for label, text in texts.items():
        tagged = real()(text)
        tagged.tag_layer(["morph_analysis"])
        server._only_verb.cache_clear()
        server._vad_participle_only.cache_clear()
        server._lexicon_pos.cache_clear()
        server._nominative_person.cache_clear()
        server._Text = lambda tagged=tagged: (lambda _text: Tagged(tagged))
        try:
            start = time.perf_counter()
            found = server.check_punctuation(text)["issues"]
            elapsed = time.perf_counter() - start
        finally:
            server._Text = real
        check(f"{label}: {elapsed:.2f} s, {len(found)} issues", elapsed < 1.5, f"{elapsed:.2f} s")


linear_time()

print("the description no longer documents the fixed misfires")
doc = server.check_punctuation.__doc__ or ""
check("no pair caveat", "comma goes before the pair" not in doc, doc)
check("no verbless-nagu caveat", "tugev nagu karu" not in doc, doc)
check("no em or en dash", "\u2014" not in doc and "\u2013" not in doc, doc)
check("names the closing-comma rules",
      "`comma-after-subordinate-clause`" in doc
      and "`comma-before-ja-after-subordinate-clause`" in doc, doc)
check("says the closing comma goes there at the latest", "at the latest" in doc, doc)
check("says when the comma goes before the subject", "`, päike`" in doc, doc)
check("says a table cell edge ends the clause", "table cell edge" in doc, doc)
check("no longer says kes and mis are unchecked",
      "kui, mis, kes (their comma depends on meaning)" not in doc, doc)

if failures:
    print(f"\n{len(failures)} failure(s):")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("\nall punctuation tests passed")
