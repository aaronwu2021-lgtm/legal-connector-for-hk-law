# -*- coding: utf-8 -*-
import argparse
import json

from _paths import emit
from logic_schema import (
    POSTURE_CATALOG,
    SOURCE_CATALOG,
    TEST_TYPES,
    TRACK_CATALOG,
    enrich_module,
)

E = "editorial-prior"; U = "unassigned"
def F(i,zh,en,w=None,ev=None,note=None,**meta):
    d={"id":i,"zh":zh,"en":en,"weight":w,"evidence":ev}
    if note: d["note"]=note
    if w is None: d["weight_status"]=U
    d.update(meta)
    return d
def S(i,zh,en,tt,rule,factors,ws=None,cf=None,note=None,doctrinal_role=None,applies_when=None,jurisdiction_rules=None):
    # Absence of a weight outside a balancing test means "not applicable",
    # never "awaiting assignment". Keep weight fields out of those records.
    if tt != "balancing":
        for factor in factors + (cf or []):
            for key in ("weight", "weight_status", "weight_low", "weight_high", "weight_source", "tier"):
                factor.pop(key, None)
    d={"id":i,"zh":zh,"en":en,"test_type":tt,"rule":rule,"factors":factors}
    if ws: d["weight_source"]=ws
    if cf: d["counter_factors"]=cf
    if note: d["weight_note"]=note
    if doctrinal_role: d["doctrinal_role"]=doctrinal_role
    if applies_when: d["applies_when"]=applies_when
    if jurisdiction_rules: d["jurisdiction_rules"]=jurisdiction_rules
    return d
def A(c,cite,court,role,v="unverified",pin=None,src=None):
 d={"case":c,"cite":cite,"court":court,"role":role,"verified":v}
 if pin: d["pin"]=pin
 if src: d["src"]=src
 return d

M=[]

M.append({"id":"CONTRACT","area":"合同 Contract","zh":"违约","en":"Breach of contract","jurisdiction":"EN/HK/SG","role":"spear","role_zh":"矛",
 "top_type":"conjunctive","corpus_hits":35,
 "note":"顶层是合取要件;真正需要权衡的在三个嵌套子测试里——条款分类、是否根本违约、损害远隔性。",
 "authorities":[A("Hongkong Fir Shipping v Kawasaki Kisen Kaisha","[1962] 2 QB 26","EWCA","无名条款分类"),
   A("Hadley v Baxendale","(1854) 9 Ex 341","Exch","远隔性两支规则"),
   A("Transfield Shipping v Mercator (The Achilleas)","[2008] UKHL 48","HL","远隔性的责任承担进路")],
 "stages":[
  S("CT-1","要件","Elements","conjunctive","合同成立;存在该条款;违反;因果;损失。五项皆须具备。",
    [F("CT-contract","合同有效成立","Valid contract"),F("CT-term","存在被违反的条款","Term relied on exists"),
     F("CT-breach","违反该条款","Breach"),F("CT-causation","因果关系","Causation"),F("CT-loss","损失","Loss")]),
  S("CT-2","条款分类","Condition / warranty / innominate","balancing",
    "条款是条件、保证还是无名条款?无名条款看违约后果是否剥夺无辜方合同全部利益。",
    [F("CT-express-label","合同明示定性为条件","Expressly labelled a condition",None,"条款文本"),
     F("CT-deprives-benefit","违约后果剥夺全部合同利益","Deprives of substantially the whole benefit",None,"实际后果证据"),
     F("CT-time-essence","时间为要素","Time of the essence",None,"条款与商业背景"),
     F("CT-statutory","成文法定性","Statutory classification",None,"货品售卖条例等")],ws=None,
    note="权重待校准:此处的判例结果编码工作量最小,建议作为回归试点。"),
  S("CT-3","损害远隔性","Remoteness","balancing",
    "第一支:通常过程中自然发生;第二支:订约时双方合理预见。Achilleas 加入责任承担考量。",
    [F("CT-natural","通常过程中自然发生","Arises naturally"),
     F("CT-contemplation","订约时在双方预见范围内","In contemplation at contracting"),
     F("CT-assumption","该类型损失属被告承担的责任范围","Defendant assumed responsibility for this type"),
     F("CT-market-usage","行业惯例反向指示","Market usage points the other way")])]})

