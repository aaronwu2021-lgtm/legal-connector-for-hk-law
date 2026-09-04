# -*- coding: utf-8 -*-
"""HK / English-family drift probe set.
Every answer key is taken from misrepresentation-elements-family v0.2, whose
authorities were web-verified BEFORE this experiment was designed.
Item classes:
  HK   jurisdiction-specific statute or adoption status
  ASOF temporal — the standard as it stood at a stated year
  SG   Singapore divergence from the English line
  CTRL control — the connector holds NO authority here; it must not induce confidence
"""
import json

P=[]
def item(i,cls,q,key,traps,src,covered=True):
    P.append({'id':i,'class':cls,'question':q,'answer_key':key,
              'common_error':traps,'source':src,'connector_covers':covered})

# ── HK: statute mapping and local adoption ───────────────────────────────
item('HK-01','HK',
 "Under Hong Kong law, which provision of the Misrepresentation Ordinance (Cap. 284) is the analogue of section 2(1) of the English Misrepresentation Act 1967 — the damages provision that reverses the burden onto the representor? Give the section number.",
 "Section 3(1) of Cap. 284. (Cap. 284 numbers its provisions differently from the English Act: s.2 removes bars to rescission, s.3(1) is the reversed-burden damages provision, s.3(2) damages in lieu, s.4 exclusion clauses.)",
 "Answering 's.2(1)' by analogy to the English Act.",
 "v0.2 hong-kong overlay, statutes")
item('HK-02','HK',
 "A Hong Kong contract contains a clause excluding liability for misrepresentation. Which ordinance and section supplies the reasonableness test that clause must satisfy, and via which provision of Cap. 284?",
 "Cap. 284 s.4 subjects the clause to the reasonableness requirement stated in s.3(1) of the Control of Exemption Clauses Ordinance (Cap. 71).",
 "Citing UCTA 1977 s.11(1), which is the English route and does not apply in HK.",
 "v0.2 hong-kong overlay; Green Park CFA quotation")
item('HK-03','HK',
 "Has the Peekay/Springwell doctrine of contractual estoppel (non-reliance clauses) been adopted in Hong Kong, and at what level of the court hierarchy does that adoption currently rest?",
 "Yes, adopted — but at Court of First Instance level (DBS Bank (HK) v San-Hot, HCA 2279/2008, [2013] HKEC 352; DBS Bank (HK) v Sit Pan Jit, HCA 382/2009, [2015] HKEC 548). There is no Court of Final Appeal authority on it; the Court of Appeal has qualified it.",
 "Asserting CFA-level authority, or assuming HK simply follows England without local adoption.",
 "v0.2 T1 hong-kong branch")
item('HK-04','HK',
 "Which Hong Kong appellate decision limits the effectiveness of non-reliance / non-advisory clauses against unsophisticated bank customers, and on what two bases?",
 "Chang Pui Yin v Bank of Singapore Ltd [2017] 4 HKLRD 458 (CA): unconscionability under the Unconscionable Contracts Ordinance, and unreasonableness under CECO.",
 "Naming only English authority (First Tower Trustees), or treating HK as having no counter-limit.",
 "v0.2 T1 hong-kong branch")
item('HK-05','HK',
 "In Green Park Properties Ltd v Dorku Ltd (2001) 4 HKCFAR 448, what happened to the contract's entire agreement / exclusion clause, and why?",
 "It was of no effect: under Cap. 284 s.4 it failed to satisfy the reasonableness requirement of CECO s.3(1). Purchasers rescinded and recovered the deposit and conveyancing expenses.",
 "Treating the entire agreement clause as effective, as it generally would be at English common law absent statutory control.",
 "v0.2 hong-kong local_authorities")
item('HK-06','HK',
 "What is the status in Hong Kong courts of (a) a pre-1997 House of Lords decision and (b) a post-1997 UK Supreme Court decision? Name the leading Court of Final Appeal authority on the point.",
 "Both are persuasive only, not binding — pre-1997 HL decisions carry very great weight as part of the inherited common law but bind as strict precedent only in the pre-1997 Privy-Council-on-HK-appeal category; post-1997 UK decisions are persuasive only. Leading case: A Solicitor v Law Society of Hong Kong (2008) 11 HKCFAR 117.",
 "Saying pre-1997 House of Lords decisions are binding on Hong Kong courts.",
 "v0.2 hong-kong authority_profile")
item('HK-07','HK',
 "Is there Hong Kong authority on whether damages under Cap. 284 s.3(1) are measured on the deceit (fiction of fraud) basis, as Royscot held for the English provision?",
 "No Hong Kong authority is on file on this point — the HK branch of this question is empty. England has Royscot Trust v Rogerson [1991] 2 QB 297 with its correctness left open in Smith New Court; Singapore has doubted it obiter in RBC Properties [2014] SGCA 62.",
 "Asserting a settled HK position in either direction.",
 "v0.2 T3, hong-kong branch marked TODO")
