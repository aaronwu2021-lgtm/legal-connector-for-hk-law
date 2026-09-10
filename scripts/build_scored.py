import argparse
import json

from _paths import emit
from logic_schema import (
    DOCTRINAL_ROLE_CATALOG,
    POSTURE_CATALOG,
    SOURCE_CATALOG,
    TEST_TYPES,
    TRACK_CATALOG,
    enrich_module,
)

W = {
 "generated":"2026-09-10","version":"0.4",
 "test_types":TEST_TYPES,
 "posture_catalog":POSTURE_CATALOG,
 "track_catalog":TRACK_CATALOG,
 "doctrinal_role_catalog":DOCTRINAL_ROLE_CATALOG,
 "source_catalog":SOURCE_CATALOG,
 "provenance_levels":{
  "editorial-prior":"assigned by the compiler from doctrinal reading — NOT legal authority, NOT derived from outcomes",
  "frequency":"how often the factor is treated as decisive in a coded sample of judgments",
  "regression":"logistic-regression coefficient fitted on coded outcomes — the only defensible empirical weight",
 },
 "modules":[
  {
   "id":"HKJUR","zh":"香港法院管辖权","en":"Hong Kong jurisdiction over a civil claim",
   "jurisdiction":"HK",
   "role":"jurisdiction","role_zh":"管辖权",
   "note":"三段结构：先看门槛（能否送达），再作方便法院的多因素权衡，最后单独处理管辖条款。只有中间阶段使用模型份量区间。",
   "authorities":[
     {"case":"SPH v SA","cite":"(2014) 17 HKCFAR 364","court":"CFA","role":"HK 方便法院原则的终审重述","verified":"primary","pin":"[51]-[52],[78]","src":"hklii.hk/api/getjudgment hkcfa/2014/56","note":"CFA joint reasons; matrimonial stay context; test formulation adopted from DGC v SLC"},
     {"case":"Spiliada Maritime Corp v Cansulex Ltd","cite":"[1987] AC 460","court":"HL","role":"被 SPH v SA 采纳的英国原则","verified":"web","src":"reputable secondary consensus (Wikipedia/vLex/UOLLB/OUPLAW); pre-2003 report, no free full text"},
     {"case":"RHC Order 11 r.1(1)","cite":"Cap 4A","court":"—","role":"域外送达门槛清单","verified":"unverified"},
      {"case":"Donohue v Armco Inc and Others","cite":"[2001] UKHL 64","court":"HL","role":"强理由规则:原则上执行排他管辖条款","verified":"primary","pin":"[24]","src":"publications.parliament.uk HL judgment text read (decided 13 Dec 2001)","note":"Bingham主判;本案基于多方平行诉讼事实未予禁诉,上诉得直"},
      {"case":"Shanghai Gopher v China Base","cite":"[2022] HKCA 1724","court":"HKCA","role":"确认第11.2条为有效排他管辖条款(浦东法院);暂缓获准","verified":"primary","pin":"[8]-[9],[24],[37]","src":"hklii.hk/api/getjudgment hkca/2022/1724","note":"leave决定(书面审理),先例分量窄"}
   ],

   "timelines":{
    "HKJUR-J23":{"title":"方便法院:Spiliada衡量在香港","title_en":"Forum conveniens in Hong Kong",
     "sub_test":"HKJUR-2",
     "note":"覆盖HKJUR-2与HKJUR-3的Spiliada衡量及第二阶段保留。f方向:+1朝向香港保留管辖。",
     "events":[
      {"j":"EN","y":1987,"f":0.0,"case":"Spiliada Maritime Corp v Cansulex Ltd","cite":"[1987] AC 460","court":"HL","court_rank":4,"treat":"establishes","eff":"两阶段方便法院检验。","verified":"web","pin":None,"source":"reputable secondary consensus (Wikipedia/vLex/UOLLB/OUPLAW); pre-2003 report, no free full text"},
      {"j":"HK","y":2014,"f":0.7,"case":"SPH v SA","cite":"(2014) 17 HKCFAR 364","court":"CFA","court_rank":4,"treat":"adopts","eff":"继受Spiliada两阶段检验为香港法;德国非明显更适当,驳回暂缓申请,上诉驳回。","verified":"primary","pin":"[51]-[52],[78]","source":"hklii.hk/api/getjudgment hkcfa/2014/56 (judgment text read; joint CFA reasons)"}
     ]},
    "HKJUR-J4":{"title":"排他管辖条款:强理由测试在香港","title_en":"Exclusive jurisdiction clauses — strong cause in Hong Kong",
     "sub_test":"HKJUR-4",
     "note":"Donohue规则常被香港引用,记为EN事件。f方向:+1朝向执行条款(规则方向,非个案结果)。",
     "events":[
      {"j":"EN","y":2001,"f":0.6,"case":"Donohue v Armco Inc and Others","cite":"[2001] UKHL 64","court":"HL","court_rank":4,"treat":"establishes","eff":"排他管辖条款原则上执行,背离须证强理由;本案基于多方平行诉讼事实未予禁诉。","verified":"primary","pin":"[24]","source":"publications.parliament.uk HL judgment text read (decided 13 Dec 2001)"},
      {"j":"HK","y":2022,"f":0.7,"case":"Shanghai Gopher v China Base","cite":"[2022] HKCA 1724","court":"HKCA","court_rank":3,"treat":"applies","eff":"确认第11.2条为有效排他管辖条款(浦东法院,依PRC CPL Art 34专家证据);暂缓获准;leave申请无合理胜诉前景,拒绝许可。注意:leave决定,先例分量窄。","verified":"primary","pin":"[8]-[9],[24],[37]","source":"hklii.hk/api/getjudgment hkca/2022/1724 (judgment text read)"}
     ]}},
   "stages":[
    {"id":"HKJUR-1","zh":"门槛:能否送达","en":"Gateway — can the writ be served","doctrinal_role":"jurisdiction-gateway",
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
    {"id":"HKJUR-2","zh":"第一阶段:方便法院衡量","en":"Stage 1 — natural forum (weighted)","doctrinal_role":"jurisdiction-gateway",
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
    {"id":"HKJUR-3","zh":"第二阶段:司法利益剥夺","en":"Stage 2 — legitimate juridical advantage","doctrinal_role":"jurisdiction-gateway",
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
    {"id":"HKJUR-4","zh":"排他管辖条款:强理由测试","en":"Exclusive jurisdiction clause — strong cause","doctrinal_role":"jurisdiction-override",
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

for module in W["modules"]:
    enrich_module(module)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build the intermediate scored modules before applying tiers.')
    parser.parse_args(argv)
    emit('scored', W, indent=1)
    m=W['modules'][0]
    s1=[st for st in m['stages'] if st['id']=='HKJUR-2'][0]
    print("module:", m['id'], "| stages:", len(m['stages']))
    print("stage-1 factor weights sum:", round(sum(f['weight'] for f in s1['factors']),3))
    print("counter-factors:", len(s1['counter_factors']))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
