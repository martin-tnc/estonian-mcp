"""Tests for `check_punctuation`: two-part connectives and `nagu`.

The EKI rules these pin (EKI teatmik, "Koma": ühendsidendid, kui- ja
nagu-tarind, koma nihkumine; õigekirja põhireeglid, reegel 44):

1. A TWO-PART CONNECTIVE TAKES ITS COMMA BEFORE THE WHOLE OF IT (Sadas
   vihma, nii et jäime koju; Ta lahkus, ilma et oleks hüvasti jätnud), or,
   for sellepärast et, selleks et, nii et and the like, between the parts
   when the first part belongs to the main clause (Tulin selleks, et
   aidata). ilma et, olgugi et and the like never take one between. The
   tool used to flag `et` in every one of these, and its suggestion `, et`
   turned a correct `ilma et` into the wrong `ilma, et`.

2. nagu TAKES A COMMA ONLY WHEN IT OPENS A CLAUSE WITH A FINITE VERB
   (Vaatas mind, nagu oleksin võõras). A verbless comparison takes none
   (Vaatas mind nagu võõrast; tugev nagu karu), and the tool flagged every
   one of those.

3. A CONJUNCTION BEFORE A SUBORDINATOR TAKES THE COMMA ITSELF: `..., et
   tuleb ja et toob kooki`, never `ja, et`. Where the conjunction joins
   main clauses the comma goes before it (Tahtsin helistada, aga et oli
   hilja, kirjutasin kirja; Ilm oli ilus, ja kuna oli puhkus, ...).

Every flag's suggestion, applied, must give text the tool accepts: the
tool once suggested `lihtsalt ilma, et` and then flagged its own output.

Run via:

    uv run python tests/test_punctuation.py
"""
from __future__ import annotations

import sys
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


def one(text: str, word: str, suggestion: str, at: str | None = None,
        rule: str = "comma-before-clause-conjunction") -> None:
    """Exactly one issue, on `word`, starting where `at` (default `word`)
    first occurs in the text, and the text with the suggestion applied
    passes."""
    got = issues(text)
    want_pos = text.index(at if at is not None else word)
    check(f"one flag on {word!r} -> {suggestion!r}: {text}",
          len(got) == 1
          and got[0]["word"] == word
          and got[0]["suggestion"] == suggestion
          and got[0]["position"] == want_pos
          and got[0]["rule"] == rule
          and bool(got[0].get("rule_estonian")),
          str(got))
    if len(got) == 1:
        pos, length = got[0]["position"], len(got[0]["word"])
        head = text[:pos].rstrip() if suggestion.startswith(",") else text[:pos]
        fixed = head + got[0]["suggestion"] + text[pos + length:]
        again = issues(fixed)
        check(f"  its fix passes: {fixed}", again == [], str(again))


print("a comma before the whole connective is right")
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
    "Võtan selle, eeldusel et hind on õige.",
    "Aadel vandus truudust, tingimusel et privileegid säilivad.",
    "Sõime edasi, olgugi et kõht oli juba täis.",
    "Kõik oli hästi, ainult et raha oli vähe.",
    "Söö, mida tahad, peaasi et kõht saab täis.",
    "Ta jõudis koju, vaevalt et keegi märkas.",
):
    clean(text)

print("a comma between the parts is right where the first part is the main clause's")
for text in (
    "Tulin selleks, et aidata.",
    "Tegin nii, nagu kokku lepiti.",
    "Tegin nii, et kõik said aru.",
    "Lõke ei süttinud sellepärast, et puud olid märjad.",
    "Ta tuli tööle hoolimata sellest, et oli haige.",
    "Ma tahan ainult, et sa oleksid õnnelik.",
    "Mul on ükskõik, kuhu sa lähed.",
    # ilma belongs to `jäi ilma` (went without), or is the noun ilm.
    "Ta jäi ilma, et teised saaksid.",
    "Ta ootas ilusat ilma, et minna randa.",
):
    clean(text)

print("a connective that opens the sentence needs no comma")
for text in (
    "Olgugi et kõht oli juba täis, sõime edasi.",
    "Ilma et keegi teaks, lahkus ta.",
    "Selle asemel et kurta, tegutse.",
    "Selleks et aidata, tulin varem.",
    "Nii et me jäime koju.",
    "Vaevalt et ta tuleb.",
    "Ükskõik kuhu sa lähed, ma tulen kaasa.",
):
    clean(text)

print("ükskõik kuhu (= kuhu tahes) opens no clause")
clean("Võid minna ükskõik kuhu.")

