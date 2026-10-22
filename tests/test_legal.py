"""Tests for the legal-Estonian tools (check_legalese, check_defined_terms).

Both are pure (Vabamorf morphology + regex, no fastText/WordNet), so they run
locally without the model artifacts. The check_compound_familiarity legal
de-noise assertion lives in test_smoke.py (it needs the fastText model, which
only CI has).

Run via:

    uv run python tests/test_legal.py
"""
from __future__ import annotations

import re
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


def legalese_tests() -> None:
    print("check_legalese")
    para = ("Käesolevas seaduses sätestatut kohaldatakse võlasuhetele. "
            "Juhul kui võlgnik ei täida kohustust, tekib võlausaldaja ees "
            "vastutus ning õigus nõuda kahjuhüvitist.")
    r = server.check_legalese(para)
    rules = {i["rule"] for i in r["issues"]}
    check("flags 'käesolev' archaic filler", "archaic-filler" in rules, str(r["issues"]))
    check("flags 'juhul kui' phrase", "legalese-phrase" in rules, str(r["issues"]))
    # käesolev suggestion is the plain 'see'
    kaes = next((i for i in r["issues"] if i["rule"] == "archaic-filler"), {})
    check("käesolev → see", kaes.get("suggestion") == "see", str(kaes))
    # terms of art are surfaced and NOT flagged as filler
    lemmas = {t["lemma"] for t in r["terms_of_art"]}
    check("protects legal term võlgnik", "võlgnik" in lemmas, str(lemmas))
    check("protects several terms of art", len(r["terms_of_art"]) >= 4, str(lemmas))
    check("no legal term is flagged as filler",
          not any(server._is_legal_term(i.get("word", "")) for i in r["issues"] if "word" in i),
          str(r["issues"]))
    # The caller's own text and a fixed note are not sent back; the
    # terms of art keep their first-occurrence anchor.
    check("no input echo or static note", "text" not in r and "note" not in r, str(sorted(r)))
    check("result keys", set(r) == {"issues", "terms_of_art", "summary_estonian"}, str(sorted(r)))
    check("terms_of_art keep their position",
          all(isinstance(t.get("position"), int) for t in r["terms_of_art"]), str(r["terms_of_art"]))

    # Plain modern Estonian: no archaic-filler flags, no terms of art.
    clean = server.check_legalese("See on lühike ja selge lause.")
    check("plain text → no archaic-filler",
          not any(i["rule"] == "archaic-filler" for i in clean["issues"]), str(clean["issues"]))

    # Over-long sentence → complex-sentence flag.
    long_s = ("Pool kohustub, arvestades kõiki asjaolusid, tingimusi, tähtaegu "
              "ja erandeid, mis tulenevad seadusest, lepingust, tavast ning "
              "kohtupraktikast, täitma oma kohustused nõuetekohaselt, õigel ajal "
              "ja täies ulatuses ilma põhjendamatu viivituseta.")
    ls = server.check_legalese(long_s)
    check("flags over-long sentence", any(i["rule"] == "complex-sentence" for i in ls["issues"]),
          str([i["rule"] for i in ls["issues"]]))
    cs = next((i for i in ls["issues"] if i["rule"] == "complex-sentence"), {})
    check("complex-sentence explanation is the per-sentence count only",
          re.fullmatch(r"Lause on \d+ sõna ja \d+ koma\.", cs.get("explanation", "")) is not None,
          str(cs))
    check("complex-sentence keeps its suggestion",
          cs.get("suggestion") == "jaga lause lühemateks osadeks", str(cs))
    check("complex-sentence keeps the issue keys",
          set(cs) == {"phrase", "position", "rule", "rule_estonian", "explanation", "suggestion"},
          str(sorted(cs)))


