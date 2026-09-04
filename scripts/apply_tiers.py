# -*- coding: utf-8 -*-
"""Assign a doctrinal weight TIER to every balancing factor.
Tiers come from how courts speak about relative importance, not from arithmetic.
Each tier maps to a percentage BAND, never a point estimate."""
import json

from _paths import emit, load

TIERS = {
 "decisive":    {"lo":None,"hi":None,"zh":"决定性","en":"Dispositive","note":"不是权重——单独成立即定案"},
 "heavy":       {"lo":0.20,"hi":0.30,"zh":"重","en":"Heavy","note":"判词常以此为核心理由"},
 "substantial": {"lo":0.13,"hi":0.20,"zh":"较重","en":"Substantial","note":"经常被明确论及并影响结论"},
 "moderate":    {"lo":0.08,"hi":0.13,"zh":"中","en":"Moderate","note":"通常被列举,少见单独决定"},
 "light":       {"lo":0.04,"hi":0.08,"zh":"轻","en":"Light","note":"提及但很少改变结论"},
 "marginal":    {"lo":0.01,"hi":0.04,"zh":"微","en":"Marginal","note":"边缘因素"},
}

T = {
 # HKJUR — forum conveniens
 "F-governing-law":"substantial","F-witnesses":"substantial","F-defendant-connection":"substantial",
 "F-tort-place":"moderate","F-performance":"moderate","F-related-proceedings":"moderate",
 "F-plaintiff-connection":"light","F-language":"light","F-assets":"light",
 "C-alt-forum":"heavy","C-foreign-law":"substantial","C-foreign-witnesses":"substantial",
 "A-limitation":"heavy","A-no-substantial-justice":"heavy","A-damages":"moderate",
 "A-procedure":"moderate","A-delay":"light",
 # CONTRACT
 "CT-express-label":"heavy","CT-deprives-benefit":"heavy","CT-time-essence":"substantial","CT-statutory":"heavy",
 "CT-natural":"heavy","CT-contemplation":"heavy","CT-assumption":"substantial","CT-market-usage":"moderate",
 # Proprietary estoppel
 "PE-clarity":"substantial","PE-detriment-scale":"heavy","PE-duration":"moderate",
 "PE-conduct":"moderate","PE-benefit-received":"moderate",
 # CICT quantification
 "CICT-contributions":"heavy","CICT-mortgage":"substantial","CICT-outgoings":"moderate",
 "CICT-improvements":"moderate","CICT-discussions":"substantial","CICT-children":"moderate",
 "CICT-separate-finances":"substantial",
 # Resulting trust rebuttal
 "RT-evidence-gift":"heavy","RT-evidence-loan":"substantial","RT-contemporaneous":"substantial",
 "RT-subsequent-conduct":"moderate",
 # Adverse possession — factual possession
 "AP-enclosure":"heavy","AP-exclusion":"heavy","AP-cultivation":"substantial",
 "AP-land-nature":"substantial","AP-maintenance":"moderate",
 # Nuisance
 "NU-locality":"heavy","NU-severity":"heavy","NU-duration":"substantial","NU-malice":"substantial",
 "NU-utility":"moderate","NU-timing":"moderate","NU-sensitivity":"substantial","NU-common-use":"heavy",
 # Illegality — Patel trio, deliberately co-equal
 "IL-purpose":"heavy","IL-other-policy":"heavy","IL-proportionality":"heavy",
 # Undue influence rebuttal
 "UI-independent-advice":"heavy","UI-advice-quality":"heavy","UI-full-disclosure":"substantial","UI-free-will":"moderate",
 # Lease vs licence — substance over form
 "LS-sham-terms":"heavy","LS-conduct":"heavy","LS-provider-services":"substantial","LS-label":"light",
 # Arbitrator challenge
 "AC-nondisclosure":"heavy","AC-financial":"heavy","AC-multiple-appointments":"substantial",
 "AC-relationship":"substantial","AC-prior-views":"moderate","AC-market-practice":"light",
 # CECO reasonableness
 "CE-bargaining":"heavy","CE-knowledge":"substantial","CE-sophistication":"substantial",
 "CE-inducement":"moderate","CE-practicable":"moderate","CE-bespoke":"light",
}

NOTES = {
 "F-plaintiff-connection":"⚠ 直觉常高估。原告不能仅凭居港创设管辖;被告的联系重得多。",
 "LS-label":"⚠ 文件自称许可几乎不影响定性——Street v Mountford 明确实质重于形式。",
 "NU-malice":"恶意在场时可把本属合理的使用变为不合理,故档位高于其表面重要性。",
 "IL-purpose":"Patel v Mirza 将三项考量并列表述,故三者同档。",
 "AC-market-practice":"该领域惯常做法通常是减弱因素,而非加强。",
}

def band(tier):
    t=TIERS[tier]; return t["lo"], t["hi"]

def apply(key):
    d=load(key)
    mods = d["modules"]
    n=0; miss=[]
    for m in mods:
        for st in m["stages"]:
            if st.get("test_type")!="balancing": continue
            for f in st.get("factors",[])+st.get("counter_factors",[]):
                tier = T.get(f["id"])
                if not tier:
                    miss.append(f["id"]); continue
                lo,hi = band(tier)
                neg = (f.get("weight") or 0) < 0 or f in st.get("counter_factors",[])
                f["tier"]=tier
                f["weight_low"]  = -hi if neg else lo
                f["weight_high"] = -lo if neg else hi
                f["weight"]      = round((f["weight_low"]+f["weight_high"])/2, 3)
                f["weight_source"]="doctrinal-tier"
                f.pop("weight_status",None)
                if f["id"] in NOTES: f["note"]=NOTES[f["id"]]
                n+=1
            st["weight_source"]="doctrinal-tier"
            st["weight_note"]="档位由判词对相对份量的表述归纳,区间非点估计;经验权重须由判决结果回归得出。"
    d["tiers"]=TIERS
    emit(key, d, indent=1)
    return n, miss

a,ma = apply('scored')
b,mb = apply('registry')
print(f"tiered factors: scored={a} registry={b} total={a+b}")
if ma+mb: print("NO TIER (check):", sorted(set(ma+mb)))