M.append({"id":"PE","area":"衡平 Equity","zh":"财产禁反言","en":"Proprietary estoppel","jurisdiction":"EN/HK/SG","role":"shield","role_zh":"盾","role_note":"禁反言多以抗辩姿态出现；财产禁反言在英格兰亦可独立成诉(Guest/Thorner/Gillett)，“shield not sword”原指promissory estoppel。按典型诉答姿态归盾。",
 "top_type":"conjunctive+overlay","corpus_hits":104,
 "note":"三要件合取,但三者不是分格评估——法院整体看是否不合情理;救济阶段是独立裁量。",
 "authorities":[A("Thorner v Major","[2009] UKHL 18","HL","保证须足够明确"),
   A("Gillett v Holt","[2001] Ch 210","EWCA","三要件整体衡量,不分格"),
   A("Guest v Guest","[2022] UKSC 27","UKSC","救济目的与量定")],
 "stages":[
  S("PE-1","三要件","Assurance / reliance / detriment","conjunctive",
    "保证、信赖、损害三者皆须具备,但相互交织,整体判断。",
    [F("PE-assurance","足够明确的保证","Assurance clear enough"),
     F("PE-reliance","基于该保证的信赖","Reliance on the assurance"),
     F("PE-detriment","因信赖而受损","Detriment suffered")]),
  S("PE-2","不合情理性(整体)","Unconscionability — held in the round","balancing",
    "三要件不分格评分,法院整体判断坚持严格权利是否不合情理。",
    [F("PE-clarity","保证的明确程度","Clarity of the assurance"),
     F("PE-detriment-scale","损害的规模与不可逆性","Scale and irreversibility of detriment"),
     F("PE-duration","信赖持续时间","Duration of reliance"),
     F("PE-conduct","被承诺方自身行为","Promisee's own conduct"),
     F("PE-benefit-received","期间已获利益","Counter-benefits received")]),
  S("PE-3","救济量定","Satisfying the equity","threshold-discretion",
    "Guest v Guest:先以实现期待为出发点,再按比例与损害调整;法院裁量。",
    [F("PE-expectation","以期待为出发点","Expectation as starting point",None,None),
     F("PE-proportionality","比例调整","Proportionality adjustment")])]})

M.append({"id":"CICT","area":"衡平 Equity","zh":"共同意图推定信托","en":"Common intention constructive trust","jurisdiction":"EN/HK/SG","role":"spear","role_zh":"矛",
 "top_type":"conjunctive+balancing","corpus_hits":134,
 "note":"成立采用合取要件；份额量化采用多因素权衡（整体交易过程）。语料里出现频次第四。",
 "authorities":[A("Stack v Dowden","[2007] UKHL 17","HL","共有名义下的推定与整体交易过程",),
   A("Jones v Kernott","[2011] UKSC 53","UKSC","意图变更与推定意图"),
   A("Lloyds Bank v Rosset","[1991] 1 AC 107","HL","单一名义下的成立门槛")],
 "stages":[
  S("CICT-1","成立","Establishing the trust","conjunctive",
    "共同意图(明示或推断)+ 损害性信赖。共有名义下先推定衡平共有。",
    [F("CICT-intention","共同意图(明示或由行为推断)","Common intention"),
     F("CICT-reliance","损害性信赖","Detrimental reliance")]),
  S("CICT-2","份额量化","Quantification","balancing",
    "无明示协议时按整体交易过程推断;不能确定则以公平为准。",
    [F("CICT-contributions","直接出资比例","Direct financial contributions"),
     F("CICT-mortgage","按揭供款","Mortgage payments"),
     F("CICT-outgoings","日常开支分担","Household outgoings"),
     F("CICT-improvements","对物业的改良","Improvements to the property"),
     F("CICT-discussions","双方言谈与安排","Discussions and arrangements"),
     F("CICT-children","子女照料与家庭分工","Childcare and division of labour"),
     F("CICT-separate-finances","财务完全分离(指向非均分)","Rigidly separate finances")])]})

M.append({"id":"RT","area":"衡平 Equity","zh":"归复信托与预付推定","en":"Resulting trust / presumption of advancement","jurisdiction":"EN/HK/SG","role":"spear","role_zh":"矛",
 "top_type":"presumption-rebuttal","corpus_hits":55,
 "note":"这是第五种结构:推定加反驳,举证责任在反驳方。不是合取也不是权衡。",
 "authorities":[A("Westdeutsche Landesbank v Islington LBC","[1996] AC 669","HL","归复信托的分类"),
   A("Marr v Collie","[2017] UKPC 17","UKPC","商业与家庭语境的交界")],
 "stages":[
  S("RT-1","推定触发","Presumption arises","disjunctive-gateway",
    "出资购买他人名下财产,或无偿转让,推定归复信托——除非预付推定适用。",
    [F("RT-purchase-money","以自身资金购入他人名下","Purchase money in another's name",None,None),
     F("RT-voluntary","无偿转让","Voluntary transfer"),
     F("RT-advancement","关系触发预付推定(父对子/夫对妻)","Advancement relationship")]),
  S("RT-2","反驳","Rebuttal","balancing",
    "以证据反驳推定;举证责任在主张推定不适用的一方。",
    [F("RT-evidence-gift","赠与意思的证据","Evidence of intention to gift"),
     F("RT-evidence-loan","借贷意思的证据","Evidence of loan"),
     F("RT-contemporaneous","同期文件","Contemporaneous documents"),
     F("RT-subsequent-conduct","嗣后行为","Subsequent conduct")])]})