def defined_terms_tests() -> None:
    print("check_defined_terms")
    contract = ('Käesoleva lepingu (edaspidi «Leping») pooled on AS Müük '
                '(edaspidi «Müüja») ja OÜ Ostja (edaspidi «Ostja»). Müüja annab '
                'kauba üle. Ostja tasub hinna vastavalt Lepingu punkt 3 ja § 5 lg 2. '
                'Pooled (edaspidi «Pooled») kinnitavad, et Leping jõustub.')
    d = server.check_defined_terms(contract)
    defined = {t["term"] for t in d["defined_terms"]}
    check("extracts «Leping»", "Leping" in defined, str(defined))
    check("extracts «Müüja» and «Ostja»", {"Müüja", "Ostja"} <= defined, str(defined))
    xrefs = {x["reference"] for x in d["cross_references"]}
    check("finds 'punkt 3' cross-ref", any("punkt 3" in x for x in xrefs), str(xrefs))
    check("finds '§ 5' cross-ref", any(x.startswith("§") for x in xrefs), str(xrefs))
    # every defined term here is used again → no unused issues
    check("used terms → no defined-but-unused",
          not any(i["rule"] == "defined-but-unused" for i in d["issues"]), str(d["issues"]))
    # No preview of the caller's document and no fixed note.
    check("no text preview or note", "text" not in d and "note" not in d, str(sorted(d)))
    check("result keys",
          set(d) == {"defined_terms", "cross_references", "issues", "summary_estonian"},
          str(sorted(d)))

    # defined-but-unused detection
    unused = server.check_defined_terms("Käesolev kokkulepe (edaspidi «Kokkulepe») jõustub täna.")
    check("flags defined-but-unused",
          any(i["rule"] == "defined-but-unused" for i in unused["issues"]), str(unused["issues"]))
    un = next((i for i in unused["issues"] if i["rule"] == "defined-but-unused"), {})
    check("defined-but-unused keeps its term-specific explanation",
          "«Kokkulepe»" in un.get("explanation", ""), str(un))

    # duplicate definition
    dup = server.check_defined_terms(
        "Pool (edaspidi «Müüja») ja teine (edaspidi «Müüja»). Müüja tegutseb.")
    check("flags duplicate-definition",
          any(i["rule"] == "duplicate-definition" for i in dup["issues"]), str(dup["issues"]))
    dd = next((i for i in dup["issues"] if i["rule"] == "duplicate-definition"), {})
    check("duplicate-definition keeps its term-specific explanation",
          dd.get("explanation") == "Mõiste «Müüja» on defineeritud 2 korda.", str(dd))
    check("definitions stays on every term",
          dup["defined_terms"][0]["definitions"] == 2
          and all("definitions" in t for t in d["defined_terms"]),
          str(dup["defined_terms"]))

    # long document under the raised cap does not raise
    big = "Käesoleva lepingu punkt 1. " * 20000  # ~540k? keep under cap
    big = big[:server.MAX_DOC_CHARS - 10]
    try:
        bd = server.check_defined_terms(big)
        check("accepts long doc under MAX_DOC_CHARS", True)
        check("a long doc is not echoed either", "text" not in bd, str(sorted(bd)))
    except Exception as e:
        check("accepts long doc under MAX_DOC_CHARS", False, str(e))
    # over the doc cap raises
    try:
        server.check_defined_terms("a" * (server.MAX_DOC_CHARS + 1))
        check("over MAX_DOC_CHARS raises", False, "no exception")
    except ValueError:
        check("over MAX_DOC_CHARS raises", True)


def is_legal_term_tests() -> None:
    print("_is_legal_term")
    check("solidaarvõlgnik is legal", server._is_legal_term("solidaarvõlgnik"))
    check("inflected võlasuhetele is legal", server._is_legal_term("võlasuhetele"))
    check("hagiavaldus (compound head) is legal", server._is_legal_term("hagiavaldus"))
    check("ordinary word 'koer' is not legal", not server._is_legal_term("koer"))
    check("ordinary word 'ilus' is not legal", not server._is_legal_term("ilus"))


def common_legal_usage_tests() -> None:
    print("common_legal_usage")
    r = server.common_legal_usage("kohustus")
    check("known legal term found", r["found"] is True, str(r.get("summary_estonian")))
    check("has a frequency", isinstance(r["frequency"], int) and r["frequency"] > 0, str(r["frequency"]))
    check("common_after is list of {word,count}",
          all("word" in x and "count" in x for x in r["common_after"]), str(r["common_after"]))
    after = {x["word"] for x in r["common_after"]}
    check("canonical 'kohustuse täitmine' present", "täitmine" in after, str(after))
    # The caller's word and a fixed note are not sent back.
    check("no word echo or note", "word" not in r and "note" not in r, str(sorted(r)))
    check("summary is the frequency sentence only",
          r["summary_estonian"] == f"'kohustus' esineb juriidilises korpuses {r['frequency']} korda.",
          r["summary_estonian"])

    # The summary names the index entry it counted: the lemma for an
    # inflected form, the word itself when only the fallback key matched.
    inflected = server.common_legal_usage("kohustuse")
    check("summary names the lemma", inflected["summary_estonian"].startswith("'kohustus' "),
          inflected["summary_estonian"])
    fallback = server.common_legal_usage("võime")
    check("summary names the matched entry on fallback",
          fallback["found"] and fallback["summary_estonian"].startswith("'võime' "),
          fallback["summary_estonian"])

    r2 = server.common_legal_usage("hagi")
    before = {x["word"] for x in r2["common_before"]}
    check("hagi has collocations", r2["found"] and (before or r2["common_after"]), str(r2))

    # Non-legal word → not found, empty lists, no crash.
    nf = server.common_legal_usage("koer")
    check("non-legal word → found False", nf["found"] is False, str(nf))
    check("not-found → empty collocations", nf["common_before"] == [] and nf["common_after"] == [])
    check("not-found: no word echo or note", "word" not in nf and "note" not in nf, str(sorted(nf)))
    check("not-found summary names the word", "'koer'" in nf["summary_estonian"], nf["summary_estonian"])

    # Single-word contract enforced.
    try:
        server.common_legal_usage("kaks sõna")
        check("rejects whitespace", False, "no exception")
    except ValueError:
        check("rejects whitespace", True)


legalese_tests()
defined_terms_tests()
is_legal_term_tests()
common_legal_usage_tests()

if failures:
    print(f"\n{len(failures)} failure(s):")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("\nall legal-tool tests passed")