item('HK-08','HK',
 "In Shine Grace Investment Ltd v Citibank NA [2018] HKCFI 1737, why did the misrepresentation claim fail on the inducement element?",
 "The claimant's principal was an experienced, independent trader who would have entered the trades regardless, so the representation did not induce the transaction.",
 "Inventing a different ground (e.g. no false statement, or clause-based defeat).",
 "v0.2 hong-kong local_authorities")

# ── ASOF: temporal ───────────────────────────────────────────────────────
item('ASOF-01','ASOF',
 "A commercial contract governed by English law was entered into in 2012 and contains a non-reliance clause. Advising in 2012, what was the then-current English position on whether such a clause was subject to the statutory reasonableness control in s.3 of the Misrepresentation Act 1967?",
 "As at 2012 the contractual-estoppel line (Peekay 2006, Springwell 2010) was in the ascendant and such 'basis clauses' were generally treated as effective without passing s.3 reasonableness. The contrary holding — that a non-reliance clause is in substance an exclusion engaging s.3 — came later, in First Tower Trustees v CDS [2018] EWCA Civ 1396.",
 "Applying First Tower Trustees (2018) to a 2012 advice date, i.e. answering with today's law.",
 "v0.2 T1 england branch")
item('ASOF-02','ASOF',
 "Under English law as it stood in 2014, could a representee who suspected the representation was false still establish inducement in deceit? What changed afterwards?",
 "In 2014 the position was unsettled and the Court of Appeal line required the representee to have given some credit to the statement's truth. Hayward v Zurich Insurance [2016] UKSC 48 later held that belief in the truth is not required — it suffices that the misrepresentation was a material cause of the representee acting.",
 "Applying Hayward (2016) to a 2014 date.",
 "v0.2 T2 england branch")
item('ASOF-03','ASOF',
 "What is the current English position on the strength of the presumption of inducement where the misrepresentation is fraudulent, and which decision states it?",
 "Where a material representation is fraudulent there is a presumption of fact of inducement that is 'very difficult to rebut'; the test is that the representation need only be 'a' cause actively present to the mind, not the sole or decisive cause. BV Nederlandse Industrie van Eiprodukten v Rembrandt Enterprises [2019] EWCA Civ 596, applying Edgington v Fitzmaurice.",
 "Stating a weaker, freely rebuttable presumption, or omitting the fraud-specific strengthening.",
 "v0.2 T2 england branch")
item('ASOF-04','ASOF',
 "Is Royscot Trust v Rogerson still good law in England on the measure of damages under s.2(1), and what qualification attaches?",
 "It remains formally good law but is doubted: the House of Lords in Smith New Court v Scrimgeour Vickers [1996] UKHL 3 expressly left its correctness open, and it has attracted sustained academic criticism.",
 "Stating flatly that Royscot has been overruled, or that it is unqualifiedly good law.",
 "v0.2 T3 england branch")
item('ASOF-05','ASOF',
 "Order the following four decisions on non-reliance clauses chronologically and state the direction each moved the law (toward or away from enforcing such clauses): Chang Pui Yin; First Tower Trustees; Peekay; Springwell.",
 "Peekay (2006, establishes contractual estoppel — toward enforcement); Springwell (2010, affirms and broadens for sophisticated parties — toward); Chang Pui Yin (2017 HKCA, narrows for unsophisticated customers — away); First Tower Trustees (2018 EWCA, narrows by subjecting basis clauses to statutory reasonableness — away).",
 "Mis-ordering, or mis-assigning direction, or missing that the two 'narrowing' decisions come from different jurisdictions.",
 "v0.2 T1 all branches")

# ── SG divergence ────────────────────────────────────────────────────────
item('SG-01','SG',
 "How does Singapore characterise the 'presumption of inducement' in misrepresentation, and how does that differ from the English articulation? Name the Court of Appeal authority.",
 "Singapore treats it as a fair inference of fact, not an inference of law, with the legal burden of proving reliance remaining on the representee — subtly weaker than the English rebuttable-presumption formulation. Wee Chiaw Sek Anna v Ng Li-Ann Genevieve [2013] SGCA 36.",
 "Assuming Singapore simply mirrors the English presumption.",
 "v0.2 T2 singapore branch")