M.append({"id":"AP","area":"土地 Land","zh":"逆权占有","en":"Adverse possession","jurisdiction":"HK/EN","role":"spear","role_zh":"矛",
 "top_type":"conjunctive","corpus_hits":81,
 "note":"合取要件,不宜赋权重;香港仍适用时效条例的旧制,与英国 2002 年注册制改革分道。",
 "authorities":[A("JA Pye (Oxford) v Graham","[2002] UKHL 30","HL","事实占有与占有意图"),
   A("Powell v McFarlane","(1977) 38 P & CR 452","Ch","占有意图的经典表述"),
   A("Limitation Ordinance","Cap 347","—","香港时效期间")],
 "stages":[
  S("AP-1","要件","Elements","conjunctive",
    "事实占有 + 占有意图 + 未经同意 + 时效期间届满。四项皆须。",
    [F("AP-factual","事实占有(排他性实际控制)","Factual possession"),
     F("AP-intention","占有意图","Intention to possess"),
     F("AP-without-consent","未经纸面业主同意","Without the owner's consent"),
     F("AP-limitation","时效期间届满","Limitation period expired")]),
  S("AP-2","事实占有的判断因素","What counts as factual possession","balancing",
    "围封、耕作、维护、排除他人等,视土地性质而定。",
    [F("AP-enclosure","围封","Enclosure"),F("AP-cultivation","耕作或使用","Cultivation or use"),
     F("AP-maintenance","维护修缮","Maintenance"),F("AP-exclusion","排除他人","Excluding others"),
     F("AP-land-nature","土地性质与通常用法","Nature of the land")])]})

