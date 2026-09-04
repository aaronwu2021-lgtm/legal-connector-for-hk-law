import json

from _paths import emit

W = {
 "generated":"2026-08-25","version":"0.1",
 "test_types":{
  "conjunctive":{"zh":"合取要件","en":"All elements must be satisfied",
    "scoring":"none — a weight is meaningless here; 80% of falsity does not prove falsity",
    "output":"gap list","examples":["misrepresentation E1–E5","deceit"]},
  "disjunctive-gateway":{"zh":"择一门槛","en":"At least one item from a closed list",
    "scoring":"count ≥ 1; strength of the strongest limb matters for discretion",
    "output":"which gateway(s) are open","examples":["RHC O.11 r.1(1) service-out gateways","NY Convention Art V grounds"]},
  "balancing":{"zh":"权重衡量","en":"Multi-factor balance, no single factor dispositive",
    "scoring":"weighted sum of present factors, net of counter-factors",
    "output":"score + swing factors + evidence still missing",
    "examples":["forum non conveniens","lease vs licence","veil piercing","CECO s.3(1) reasonableness"]},
  "threshold-discretion":{"zh":"门槛加裁量","en":"Threshold then discretionary override",
    "scoring":"gate, then a separate discretionary limb",
    "output":"gate result + discretion result","examples":["exclusive jurisdiction clause — strong cause"]},
 },
 "provenance_levels":{
  "editorial-prior":"assigned by the compiler from doctrinal reading — NOT legal authority, NOT derived from outcomes",
  "frequency":"how often the factor is treated as decisive in a coded sample of judgments",
  "regression":"logistic-regression coefficient fitted on coded outcomes — the only defensible empirical weight",
 },
 "modules":[
  {
   "id":"HKJUR","zh":"香港法院管辖权","en":"Hong Kong jurisdiction over a civil claim",
   "jurisdiction":"HK",
   "note":"三段结构:先看门槛(能否送达),再看方便法院衡量,最后管辖条款单独一条。只有中间那段是权重制。",
   "authorities":[
     {"case":"SPH v SA","cite":"(2014) 17 HKCFAR 364","court":"CFA","role":"HK 方便法院原则的终审重述","verified":"web"},
     {"case":"Spiliada Maritime Corp v Cansulex Ltd","cite":"[1987] AC 460","court":"HL","role":"被 SPH v SA 采纳的英国原则","verified":"web"},
     {"case":"RHC Order 11 r.1(1)","cite":"Cap 4A","court":"—","role":"域外送达门槛清单","verified":"unverified"}
   ],
   "stages":[
    {"id":"HKJUR-1","zh":"门槛:能否送达","en":"Gateway — can the writ be served",
     "test_type":"disjunctive-gateway","rule":"域内送达当然有管辖;域外送达须落入 O.11 r.1(1) 任一项并获法院许可",
     "factors":[
      {"id":"G-presence","zh":"被告在港(居住/营业/送达时在港)","en":"Defendant present or carrying on business in HK","dispositive":True},
      {"id":"G-submission","zh":"被告应诉或合意接受管辖","en":"Submission to the jurisdiction","dispositive":True},
      {"id":"G-contract-made","zh":"合同在香港订立","en":"Contract made in HK"},
      {"id":"G-contract-law","zh":"合同准据法为香港法","en":"Contract governed by HK law"},
      {"id":"G-breach","zh":"违约行为发生在香港","en":"Breach committed in HK"},
      {"id":"G-tort","zh":"侵权行为地或损害发生地在香港","en":"Tort committed in / damage sustained in HK"},
      {"id":"G-property","zh":"标的财产位于香港","en":"Property situated in HK"},
      {"id":"G-necessary-party","zh":"被告为已妥为送达之诉的必要或适当当事人","en":"Necessary or proper party"},
      {"id":"G-injunction","zh":"寻求在港作为或不作为的强制令","en":"Injunction as to acts in HK"}
     ]},
    {"id":"HKJUR-2","zh":"第一阶段:方便法院衡量","en":"Stage 1 — natural forum (weighted)",
     "test_type":"balancing",
     "rule":"申请方须证明:香港并非自然或适当法院(即与诉讼有最真实且实质联系者),且存在另一个明显或显著更适当的可用法院。",
     "weight_note":"以下权重为编者先验,法院从不给数字。待以判决结果回归校准后替换。",
     "weight_source":"editorial-prior",
     "factors":[
      {"id":"F-governing-law","zh":"准据法为香港法","en":"HK law governs the contract","weight":0.18,
       "evidence":"合同管辖法条款;若无,以最密切联系判断","note":"重量级:审理外国法需专家证据,是强力的向港因素"},
      {"id":"F-witnesses","zh":"证人与文件在香港","en":"Witnesses and documents located in HK","weight":0.16,
       "evidence":"证人名单及居住地;文件所在地与语言","note":"实务上常是决定性的一项"},
      {"id":"F-defendant-connection","zh":"被告在港(住所/营业地)","en":"Defendant resident or trading in HK","weight":0.15,
       "evidence":"公司注册处纪录;营业地址"},
      {"id":"F-tort-place","zh":"侵权行为地/损害地在香港","en":"Place of the tort or damage is HK","weight":0.13,
       "evidence":"损害发生地;行为实施地"},
      {"id":"F-performance","zh":"履行地在香港","en":"Place of performance is HK","weight":0.12,
       "evidence":"交付地、付款地、服务提供地"},
      {"id":"F-related-proceedings","zh":"香港已有关联程序(避免程序多重)","en":"Related HK proceedings / multiplicity risk","weight":0.09,
       "evidence":"平行诉讼编号;当事人重叠度"},
      {"id":"F-plaintiff-connection","zh":"原告在香港","en":"Plaintiff resident in HK","weight":0.06,
       "evidence":"住所证明",
       "note":"⚠ 直觉常高估这一项。原告不能仅凭自身居港制造管辖;被告的联系远重于原告。"},
      {"id":"F-language","zh":"证据语言为中文","en":"Evidence in Chinese","weight":0.06,
       "evidence":"文件语言;是否需翻译"},
      {"id":"F-assets","zh":"资产在香港(执行便利)","en":"Assets in HK","weight":0.05,
       "evidence":"资产清单","note":"与执行相关,对自然法院判断本身权重低"}
     ],
     "counter_factors":[
      {"id":"C-alt-forum","zh":"存在明显更适当的替代法院","en":"A clearly more appropriate alternative forum exists","weight":-0.30,
       "note":"这是申请方必须证明的核心命题,不是普通因素"},
      {"id":"C-foreign-law","zh":"准据法为外国法","en":"Foreign governing law","weight":-0.18},
      {"id":"C-foreign-witnesses","zh":"主要证人在境外","en":"Key witnesses abroad","weight":-0.16}
     ]},
    {"id":"HKJUR-3","zh":"第二阶段:司法利益剥夺","en":"Stage 2 — legitimate juridical advantage",
     "test_type":"balancing",
     "rule":"即使第一阶段指向他地,若答辩方证明在他地审理会被剥夺正当的个人或司法利益,法院仍可保留管辖;但若他地能实现实质正义,利益丧失未必致命。",
     "weight_source":"editorial-prior",
     "factors":[
      {"id":"A-limitation","zh":"他地时效已过","en":"Time-barred in the alternative forum","weight":0.30},
      {"id":"A-no-substantial-justice","zh":"他地无法实现实质正义","en":"Substantial justice unavailable abroad","weight":0.30},
      {"id":"A-damages","zh":"他地可获赔偿显著较低","en":"Materially lower recovery abroad","weight":0.15},
      {"id":"A-procedure","zh":"他地无对应程序(如披露)","en":"No equivalent procedure (e.g. discovery)","weight":0.15},
      {"id":"A-delay","zh":"他地程序严重迟延","en":"Serious delay abroad","weight":0.10}
     ]},
    {"id":"HKJUR-4","zh":"排他管辖条款:强理由测试","en":"Exclusive jurisdiction clause — strong cause",
     "test_type":"threshold-discretion",
     "rule":"若合同订有排他管辖条款,法院原则上执行该条款;背离者须证明强理由(strong cause)。此段覆盖前两段的衡量。",
     "factors":[
      {"id":"E-ejc-present","zh":"存在排他管辖条款","en":"Exclusive jurisdiction clause present","gate":True},
      {"id":"E-strong-cause","zh":"存在背离条款的强理由","en":"Strong cause to depart shown","override":True}
     ]}
   ]
  }
 ]
}
emit('scored', W, indent=1)
m=W['modules'][0]
s1=[st for st in m['stages'] if st['id']=='HKJUR-2'][0]
print("module:", m['id'], "| stages:", len(m['stages']))
print("stage-1 factor weights sum:", round(sum(f['weight'] for f in s1['factors']),3))
print("counter-factors:", len(s1['counter_factors']))