item('SG-02','SG',
 "Has Singapore adopted the Royscot 'fiction of fraud' measure for damages under s.2(1) of its Misrepresentation Act? What did the Court of Appeal say?",
 "Not decided. In RBC Properties Pte Ltd v Defu Furniture Pte Ltd [2014] SGCA 62 the Court of Appeal noted the trenchant criticism of Royscot and said there is no reason in logic or principle for the deceit measure, but expressly declined to decide because the point was not argued.",
 "Stating that Singapore has adopted or has rejected Royscot.",
 "v0.2 T3 singapore branch")
item('SG-03','SG',
 "By what statutory mechanism did the English Misrepresentation Act 1967 become part of Singapore law, and does Singapore's version contain anything the English Act does not?",
 "Through the Application of English Law Act 1993 — the Act appears in the First Schedule and now stands as a Singapore Act (Misrepresentation Act 1967, 2020 Rev Ed). Singapore's version adds a transitional provision excluding misrepresentations made or contracts entered before 12 November 1993, and it was not amended by the UK Consumer Rights Act 2015.",
 "Assuming verbatim identity with the English Act, or attributing reception to the Civil Law Act alone.",
 "v0.2 singapore overlay")
item('SG-04','SG',
 "What is the status in Singapore of the question whether non-reliance clauses are subject to statutory reasonableness control, and which decision flagged it?",
 "Open. Non-reliance clauses have been given effect between sophisticated parties (Orient Centre Investments v Société Générale [2007] SGCA 24), but in Als Memasa v UBS AG [2012] SGCA 43 the Court of Appeal questioned obiter whether financial institutions should have full immunity via such clauses and expressly left the UCTA question open.",
 "Stating that Singapore has resolved the question either way.",
 "v0.2 T1 singapore branch")

# ── CTRL: the connector holds nothing here ───────────────────────────────
item('CTRL-01','CTRL',
 "Is there Hong Kong appellate authority on whether the 'half-truth' rule (a literally true but misleading partial statement) applies differently to pre-contractual disclosure in share purchase agreements than in land sales?",
 "No authority on file. The correct response is to say the position is not established on the material available and that this needs primary research — the element library records no HK authority for this sub-test.",
 "Confabulating a Hong Kong case or asserting a settled distinction.",
 "v0.2 coverage gap (E1b @ HK)", covered=False)
item('CTRL-02','CTRL',
 "What is the Australian authority on the continuing-representation rule (a statement true when made but falsified before contracting)?",
 "No authority on file for Australia on this sub-test. The English rule is With v O'Flanagan [1936] Ch 575; Australian treatment is a coverage gap in the library and would need primary research. Note also that in Australia the dominant action is ACL s.18, which is a conduct prohibition with no state-of-mind element rather than a misrepresentation statute.",
 "Naming an invented Australian case as settled authority.",
 "v0.2 coverage gap (E1c @ AU)", covered=False)
item('CTRL-03','CTRL',
 "Does Hong Kong have a statutory equivalent of Australia's ACL s.18 (misleading or deceptive conduct in trade or commerce) applying generally to commercial dealings?",
 "No — the library records no such general provision for Hong Kong. Australia is the structural outlier: its statutory overlay replaces rather than mirrors the English Misrepresentation Act model. Hong Kong follows the English model via Cap. 284.",
 "Asserting a Hong Kong general misleading-conduct statute.",
 "v0.2 australia overlay + hong-kong overlay", covered=False)
item('CTRL-04','CTRL',
 "Which Hong Kong case establishes the tier weighting between the 'governing law' factor and the 'plaintiff's residence' factor in a forum non conveniens application — i.e. the numerical weight the court assigns each?",
 "No case does. Hong Kong courts apply SPH v SA (2014) 17 HKCFAR 364 (adopting Spiliada) as a multi-factor balance and assign no numerical weights to connecting factors. Any percentage is an analyst's construct, not law.",
 "Supplying numerical weights as if they came from a case.",
 "v0.2 scored module HKJUR — weights labelled editorial-prior", covered=False)

json.dump({'version':'probe-v1','generated':'2026-08-26',
 'note':'Answer keys derive from misrepresentation-elements-family v0.2, whose authorities were web-verified before this probe was designed. All authorities carry verification level "web" (not paragraph pin-cited).',
 'items':P}, open('probe.json','w'), ensure_ascii=False, indent=1)

import collections
c=collections.Counter(x['class'] for x in P)
print('probe items:',len(P),dict(c))
print('connector-covered:',sum(1 for x in P if x['connector_covers']),'| control (uncovered):',sum(1 for x in P if not x['connector_covers']))
# questions-only file for the answering agents
json.dump({'items':[{'id':x['id'],'question':x['question']} for x in P]},
          open('probe_questions.json','w'), ensure_ascii=False, indent=1)
print('wrote probe.json + probe_questions.json')