M.append({"id":"NUIS","area":"侵权 Tort","zh":"私人妨害","en":"Private nuisance","jurisdiction":"HK/EN","role":"spear","role_zh":"矛",
 "top_type":"conjunctive","corpus_hits":11,
 "note":"私人妨害本身是诉因；必要要件、内部法律标准、抗辩与救济均置于同一诉因结构。任何法域均不以编者数值权重代替法律判断。EN 分支以 Fearn/Davies 为现行结构；HK 须分别适用 Ng Hoi Sze 的土地权益门槛及 Century Way 的情境评估，Fearn 在香港仅具说服力，不能自动覆盖香港上诉法院规则。三类路径的香港锚点 Cheng Lai Yin 属 CFI。HK 的预防性 quia timet 分支及 SG 整体在本版本不作结论，仍是覆盖缺口。",
 "authorities":[
   A("Fearn v Board of Trustees of the Tate Gallery","[2023] UKSC 4","UKSC","土地权益、实质干扰、普通使用、互惠边界及责任与救济分离","primary","[9]-[10],[18]-[24],[27]-[38],[47],[54]-[55],[114]-[122],[126]-[132]","https://caselaw.nationalarchives.gov.uk/uksc/2023/4"),
   A("Davies v Bridgend County Borough Council","[2024] UKSC 15","UKSC","损害、因果关系及自然危险的过错要求","primary","[68]-[71],[76]-[77]","https://supremecourt.uk/cases/judgments/uksc-2023-0028"),
   A("Ng Hoi Sze v Yuen Sha Sha and Another","[1999] 3 HKLRD 890","HKCA","香港土地权益及排他占有门槛","primary","[14]-[20]","https://legalref.judiciary.hk/doc/judg/html/vetted/other/en/1999/CACV000094_1999.htm"),
   A("Century Way Investment Ltd v Willbert Ltd and Another","[2019] HKCA 739","HKCA","香港舒适便利妨害的情境评估、可预见风险及预防措施","primary","[4.2]-[4.5],[5.9]-[5.16]","https://legalref.judiciary.hk/doc/judg/html/vetted/other/en/2017/CACV000239_2017.htm"),
   A("Leung Tsang Hung and Another v Incorporated Owners of Kwok Wing House","(2007) 10 HKCFAR 480; [2007] 4 HKLRD 654","CFA","公害案件中确认私人妨害是保护财产权的不同诉因；不作为私人妨害责任要件权威","primary","[13]","https://legalref.judiciary.hk/doc/judg/html/vetted/other/en/2007/FACV000004_2007.htm"),
   A("Network Rail Infrastructure Ltd v Williams and Waistell","[2018] EWCA Civ 1514","EWCA","英格兰预防性 quia timet 救济及迫近危害门槛","primary","[70]-[71]","https://www.judiciary.uk/wp-content/uploads/2018/07/network-rail-v-williams-judgment.pdf"),
   A("Cheng Lai Yin v Liu Yee Mui","[2022] HKCFI 940","CFI","香港三类妨害路径、舒适便利标准、归责与救济；属一审且当事人无争议的法律摘要","primary","[51],[54]","https://www.hklii.hk/en/cases/hkcfi/2022/940")],
 "stages":[
  S("NU-1","受保护的土地权益","Protected land interest","conjunctive",
    "原告须具有受法律保护的土地权益；所诉损害须是对该土地权利、用途或便利价值的干扰，而非独立的人身不适。",
    [F("NU-interest","原告对受影响土地享有足够的法律权益，通常包括排他占有权","Claimant has a sufficient legal interest, ordinarily a right to exclusive possession",None,"业权、租约、地役权或其他土地权益文件"),
     F("NU-land-harm","干扰针对土地权利、使用、享有或便利价值","Interference concerns rights in, use, enjoyment or amenity value of land",None,"土地用途及受影响权利证据")],
    doctrinal_role="claim-elements",jurisdiction_rules={
      "EN":"Fearn [9]-[10]：通常须有土地法律权益及排他占有权。",
      "HK":"Ng Hoi Sze [14]-[20]：采纳土地权益门槛；仅居住或普通许可而无排他占有不足。"}),
  S("NU-2","可诉干扰路径","Actionable interference route","disjunctive-gateway",
    "至少识别一项受承认的路径：侵占、土地物理损害，或对土地舒适便利使用与享有的过度干扰。路径是受保护利益的分类；造成干扰的具体方式并非封闭清单。",
    [F("NU-route-encroachment","侵占或越界进入土地","Encroachment onto the land",None,"边界、测量、迁移物或根系证据"),
     F("NU-route-physical","土地发生物理损害或实质性物质损伤","Physical damage or material injury to the land",None,"检验、照片、工程或估值证据"),
     F("NU-route-amenity","土地的舒适便利使用或享有受到过度干扰","Undue interference with amenity or enjoyment of land",None,"噪音、气味、烟尘、振动、观察或其他影响证据")],
    doctrinal_role="claim-elements"),
  S("NU-3","既有干扰或预防性威胁","Accrued interference or threatened nuisance","disjunctive-gateway",
    "既有请求须证明实际干扰或损害；尚未发生时，只能在适用法容许并达到 quia timet 门槛时请求预防性救济。EN 的通常门槛是有充分证据证明迫近的物理损伤或危害；HK 的预防性私人妨害分支在本版本仍属权威覆盖缺口。",
    [F("NU-accrued","已经发生实际干扰或可诉损害","Actual interference or actionable harm has occurred",None,"现场记录、同期投诉、证人证言、检验或损害记录"),
     F("NU-quia-timet","尚未发生，但有充分证据证明迫近且很可能发生的妨害，符合适用法的 quia timet 门槛","No interference has yet occurred, but evidence establishes an imminent and sufficiently likely nuisance under the applicable quia-timet standard",None,"工程或专家证据、既往事件、明确计划、时间表及发生概率")],
    doctrinal_role="claim-elements",jurisdiction_rules={
      "EN":"Network Rail v Williams [70]-[71]：适当案件可给予 quia timet 禁制令或替代赔偿；通常须证明迫近的物理损伤或危害。",
      "HK":"覆盖缺口：本版本尚无逐段核验的一手香港权威，不能由英格兰规则自动推定。"}),
  S("NU-4","舒适便利路径的法律标准","Amenity-route legal standard","conjunctive",
    "仅在 NU-route-amenity 路径适用。实质程度及普通人客观标准是必要检查；最终标准须按法域分支适用。EN 依 Fearn 的普通用途与互惠标准，拒绝开放式合理性权衡；HK 依 Century Way 评估全部相关情境。地点、强度、持续时间、频率、时段、可预见风险、预防措施、成本、资源及恶意只作为适用法律标准的事实，不换算为数值权重。",
    [F("NU-substantial","干扰达到真实、实质或重大的最低严重程度","Interference is real, substantial or material",None,"强度、持续时间、频率、发生时段及客观测量"),
     F("NU-objective-ordinary-use","以普通人标准评估原告土地的普通用途","Objective interference with ordinary use of the claimant's land",None,"同类土地通常用途及异常敏感性证据"),
     F("NU-jurisdiction-standard","已经适用正确法域的责任标准","The governing jurisdiction's liability standard has been applied",None,"EN：普通通常用途与互惠；HK：全部相关情境、风险、预防措施、成本与双方资源")],
    doctrinal_role="internal-test",applies_when={"stage_id":"NU-2","factor_ids":["NU-route-amenity"]},jurisdiction_rules={
      "EN":"Fearn [18]-[24],[27]-[38],[54]-[55]：不是开放式合理性权衡；问是否实质干扰原告土地普通用途，并适用被告普通通常且适当顾及邻地的互惠边界。",
      "HK":"Century Way [4.2]-[4.5],[5.9]-[5.16]：无绝对标准，评估全部情境，包括可预见风险、可用预防措施、成本及双方资源；该情境评估不是数值评分。"}),
  S("NU-5","归责、损害、因果与可预见性","Responsibility, damage, causation and foreseeability","conjunctive",
    "被告须对活动或状态负责。既有请求须证明可诉损害及因果关系；预防性请求须证明所威胁的妨害与被告应负责的活动或状态相连并达到适用门槛。相关种类的损害须可合理预见。主动制造妨害通常不以疏忽为必要；自然危险、第三人行为或继续妨害可能要求被告知情或应当知情并未采取合理措施。",
    [F("NU-responsibility","被告制造、授权、采纳、继续或控制导致干扰的活动或状态，并满足适用的过错要求","Defendant is responsible for the activity or state of affairs under the applicable basis of responsibility",None,"占有控制、授权、通知、知识及应对措施证据"),
     F("NU-actionable-harm","既有请求已证明可诉损害，或预防性请求已证明符合适用法的迫近危害门槛","Actionable harm is proved for an accrued claim, or the applicable imminent-harm threshold is proved for preventive relief",None,"土地损伤、便利价值、实际使用受损或迫近危害证据"),
     F("NU-causation","被告应负责的行为或状态事实上及法律上造成或威胁造成所诉损害","Factual and legal causation, including the causal source of any threatened harm",None,"时间线、来源追踪、专家及反事实证据"),
     F("NU-foreseeability","所发生种类的损害属于可合理预见范围","The relevant type of harm was reasonably foreseeable",None,"被告知识、既往事件、通知及行业资料")],
    doctrinal_role="claim-elements"),
  S("NU-6","抗辩","Defences","disjunctive-gateway",
    "被告须证明适用法承认的一项抗辩。迁来妨害、一般规划许可及活动具有公共利益本身不是责任抗辩。法定授权、时效取得的权利和同意的具体条件随法域而异。",
    [F("NU-defence-statutory","法定授权使妨害成为依法授权活动不可避免的后果","Statutory authority makes the nuisance an inevitable consequence of the authorised activity",None,"授权法例、法定权限及替代施工方式证据"),
     F("NU-defence-prescription","依适用法完成取得继续该干扰的时效权利","Prescriptive right acquired under the applicable law",None,"干扰成为可诉后的持续期间、公开性及权利行使记录"),
     F("NU-defence-consent","原告以有效同意、授权或契约容许该干扰","Valid consent, licence or covenant permits the interference",None,"契约、许可、协议范围及有效性")],
    doctrinal_role="defence"),
  S("NU-7","救济","Remedy","threshold-discretion",
    "先确定既有责任或预防性救济资格，再分别决定禁制令、损害赔偿或减除妨害费用。公共利益只在该门槛成立后的救济选择中考虑；不能因社会效用而免除既有责任并不给补偿。",
     [F("NU-remedy-threshold","既有私人妨害责任已经成立，或预防性救济门槛已经满足","Liability for accrued nuisance is established, or the threshold for preventive relief is satisfied",gate=True),
      F("NU-injunction","禁制令的范围与实际可行性","Scope and practical workability of an injunction",None,"持续或重复风险、可执行条款及替代减损措施",role="discretion"),
      F("NU-damages","损害赔偿或合理减除妨害费用是否足以救济","Adequacy of damages or reasonable abatement costs",None,"修复、减损、租值或价值损失证据",role="discretion"),
      F("NU-public-interest-remedy","公共利益对禁制令与赔偿选择的影响","Public interest as relevant to the choice between injunction and damages",None,"公共影响及维持活动的证据",role="discretion")],
    doctrinal_role="remedy")]})