print("a conjunction before a subordinator takes the comma itself")
clean("Ta ütles, et tuleb ja et toob kooki.")
clean("Ta tuli, kuid kuna oli hilja, läks ta varsti ära.")
one("Ta ei tulnud sest et oli haige.", "sest", ", sest")

print("no comma anywhere: one flag, before the whole connective")
one("Sadas vihma nii et jäime koju.", "nii et", ", nii et")
one("Tulin selleks et aidata.", "selleks et", ", selleks et")
one("Ta lahkus ilma et oleks hüvasti jätnud.", "ilma et", ", ilma et")
one("Lõke ei süttinud sellepärast et puud olid märjad.",
    "sellepärast et", ", sellepärast et")
one("Ta jäi koju seetõttu et oli haige.", "seetõttu et", ", seetõttu et")
one("Ta tegutses selle asemel et kurta.", "selle asemel et", ", selle asemel et")
one("Ta tuli tööle hoolimata sellest et oli haige.",
    "hoolimata sellest et", ", hoolimata sellest et")
one("Ta tuli vaatamata sellele et oli väsinud.",
    "vaatamata sellele et", ", vaatamata sellele et")
one("Sõime edasi olgugi et kõht oli täis.", "olgugi et", ", olgugi et")
one("Kõik oli hästi ainult et raha oli vähe.", "ainult et", ", ainult et")
one("Ta tuli koju nii nagu ta alati tuleb.", "nii nagu", ", nii nagu")
one("Ma jään siia ilma et keegi teaks.", "ilma et", ", ilma et")

print("no comma anywhere, first part the main clause's: the comma goes before et")
# nii or ainult right after a finite verb is that verb's (EKI: the manner
# nii et takes the comma between its parts).
one("Tegin nii et kõik said aru.", "et", ", et")
one("Tegin nii nagu kokku lepiti.", "nagu", ", nagu")
one("Tee just nii et keegi ei näe.", "et", ", et")
one("Ma tahan ainult et sa oleksid õnnelik.", "et", ", et")
# A focus particle makes the first part a stressed main-clause word.
one("Tulin just selleks et aidata.", "et", ", et")
# ilma as the main clause's adverb or the noun ilm: the old answer stands.
one("Ta jäi rahast ilma et teised saaksid.", "et", ", et")
one("Ta ootas ilusat ilma et minna randa.", "et", ", et")
one("Mul on ükskõik kuhu sa lähed.", "kuhu", ", kuhu")

print("a comma inside ilma et or olgugi et is wrong")
# The old tool's own suggestion produced these.
one("Ta lahkus ilma, et oleks hüvasti jätnud.", "ilma, et", ", ilma et",
    rule="no-comma-inside-conjunction")
one("Ilma, et keegi teaks, lahkus ta.", "Ilma, et", "Ilma et",
    rule="no-comma-inside-conjunction")
one("Sõime edasi olgugi, et kõht oli täis.", "olgugi, et", ", olgugi et",
    rule="no-comma-inside-conjunction")

print("a verbless nagu comparison takes no comma")
for text in (
    "Ta on tugev nagu karu.",
    "Ta jooksis nagu tuul.",
    "Ta on valge nagu lumi.",
    "Vaatas mind nagu võõrast.",
    "Ta käitus nagu laps.",
    "Ta on samasugune nagu ema.",
    # tuli is also the noun "fire"; the sentence analysis reads it as a verb.
    "Ta oli punane nagu tuli.",
    # The finite verb after the comparison is the main clause's (EKI).
    "Kassid nagu kõik koduloomad vajavad hoolitsust.",
    "Sina nagu minagi tahame puhata.",
    # A conjunction or a relative word ends the comparison.
    "Ta jooksis nagu tuul ja hüppas üle aia.",
    "Ta on tugev nagu karu kes elab metsas.",
    "Ta jooksis nagu ei keegi teine.",
    # nagu the particle ("kind of").
    "Ma nagu ei tea.",
    "Ta on tugev nii nagu karu.",
):
    clean(text)

print("a nagu clause with a finite verb takes the comma")
one("Tee nagu tahad.", "nagu", ", nagu")
one("Ta rääkis nagu oleks ta seal olnud.", "nagu", ", nagu")
one("Vaatas mind nagu oleksin võõras.", "nagu", ", nagu")
one("Ma tegin nagu sina tegid.", "nagu", ", nagu")
one("Ta käitus nagu ta ei teadnud midagi.", "nagu", ", nagu")
one("Ta käitus nagu poleks midagi juhtunud.", "nagu", ", nagu")
one("Tundub nagu keegi oleks siin.", "nagu", ", nagu")
one("Ta vastas nagu kästi.", "nagu", ", nagu")