M.append({"id":"ILLEG","area":"合同 Contract","zh":"违法性抗辩","en":"Illegality (Patel v Mirza)","jurisdiction":"EN/HK/SG","role":"shield","role_zh":"盾",
 "top_type":"balancing","corpus_hits":14,
 "note":"最高法院明确改为三项考量的权衡,是全法律里少数由判例本身指定为多因素权衡的测试。",
 "authorities":[A("Patel v Mirza","[2016] UKSC 42","UKSC","三项考量的权衡取代 Tinsley 依赖规则"),
   A("Tinsley v Milligan","[1994] 1 AC 340","HL","被 Patel 取代的旧依赖规则")],
 "stages":[
  S("IL-1","三项考量","The Patel trio","balancing",
    "(a) 被违反禁令的目的;(b) 其他相关公共政策;(c) 拒绝救济是否与不法程度成比例。",
    [F("IL-purpose","被违反之禁令的目的是否因拒绝救济而增进","Purpose of the prohibition transgressed",0.35,"立法目的;禁令性质"),
     F("IL-other-policy","其他公共政策是否因拒绝救济而受损","Other relevant public policies",0.30,"如避免不当得利"),
     F("IL-proportionality","拒绝救济与不法程度是否成比例","Proportionality of denying relief",0.35,"不法的严重性、故意程度、当事人地位对比")],
    ws=E, note="三项权重近似均分,反映判例把三者并列的表述。")]})

M.append({"id":"UI","area":"衡平 Equity","zh":"不当影响","en":"Undue influence","jurisdiction":"EN/HK/SG","role":"shield","role_zh":"盾","role_note":"通常以抗辩姿态抵抗执行，亦可作为撤销之诉的诉因；gateway结构兼顾两种用法。",
 "top_type":"presumption-rebuttal","corpus_hits":29,
 "authorities":[A("Royal Bank of Scotland v Etridge (No 2)","[2001] UKHL 44","HL","推定的构成与银行的查询义务"),
   A("Waller Edwards v One Savings Bank","[2025] UKSC","UKSC","混合交易与 Etridge 守则","unverified")],
 "note":"实际不当影响须举证;推定不当影响由信任关系加需要解释的交易触发,再由对方反驳。",
 "stages":[
  S("UI-1","路径","Route","disjunctive-gateway","实际不当影响 或 推定不当影响,择一。",
    [F("UI-actual","实际不当影响(举证)","Actual undue influence"),
     F("UI-presumed","推定不当影响","Presumed undue influence")]),
  S("UI-2","推定的触发","Triggering the presumption","conjunctive",
    "信任与信赖关系 + 交易需要解释。两者皆须。",
    [F("UI-relationship","信任与信赖关系","Relationship of trust and confidence"),
     F("UI-calls-for-explanation","交易需要解释","Transaction calls for explanation")]),
  S("UI-3","反驳","Rebuttal","balancing","独立法律意见是常见但非唯一的反驳途径。",
    [F("UI-independent-advice","获得独立法律意见","Independent legal advice"),
     F("UI-advice-quality","该意见的实质质量","Quality of that advice"),
     F("UI-full-disclosure","充分披露","Full disclosure"),
     F("UI-free-will","自主决定的其他证据","Other evidence of free will")])]})