print("the single conjunctions still fire")
one("Ma tean et see on hea.", "et", ", et")
one("Ta ei tulnud sest oli haige.", "sest", ", sest")
one("Ta tuli kuid lahkus kohe.", "kuid", ", kuid")
one("Ma ei käinud mitte Prahas vaid Viinis.", "vaid", ", vaid")
one("Ta jäi koju kuigi ilm oli ilus.", "kuigi", ", kuigi")
one("Ta ei tulnud kuna oli haige.", "kuna", ", kuna")
one("Ta oli haige mistõttu ta ei tulnud.", "mistõttu", ", mistõttu")
one("Ta oli haige millepärast ta ei tulnud.", "millepärast", ", millepärast")
one("Ma ei tea kuhu ta läks.", "kuhu", ", kuhu")
one("Ta oli nii väsinud et jäi magama.", "et", ", et")

print("a nagu clause whose verb is also a noun takes the comma")
# võis (või), soovis (soov), palus (palu), sõnas, lisas, selgus: the verb
# counts after a subject or adverb, or before an infinitive.
one("Kõik läks nagu võis arvata.", "nagu", ", nagu")
one("Hind langes nagu võis eeldada.", "nagu", ", nagu")
one("Raport valmis nagu tellija soovis.", "nagu", ", nagu")
one("Tegin nagu ta palus.", "nagu", ", nagu")
one("Tee nii nagu ema palus.", "nagu", ", nagu")
one("Olukord on keeruline nagu peaminister sõnas.", "nagu", ", nagu")
one("Hinnad tõusevad nagu juhatuse esimees lisas.", "nagu", ", nagu")
one("Ta oli süütu nagu hiljem selgus.", "nagu", ", nagu")
# The noun of a comparison stays a noun, even where the sentence
# analysis reads it as a verb (ahju tuli = came into the oven).
for text in (
    "Ta oli kuum nagu ahju tuli.",
    "Ta on külm nagu talvine jää.",
    "Maja põles nagu tuli lõkkes.",
    "Ta nagu tema vend tuli hilja.",
    "Eesti nagu Läti tuli kriisiga toime.",
):
    clean(text)

print("a nagu clause before the main verb takes the comma")
one("See projekt nagu me teame on hilinenud.", "nagu", ", nagu")
one("Eesti majandus nagu analüütikud ennustasid kasvas kaks protsenti.", "nagu", ", nagu")
one("Meie meeskond nagu te kindlasti teate töötab kaugtööl.", "nagu", ", nagu")
one("Tallinna Vesi nagu ettevõte teatas tõstab hindu.", "nagu", ", nagu")
one("Ta nagu ma juba ütlesin on väga tark.", "nagu", ", nagu")
for text in (
    "Linnud nagu lennukid lendavad kõrgel.",
    "Mari nagu Jüri ei ole kodus.",
    "Mari nagu Jüri ei tea midagi.",
):
    clean(text)

print("a comparative kui does not hide the main verb")
one("Tulemused olid paremad kui eelmisel aastal nagu juhataja märkis.", "nagu", ", nagu")
one("Ta töötas rohkem kui keegi teine nagu ülemus ütles.", "nagu", ", nagu")
# A kui that opens a clause still ends the main clause.
clean("Ta oli kodus kui lapsed nagu tavaliselt koolist tulid.")

print("a sentence-initial noun that is also an imperative")
one("„Tee nagu tahad,“ ütles ema.", "nagu", ", nagu")
one("Tule nagu saad.", "nagu", ", nagu")
for text in (
    "Tee nagu kohv sisaldab kofeiini.",
    "Muna nagu piim sisaldab palju valku.",
    "Luba nagu iga teine dokument kehtib viis aastat.",
):
    clean(text)

print("ilma the noun: an adjective before it, or a verb such as ootama")
for text in (
    "Lootsime sooja ilma, et saaks ujuma minna.",
    "Loodame sooja ilma, et lapsed saaksid õues mängida.",
    "Ootasime külma ilma, et jää kannaks.",
    "Ootasime ilma, et minna randa.",
):
    clean(text)
one("Lootsime sooja ilma et saaks ujuma minna.", "et", ", et")
# The disambiguation reads these ilma as the noun; nothing else does.
one("Ta maksis arve ära ilma, et oleks seda kontrollinud.", "ilma, et", ", ilma et",
    rule="no-comma-inside-conjunction")
one("ILMA, ET KEEGI TEAKS, LAHKUS TA.", "ILMA, ET", "ILMA ET",
    rule="no-comma-inside-conjunction")
# A predicative adjective, or one after midagi, does not make ilma a noun.
one("Ta oli vaba ilma, et keegi teda kontrolliks.", "ilma, et", ", ilma et",
    rule="no-comma-inside-conjunction")
one("Ta tahtis midagi uut ilma, et peaks maksma.", "ilma, et", ", ilma et",
    rule="no-comma-inside-conjunction")

print("a particle before a closed connective does not split it")
one("Ta lahkus lihtsalt ilma et oleks hüvasti jätnud.", "ilma et", ", ilma et")
one("Ta tuli ikka olgugi et oli haige.", "olgugi et", ", olgugi et")
one("Taotluse saab esitada ka ilma et peaks kontorisse tulema.", "ilma et", ", ilma et")
for text in (
    "Taotluse saab esitada, ka ilma et peaks kontorisse tulema.",
    # A comma before a focus particle sets off the clause.
    "Ma ei tulnud puhkama, vaid et aidata.",
    "Ta tegi seda, eriti kuna oli aega.",
):
    clean(text)

print("ainult et after a verb that takes no et clause is the connective")
one("Kõik töötab ainult et ekraan vilgub.", "ainult et", ", ainult et")
one("Kõik töötab hästi ainult et ekraan vilgub.", "ainult et", ", ainult et")
one("Ma tahan tegelikult ainult et sa tuleksid.", "et", ", et")
one("Mul on vaja ainult et sa tuleksid.", "et", ", et")

print("on ükskõik, kuhu past an adverb; kuhu tahes opens no clause")
one("Mulle on täiesti ükskõik kuhu me sõidame.", "kuhu", ", kuhu")
one("Mul on ju ükskõik kuhu sa lähed.", "kuhu", ", kuhu")
one("Mul on päris ükskõik kuhu raha kulub.", "kuhu", ", kuhu")
one("Mul pole ükskõik kuhu sa lähed.", "kuhu", ", kuhu")
one("Ma järgnen sulle kuhu tahes sa lähed.", "kuhu", ", kuhu")
for text in (
    "Ma oleksin ükskõik kuhu läinud.",
    "Võid istuda kuhu tahes.",
    "Võid minna kuhu iganes.",
    # EKI: the idiom takes no comma.
    "Ta valetab nii et suu suitseb.",
):
    clean(text)

print("a coordinator joining main clauses takes the subordinate clause's comma")
one("Tahtsin helistada aga et oli hilja kirjutasin kirja.", "aga et", ", aga et")
one("Ma tahtsin tulla aga kuna oli hilja jäin koju.", "aga kuna", ", aga kuna")
one("Lubasime tulla aga kuigi proovisime ei jõudnud me kohale.", "aga kuigi", ", aga kuigi")
one("Ta lubas tulla ent kuna jäi haigeks ei tulnud.", "ent kuna", ", ent kuna")
one("Tahtsin helistada aga kuna oli hilja, kirjutasin kirja.", "aga kuna", ", aga kuna")
one("Ilm oli ilus ja kuna oli puhkus läksime randa.", "ja kuna", ", ja kuna")
one("Ta ütles, et tuleb aga et ei too kooki.", "aga et", ", aga et")
# aga the particle (= however): the comma stays before et.
one("Hiljem selgus aga et ta oli haige.", "et", ", et")
one("Mine aga kuhu tahad.", "kuhu", ", kuhu")
for text in (
    "Hiljem selgus aga, et ta oli haige.",
    "Tahtsin helistada, aga et oli hilja, kirjutasin kirja.",
    "Ilm oli ilus, ja kuna oli puhkus, läksime randa.",
    # A reporting verb after the clauses is no second main clause.
    "Valitsus otsustas, et maksud tõusevad ja et toetused kahanevad, teatas minister.",
):
    clean(text)

print("a word after an opening quotation mark starts a sentence")
for text in (
    "Ta küsis: „Kuhu sa lähed?“",
    'Ta küsis: "Kuhu sa lähed?"',
    "„Et oleks selge, koosolek jääb ära,“ ütles juht.",
    "Ta ütles: „Nii et homme ei tule keegi.“",
    "«Kuna sajab, jääme koju,» ütles ta.",
):
    clean(text)

print("the description no longer documents the fixed misfires")
doc = server.check_punctuation.__doc__ or ""
check("no pair caveat", "comma goes before the pair" not in doc, doc)
check("no verbless-nagu caveat", "tugev nagu karu" not in doc, doc)
check("no em or en dash", "\u2014" not in doc and "\u2013" not in doc, doc)

if failures:
    print(f"\n{len(failures)} failure(s):")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("\nall punctuation tests passed")