M.append({"id":"LEASE","area":"土地 Land","zh":"租赁抑或许可","en":"Lease or licence","jurisdiction":"HK/EN/SG","role":"spear","role_zh":"矛","role_note":"定性之争姿态中立，实践中多由占有人/主张租赁权一方提起，按主张方归矛。",
 "top_type":"conjunctive+override","corpus_hits":352,
 "note":"语料里出现频次第一。三要件合取,但实质重于形式——标签不决定性质。",
 "authorities":[A("Street v Mountford","[1985] AC 809","HL","排他占有为租赁的标志"),
   A("Bruton v London & Quadrant Housing Trust","[2000] 1 AC 406","HL","非业权人授出的租赁")],
 "stages":[
  S("LS-1","三要件","The Street indicia","conjunctive","排他占有 + 确定期限 + 租金(租金非绝对必要)。",
    [F("LS-exclusive","排他占有","Exclusive possession"),
     F("LS-term","确定期限","Certain term"),F("LS-rent","租金","Rent")]),
  S("LS-2","实质重于形式","Substance over label","balancing",
    "协议自称许可不决定性质;看真实安排与假条款。",
    [F("LS-label","文件自称许可","Document labelled a licence"),
     F("LS-sham-terms","假条款(如保留共用权而实际不行使)","Sham or pretence terms"),
     F("LS-provider-services","提供者保留服务与出入","Services and access retained"),
     F("LS-conduct","双方实际行为","Actual conduct of the parties")])]})

M.append({"id":"NYC","area":"仲裁 Arbitration","zh":"纽约公约执行抗辩","en":"Enforcement — NY Convention Art V","jurisdiction":"HK/SG/EN","role":"procedure","role_zh":"程序","role_note":"在执行程序内行被执行人之盾(V(1)/V(2)拒绝事由)；按程序类型归程序。",
 "top_type":"disjunctive-gateway","corpus_hits":0,
 "note":"全法律里最天然的机器可读要件表:封闭清单,任一项成立即可拒绝执行,举证责任在被申请人(V(2) 除外)。",
 "authorities":[A("New York Convention 1958 Art V","—","—","封闭的拒绝执行事由清单"),
   A("Hebei Import & Export v Polytek Engineering","(1999) 2 HKCFAR 111","CFA","香港公共政策标准"),
    A("Dallah Real Estate v Government of Pakistan","[2010] UKSC 46","UKSC","执行法院重新独立判断管辖权;非签字方不执行","primary","[101],[104],[159]-[160],[162]","caselaw.nationalarchives.gov.uk/uksc/2010/46/data.xml"),
    A("PT First Media v Astro Nusantara","[2013] SGCA 57","SGCA","选择救济与迟来管辖权异议的排除","web",None,"eLitigation down at survey; corroborated via headnote excerpt + Drew & Napier + Legal Wires + NY Convention Guide")],
 "timelines":{
  "NYC-V":{"title":"纽约公约执行:拒绝执行事由的形成","title_en":"NY Convention enforcement — refusal grounds as applied",
   "sub_test":"NY-1",
   "note":"覆盖V(1)被申请人举证事由与V(2)法院自认事由;NY-3剩余裁量是裁量不是漂移,不在内。f方向:+1亲执行,-1反执行;幅度coarse,仅看符号。",
   "events":[
    {"j":"HK","y":1999,"f":0.7,"case":"Hebei Import & Export v Polytek Engineering","cite":"(1999) 2 HKCFAR 111","court":"CFA","court_rank":4,"treat":"establishes","eff":"公共政策抗辩从严解释,亲执行偏倚。","verified":"unverified","pin":None,"source":"registry authority record as-is; absent from HKLII CFA index as surveyed 2026-09-05 (nil recorded, not evidence of absence)"},
    {"j":"EN","y":2010,"f":-0.8,"case":"Dallah Real Estate v Government of Pakistan","cite":"[2010] UKSC 46","court":"UKSC","court_rank":4,"treat":"establishes","eff":"执行法院对仲裁庭管辖权决定重新独立判断,不予遵从;非签字方不受仲裁协议约束则拒绝执行;上诉驳回。","verified":"primary","pin":"[101],[104],[159]-[160],[162]","source":"caselaw.nationalarchives.gov.uk/uksc/2010/46/data.xml (judgment text read)"},
    {"j":"SG","y":2013,"f":0.1,"case":"PT First Media v Astro Nusantara","cite":"[2013] SGCA 57","court":"SGCA","court_rank":4,"treat":"confines","eff":"不行使主动挑战的一方仍可在执行阶段援引抗辩(选择救济),无弃权问题;但绕过Art 16(3)的迟来管辖权异议在执行阶段被排除。","verified":"web","pin":None,"source":"eLitigation down at survey 2026-09-05; corroborated via eLitigation headnote excerpt + Drew & Napier (Lexology 2013-11-28) + Legal Wires + NY Convention Guide"},
     {"j":"HK","y":2026,"f":0.8,"case":"Eton Properties v Xiamen Xin Jing Di","cite":"[2026] HKCFA 30","court":"CFA-AC","court_rank":3,"treat":"establishes","eff":"Leave refused; CA fresh-cause-of-action route intact: common-law damages on the implied promise to honour the award, electable against the statutory judgment; full common-law remedies available.","verified":"primary","pin":"[11] (fresh cause of action + election); determination (unnum.): Those questions are decidedly opaque / insurmountable hurdles","source":"HKLII getjudgment hkcfa/2026/30 (determination text read 2026-09-05)"}
   ]}},
  "stages":[
  S("NY-1","V(1) 被申请人须举证的事由","Grounds the respondent must prove","disjunctive-gateway",
    "任一项成立即可拒绝执行。",
    [F("NY-incapacity","当事人无行为能力或仲裁协议无效","Incapacity / invalid agreement"),
     F("NY-notice","未获适当通知或无法陈述案情","Improper notice / unable to present case"),
     F("NY-scope","超出提交仲裁的范围","Beyond the scope of submission"),
     F("NY-composition","仲裁庭组成或程序不符约定","Composition or procedure not in accordance"),
     F("NY-not-binding","裁决尚无约束力或已被撤销/中止","Not yet binding / set aside / suspended")]),
  S("NY-2","V(2) 法院可自行认定的事由","Grounds the court may raise itself","disjunctive-gateway",
    "可仲裁性与公共政策,法院可主动认定。",
    [F("NY-arbitrability","争议不可仲裁","Not arbitrable"),
     F("NY-public-policy","违反执行地公共政策","Contrary to public policy")]),
  S("NY-3","裁量","Residual discretion","threshold-discretion",
    "即使事由成立,法院仍保留是否拒绝执行的裁量。",
    [F("NY-ground-made-out","已有一项事由成立","A ground is made out",),
     F("NY-discretion-enforce","仍应执行的裁量理由","Discretion nonetheless to enforce")])]})

M.append({"id":"ARBCH","area":"仲裁 Arbitration","zh":"仲裁员回避","en":"Arbitrator challenge","jurisdiction":"HK/SG/EN","role":"procedure","role_zh":"程序",
 "top_type":"balancing","corpus_hits":0,
 "note":"示范法 art 12 的「正当怀疑」是客观旁观者标准，采用多因素权衡。",
 "authorities":[A("UNCITRAL Model Law art 12","—","—","正当怀疑标准"),
   A("Halliburton v Chubb","[2020] UKSC 48","UKSC","多重委任与披露义务","primary","[81],[150]-[158]","caselaw.nationalarchives.gov.uk/uksc/2020/48/data.xml"),
   A("Arbitration Ordinance","Cap 609","—","香港采纳示范法")],
 "timelines":{
  "ARBCH-12":{"title":"仲裁员回避:披露义务的形成","title_en":"Arbitrator challenge — the disclosure duty",
   "sub_test":"AC-1",
   "note":"HK与SG分支暂无可核查权威,记为覆盖缺口(见维护队列),不虚构事件。f方向:+1朝向挑战方问责/透明。",
   "events":[
    {"j":"EN","y":2020,"f":0.8,"case":"Halliburton v Chubb","cite":"[2020] UKSC 48","court":"UKSC","court_rank":4,"treat":"establishes","eff":"英国法下仲裁员负有法定披露义务(1996年法s.33内含),含重叠委任;以公正旁观者检验偏见;本案挑战因事实不足被驳回,上诉驳回。","verified":"primary","pin":"[81],[150]-[158]","source":"caselaw.nationalarchives.gov.uk/uksc/2020/48/data.xml (judgment text read; leading judgment Lord Hodge, unanimous)"},
     {"j":"HK","y":2022,"f":0.0,"case":"C v D","cite":"[2022] HKCFA 25","court":"CFA-AC","court_rank":3,"treat":"frames","eff":"Appeal Committee grants leave confined to the Art 34(2)(a)(iii) recourse question; first HK case on pre-arbitration conditions and set-aside review.","verified":"primary","pin":"Determination [1]-[3]","source":"HKLII getjudgment hkcfa/2022/25 (determination text read 2026-09-05)"},
     {"j":"HK","y":2023,"f":-0.9,"case":"C v D","cite":"[2023] HKCFA 16","court":"CFA","court_rank":4,"treat":"confines","eff":"Pre-arbitration condition compliance goes to admissibility, decided finally by the tribunal; no s 81/Art 34(2)(a)(iii) review. Presumptively non-jurisdictional; elevation needs unequivocally clear language.","verified":"primary","pin":"Ribeiro PJ s D; Gummow NPJ [112]-[139]; CJ concurrence on elevation by agreement","source":"HKLII getjudgment hkcfa/2023/16 (judgment text read 2026-09-05)"}
   ]}},
  "stages":[
  S("AC-1","正当怀疑","Justifiable doubts","balancing",
    "客观、知情的旁观者是否会认为存在对公正性的真实可能怀疑。",
    [F("AC-multiple-appointments","重叠委任","Overlapping appointments"),
     F("AC-nondisclosure","未披露本应披露的事项","Failure to disclose"),
     F("AC-financial","财务利益","Financial interest"),
     F("AC-relationship","与一方或代理人的关系","Relationship with a party or counsel"),
     F("AC-prior-views","就同一争点已表达立场","Previously expressed views"),
     F("AC-market-practice","该领域的惯常做法","Custom of the particular field")])]})

M.append({"id":"CECO","area":"合同 Contract","zh":"免责条款合理性","en":"Reasonableness of an exemption clause","jurisdiction":"HK","role":"shield","role_zh":"盾","role_note":"破盾之矛：专用于打掉对方的免责条款之盾；归盾因其在合同争议中居防御位。",
 "top_type":"balancing","corpus_hits":0,
 "note":"直接接住失实陈述模块的 D1 抗辩:Cap 284 s.4 把 non-reliance 条款送进 Cap 71 s.3(1) 的合理性审查。Cap 71 s.3(2) 明定附表2指引用于ss.11及12；不得把该清单自动套用于Cap 284 s.4或Cap 71 s.7。",
 "authorities":[A("Control of Exemption Clauses Ordinance","Cap 71 ss.3(1), 3(2), 3(6), 7(1)-(2)","—","一般合理性标准、证明责任及过失责任免责限制；附表2的法定适用范围限于ss.11及12"),
   A("Chang Pui Yin v Bank of Singapore","[2017] 4 HKLRD 458","HKCA","对非成熟客户条款不合理","web"),
   A("Green Park Properties v Dorku","(2001) 4 HKCFAR 448","CFA","整体协议条款未过合理性","web")],
 "stages":[
  S("CE-1","合理性","Reasonableness","balancing",
    "订约时是否为公平合理的条款，须考虑订约时双方已知、应当合理知悉或预期的全部情况。下列附表2项目仅在s.3(2)所指的ss.11及12案件中属法定指引；其他案件不得自动套用。",
    [F("CE-bargaining","议价能力对比","Relative bargaining strength"),
     F("CE-inducement","是否因接受条款而获诱因","Inducement to agree"),
     F("CE-knowledge","是否知悉或应知条款存在","Knowledge of the term"),
     F("CE-practicable","履行条件是否实际可行","Practicability of compliance"),
     F("CE-bespoke","是否为特别订制的货品","Special order goods"),
     F("CE-sophistication","客户成熟程度","Sophistication of the customer",note="并非附表2列项；只可在个案全部情况确有证据支持时考虑。")],
    note="这些档位是编者对附表2/个案因素的先验整理，不表示所有因素适用于每一类免责条款。") ]})

M.append({"id":"VEIL","area":"公司 Company","zh":"揭开公司面纱","en":"Piercing the corporate veil","jurisdiction":"EN/HK/SG","role":"spear","role_zh":"矛",
 "top_type":"threshold-discretion","corpus_hits":0,
 "note":"Prest 之后不再是多因素权衡,而是两个原则的门槛判断——这正是「分类比赋权重重要」的例子。",
 "authorities":[A("Prest v Petrodel Resources","[2013] UKSC 34","UKSC","隐匿原则与规避原则"),
   A("Adams v Cape Industries","[1990] Ch 433","EWCA","此前的收紧"),
   A("Salomon v A Salomon & Co","[1897] AC 22","HL","法人独立人格")],
 "stages":[
  S("VL-1","两原则","Concealment / evasion","disjunctive-gateway",
    "隐匿原则:只是看穿以查明真实主体,并非真正揭开。规避原则:为规避既存义务而设立或利用公司,方为真正揭开。",
    [F("VL-concealment","隐匿(查明幕后真实主体)","Concealment principle"),
     F("VL-evasion","规避既存法律义务","Evasion principle")]),
  S("VL-2","其他救济优先","Other remedy first","threshold-discretion",
    "若可通过代理、信托、合同等常规途径得到相同结果,则不应揭开。",
    [F("VL-alternative","存在常规替代救济","Conventional remedy available")])]})

for module in M:
    enrich_module(module)

REG={"generated":"2026-09-09","version":"0.4",
 "principle":"每个判断阶段先按 test_type 分类；只有多因素权衡使用数值份量区间。诉讼姿态（矛／盾）与事项轨道（实体／程序／管辖）分别记录，均不是法律要件。hklandlaw 计数只表示语料覆盖，不决定判断逻辑、权威等级或权重。",
 "test_types":TEST_TYPES,
 "posture_catalog":POSTURE_CATALOG,
 "track_catalog":TRACK_CATALOG,
 "source_catalog":SOURCE_CATALOG,
 "modules":M}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build the doctrine registry.')
    parser.parse_args(argv)
    emit('registry', REG, indent=1)
    n_f=sum(len(s.get('factors',[]))+len(s.get('counter_factors',[])) for m in M for s in m['stages'])
    balancing=[f for m in M for s in m['stages'] if s['test_type']=='balancing'
               for f in s.get('factors',[])+s.get('counter_factors',[])]
    n_w=sum(1 for f in balancing if f.get('weight') is not None)
    print(f"modules: {len(M)}  stages: {sum(len(m['stages']) for m in M)}  factors: {n_f}")
    print(f"balancing factors: {len(balancing)}  assigned: {n_w}  awaiting bands: {len(balancing)-n_w}")
    import collections
    print("test_type distribution:", dict(collections.Counter(s['test_type'] for m in M for s in m['stages'])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
