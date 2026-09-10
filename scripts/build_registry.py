# -*- coding: utf-8 -*-
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

E = "editorial-prior"; U = "unassigned"
def F(i,zh,en,w=None,ev=None,note=None,**meta):
    d={"id":i,"zh":zh,"en":en,"weight":w,"evidence":ev}
    if note: d["note"]=note
    if w is None: d["weight_status"]=U
    d.update(meta)
    return d
def S(i,zh,en,tt,rule,factors,ws=None,cf=None,note=None,doctrinal_role=None,applies_when=None,jurisdiction_rules=None,jurisdictions=None):
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
    if jurisdictions: d["jurisdictions"]=list(jurisdictions)
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

M.append({"id":"PENALTY","area":"合同 Contract","zh":"违约金条款","en":"Penalty clauses","jurisdiction":"HK/EN","role":"shield","role_zh":"盾",
 "top_type":"conjunctive","corpus_hits":3,
 "note":"罚则规则是执行抗辩，不是独立诉因。先确认条款因违约启动并课加从属不利益，再判断该不利益是否相对守约方履行利益显失比例；不以固定比例或数值权重代替法律判断。",
 "jurisdiction_rules":{
   "EN":"Cavendish 是控制性规则；在订约时评价。消费者不公平条款审查属于另一制度。",
   "HK":"Law Ting Pong 明示采纳 Cavendish；主张罚则者负举证责任。"},
 "authorities":[
   A("Cavendish Square Holding BV v Talal El Makdessi; ParkingEye Ltd v Beavis","[2015] UKSC 67; [2016] AC 1172","UKSC","主要／从属义务门槛；正当利益与显失比例测试","verified-primary","[9],[13]-[15],[31]-[35]","https://supremecourt.uk/uploads/uksc_2013_0280_judgment_c7f37dda32.pdf"),
   A("Law Ting Pong Secondary School v Chen Wai Wah","[2021] HKCA 873; [2021] 3 HKLRD 185","HKCA","香港采纳 Cavendish；举证责任、适用门槛与比例分析","verified-primary","[2]-[6],[64],[69]-[75],[79]-[82]","https://legalref.judiciary.hk/doc/judg/word/vetted/other/en/2019/CACV000517_2019.docx")],
 "stages":[
  S("PEN-1","适用门槛：违约后的从属义务","Scope gateway — secondary obligation on breach","conjunctive",
    "主张该条款为罚则者须证明：条款因违反主要义务而启动，并课加一项从属性不利益。主要义务本身及非因违约发生的条件性付款不受罚则规则规制；分类看实质而非标签。",
    [F("PEN-breach-trigger","条款由违约触发","Triggered by breach",required=True,evidence="合同触发条文、所指主要义务及已发生的违约"),
     F("PEN-secondary","属于违约后的从属义务而非主要义务","Secondary rather than primary obligation",required=True,evidence="整份合同、价款机制及违约后果"),
     F("PEN-detriment","向违约方课加不利益","Detriment imposed on the contract-breaker",required=True,evidence="付款、没收、扣留价款、财产转移或其他后果")],
    jurisdiction_rules={"EN":"按 Cavendish 在订约时检验主要／从属义务。","HK":"Law Ting Pong [69]-[71] 采纳同一门槛。"}),
  S("PEN-2","正当利益与显失比例","Legitimate interest and disproportionality","conjunctive",
    "识别守约方在主要义务履行上的正当利益。只有所加不利益相对于任何该等利益均显失比例，达到 extravagant、exorbitant 或 unconscionable 的惩罚性质，才作为罚则不可执行。预期损失仍重要，但不是唯一可保护利益。",
    [F("PEN-interest","识别订约时可保护的正当履行利益","Legitimate performance interest identified",required=True,evidence="补偿、履行、商誉、周转或交易结构等订约时材料"),
     F("PEN-proportionality","不利益相对任何正当利益显失比例","Detriment out of all proportion to every legitimate interest",required=True,dispositive=True,evidence="金额、实际效果、预期损失、损失估算难度及商业背景")],
    jurisdiction_rules={"EN":"同等议价且获专业意见的成熟商业合同通常受到较强尊重，但不是不可推翻。","HK":"主张罚则者负举证责任；重点仍是正当利益与比例，而非机械适用 Dunlop 标签。"})]})

M.append({"id":"NMS","area":"侵权 Tort","zh":"过失性失实陈述","en":"Negligent misstatement","jurisdiction":"HK/EN","role":"spear","role_zh":"矛",
 "top_type":"conjunctive","corpus_hits":1,
 "note":"责任链分为注意义务、违反及损失三段。Hedley Byrne 的客观承担责任与合理信赖是本类别基础；在既有类别中不把 Caparo 三项再机械叠加为第二套固定要件。",
 "jurisdiction_rules":{
   "EN":"Hedley Byrne／Playboy Club 以客观承担责任为基础；Manchester Building Society 以义务目的界定可赔风险。",
   "HK":"Desmond Yiu 以客观承担责任和合理信赖表述规则，并把实际信赖作为独立事实问题；Manchester 2021 的义务目的分析在此仅列为英格兰控制性发展及香港说服性参照。"},
 "authorities":[
   A("Hedley Byrne & Co Ltd v Heller & Partners Ltd","[1963] UKHL 4; [1964] AC 465","HL","特殊关系、承担责任与免责声明","verified-primary","AC 486,492-493,502-503,529-533","https://www.bailii.org/uk/cases/UKHL/1963/4.html"),
   A("Desmond Yiu Chown Leung v Chow Wai Lam William","[2005] HKCFA 68; (2005) 8 HKCFAR 592","HKCFA","香港约束性客观承担责任测试、义务范围与实际信赖","verified-primary","[7],[26]-[30]","https://legalref.judiciary.hk/doc/judg/word/vetted/other/en/2004/FACV000018_2004.doc"),
   A("Banca Nazionale del Lavoro SpA v Playboy Club London Ltd","[2018] UKSC 43; [2018] 1 WLR 4041","UKSC","可识别收件人、已知交易与目的","verified-primary","[6]-[11],[16],[20]-[24]","https://supremecourt.uk/uploads/uksc_2016_0121_judgment_837b810e47.pdf"),
   A("Manchester Building Society v Grant Thornton UK LLP","[2021] UKSC 20; [2022] AC 783","UKSC","可赔损失范围由义务目的客观界定","verified-primary","[4],[6],[13]-[15]","https://supremecourt.uk/uploads/uksc_2019_0040_judgment_2b04c84658.pdf")],
 "stages":[
  S("NMS-1","注意义务：承担责任与合理信赖","Duty — assumption of responsibility and reasonable reliance","conjunctive",
    "在无合同的情况下，若原告在合理情境中依赖被告提供的资料、意见或服务，而被告客观上承担该任务并知道或应知道该原告或可识别类别会为已知目的依赖，可产生对纯经济损失的注意义务；无须证明被告主观上有意承担。",
    [F("NMS-undertaking","被告客观承担提供资料、意见或服务的任务","Objective undertaking or assumption of responsibility",required=True),
     F("NMS-recipient","原告属于已识别或可识别的人或类别","Identifiable person or class",required=True),
     F("NMS-purpose","被告知悉具体交易或依赖目的","Known transaction or purpose",required=True),
     F("NMS-knowledge","被告知道或应知道该依赖很可能发生","Knowledge that reliance was likely",required=True),
     F("NMS-reasonable-reliance","该信赖在整体情境中合理","Reliance objectively reasonable",required=True),
     F("NMS-disclaimer","有效免责声明是否客观否定承担责任","Effective disclaimer may negate responsibility",negates=True,note="效力仍须接受适用的合同及法定控制，不能自动视为有效。")]),
  S("NMS-2","违反义务及任务范围","Breach and scope of the task","conjunctive",
    "资料或意见须不准确、不完整或以其他方式误导，而且被告在准备或传达时未尽合理谨慎与技能；错误须落在被告客观承担的任务及已知使用目的内。",
    [F("NMS-inaccuracy","资料或意见不准确、不完整或误导","Inaccurate, incomplete or misleading information or advice",required=True),
     F("NMS-standard","被告未尽合理谨慎与技能","Failure to exercise reasonable care and skill",required=True),
     F("NMS-task-scope","错误落在被承担任务内","Error within the task undertaken",required=True),
     F("NMS-use-scope","原告按被告知悉的目的使用陈述","Use for the known purpose or transaction",required=True)]),
  S("NMS-3","实际信赖、因果关系与可赔损失","Actual reliance, causation and recoverable loss","conjunctive",
    "原告须实际依赖，并证明违反义务事实上造成可诉损失；可赔范围还须对应义务旨在防范的风险，并受法律因果关系、遥远性、减损及共同过失等一般限制。",
    [F("NMS-actual-reliance","原告实际依赖该陈述或意见","Actual reliance",required=True),
     F("NMS-factual-cause","若无该过失陈述，损失不会发生","Factual causation",required=True),
     F("NMS-actionable-loss","发生可诉损失，包括适用时的纯经济损失","Actionable loss, including pure economic loss where recoverable",required=True),
     F("NMS-duty-risk","损失属于该义务目的所防范的风险","Loss within the purpose and scope of duty",required=True),
     F("NMS-remoteness","通过遥远性及其他损害限制","Remoteness and other limits",required=True)],
    jurisdiction_rules={"EN":"Manchester Building Society 是义务范围的控制性说明。","HK":"本地现有锚点为 Desmond Yiu；Manchester 的精确适用仍应核对其后香港约束性权威。"})]})

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

M.append({"id":"LPP","area":"程序与证据 Procedure & Evidence","zh":"法律专业特权","en":"Legal professional privilege","jurisdiction":"HK/EN","role":"shield","role_zh":"盾",
 "top_type":"conjunctive+disjunctive-gateway","corpus_hits":0,
 "note":"先过共同保密和举证门槛，再由法律意见特权或诉讼特权任一分支成立，最后独立检查放弃、欺诈／不法目的、保密性丧失或明确法定限制。各分支均为法律清单，不赋数值权重。Without-prejudice privilege 是另一制度，未混入本模块。",
 "jurisdiction_rules":{
   "HK":"Citic Pacific 不采 Three Rivers (No 5) 的狭窄公司 client group；获授权雇员为取得法律意见而参与的沟通过程可受保护，但仍须逐件证明主导目的。Akai 控制诉讼特权的现实诉讼前景及主导目的。",
   "EN":"Three Rivers (No 5) 的狭窄 client group 规则仍约束上诉法院；ENRC 明言认为该规则有疑问但无权推翻。Aabar 2026 仅为高院层面对已确定客户组内部文件的更新。"},
 "authorities":[
   A("Citic Pacific Ltd v Secretary for Justice and Commissioner of Police","[2015] HKCA 293; [2015] 4 HKLRD 20","HKCA","香港法律意见特权、主导目的、既有原始文件及公司客户范围","verified-primary","[2],[34]-[36],[42]-[50],[52]-[63]","https://legalref.judiciary.hk/doc/judg/word/vetted/other/en/2012/CACV000007_2012.doc"),
   A("Akai Holdings Ltd (in Compulsory Liquidation) v Ernst & Young (A Hong Kong Firm)","[2009] HKCFA 14; (2009) 12 HKCFAR 649","HKCFA","现实诉讼前景、主导目的及调查性取材与对抗性目标诉讼","verified-primary","[67]-[72],[76]-[77],[99]-[102],[117]-[123]","https://legalref.judiciary.hk/doc/judg/word/vetted/other/en/2008/FACV000028_2008.doc"),
   A("Director of the Serious Fraud Office v Eurasian Natural Resources Corp Ltd","[2018] EWCA Civ 2006; [2019] 1 WLR 791","EWCA","英国两类特权、合理预期诉讼与主导目的；Three Rivers 窄客户规则仍具约束力","verified-primary","[64]-[66],[91]-[102],[121]-[133]","https://caselaw.nationalarchives.gov.uk/ewca/civ/2018/2006"),
   A("Aabar Holdings SARL v Glencore plc","[2026] EWHC 877 (Comm); [2026] WLR(D) 233","EWHC (Comm)","既定客户组内部材料以寻求法律意见为主导目的时的高院更新","verified-primary","[16],[46],[51],[62]-[75]","https://www.judiciary.uk/wp-content/uploads/2026/04/FL-2022-000024-Judgment-Final.pdf")],
 "stages":[
  S("LPP-1","共同门槛：保密、权利人及具体证明","Common gateway — confidentiality, holder and proof","conjunctive",
    "主张者负举证责任，须识别具体通信或材料，证明其保密性及主张特权的资格，并以材料形成时的客观事实和具体证据支持法律意见或诉讼分支。标签、把律师抄送在内或事后把既有文件交给律师均不充分。",
    [F("LPP-confidential","材料具有并维持保密性","Material is confidential",required=True,evidence="收件人、传播范围、保密标示与实际处理"),
     F("LPP-holder","特权属于该客户且由其或获授权者主张","Privilege belongs to the client and is properly asserted",required=True),
     F("LPP-proof","有具体、同期及客观证据证明形成目的","Specific contemporaneous and objective proof",required=True,evidence="形成日期、作者、收件人、委聘范围、同期邮件及具体誓章"),
      F("LPP-material-identity","已区分既有原始文件与为受保护目的形成的新通信或材料","Pre-existing raw material distinguished from newly privileged communications",role="scope-check")]),
  S("LPP-2","法律意见特权","Legal advice privilege","conjunctive",
    "须为保密的律师—客户通信，或依适用法域可纳入的客户内部材料，其唯一或主导目的为寻求、给予、记录、传达或落实法律意见。法律意见可涵盖在相关法律情境中应审慎合理采取的行动；主要为商业或行政意见不会因律师参与而受保护。",
    [F("LAP-lawyer-capacity","法律顾问以专业法律身份参与","Lawyer acting in a legal capacity",required=True),
     F("LAP-client-channel","属于适用法域认可的客户沟通渠道","Recognised client communication channel",required=True),
     F("LAP-dominant-purpose","唯一或主导目的为取得或给予法律意见","Sole or dominant legal-advice purpose",required=True),
     F("LAP-legal-context","内容属于广义法律意见或其传达落实","Advice in a relevant legal context or its communication and implementation",required=True),
      F("LAP-mixed-purpose","如材料具有混合目的，已经逐件或逐通信判断","Mixed-purpose material assessed document by document where applicable",role="conditional-check")],
    jurisdiction_rules={"HK":"公司本身为客户；依 Citic Pacific，获授权雇员在以取得法律意见为主导目的的过程中的通信可受保护。","EN":"须先按 Three Rivers (No 5) 识别获授权寻求和接收法律意见的 client group；Aabar 2026 仅说明该组内部材料的主导目的分析，且只是高院判决。"}),
  S("LPP-3","诉讼特权","Litigation privilege","conjunctive",
    "材料形成时，目标诉讼须已进行或被合理预期并属对抗性；受保护通信或材料的唯一或主导目的须为就该诉讼取得或给予法律意见、搜集证据或进行诉讼，包括抵抗、避免或和解现实预期的程序。一般合规、业务补救或抽象风险本身不足。",
    [F("LIT-prospect","诉讼已进行或有现实且合理的前景","Litigation in progress or reasonably contemplated",required=True),
     F("LIT-adversarial","目标程序具有对抗性","Target proceedings are adversarial",required=True),
     F("LIT-material","属于客户、律师或第三方通信，或为诉讼形成的取证材料","Protected communication or evidential material",required=True),
     F("LIT-dominant-purpose","形成时唯一或主导目的为进行该诉讼","Sole or dominant litigation purpose at creation",required=True),
     F("LIT-conduct","目的属于取证、法律意见、抵抗、避免或和解诉讼","Evidence, advice, resistance, avoidance or settlement",required=True)],
    jurisdiction_rules={"HK":"Akai 要求积极考虑且具有现实前景；取材机制本身即使调查或纠问，也不自动排除材料服务于另一对抗性诉讼。","EN":"ENRC 要求现实可能而非抽象可能；避免或和解预期程序也可属于进行诉讼。"}),
  S("LPP-4","丧失、不适用与明确限制","Loss, exceptions and express limits","disjunctive-gateway",
    "即使某分支初步成立，请求查阅者仍可证明一项适用的丧失或排除理由。每项理由须按法域分别证明；披露迟延或一般公平诉求本身不够。",
    [F("LPP-waiver","权利人明示或默示放弃相关特权及其适当范围","Express or implied waiver and its proper scope",evidence="自愿披露、依赖材料、共同公平及有限放弃范围"),
     F("LPP-iniquity","通信服务于欺诈、不法或滥用法律咨询关系的目的","Fraud, iniquity or abuse exception",evidence="通信目的而非仅指称既往不法"),
     F("LPP-confidentiality-lost","保密性已经丧失且法律不再保护","Confidentiality lost so protection no longer subsists",evidence="传播对象、授权、公开程度及补救步骤"),
     F("LPP-statutory-limit","成文法以足够明确用语废除或限制特权","Statute clearly abrogates or limits privilege",evidence="条文文字、适用范围及保留条款")],
    jurisdiction_rules={"HK":"放弃、欺诈／不法目的及法定限制必须按香港权威和具体事实分别核验；本阶段不把任一标签自动当作成立。","EN":"同样须逐项适用英格兰现行规则；common-interest privilege 属另一扩展问题，并非本阶段的丧失理由。"})]})

M.append({"id":"DISC","area":"程序与证据 Procedure & Evidence","zh":"文件披露范围","en":"Scope of disclosure","jurisdiction":"HK/EN","role":"procedure","role_zh":"程序",
 "top_type":"conjunctive+threshold-discretion","corpus_hits":1,
 "note":"香港与英格兰的范围规则必须分支处理。香港 O.24 保留较宽的直接、间接及调查线索相关性，但具体披露仍须与已诉辩争点相连并受公正、成本和比例限制；英格兰普通 CPR 31.6 与 Business and Property Courts 的 PD57AD 不能混用。特权、诉前披露及非当事人披露另按各自门槛处理。",
 "jurisdiction_rules":{
   "HK":"RHC O.24 以直接、间接及合理调查线索相关性为起点；具体披露须就已诉辩争点必要，并受 O.1A、rr.8、13、15A 的公正、成本及比例限制。",
   "EN":"CPR 31.6 标准披露涵盖己方依赖、对己方或他方不利、或支持他方案件的文件；Business and Property Courts 依 PD57AD 按争点选择 Models A–E，Model E 的调查线索搜索只属例外。"},
 "authorities":[
   A("Rules of the High Court, Order 24","Cap 4A, O.24 rr.1,3,7,8,13,15A","HK subsidiary legislation","香港文件披露、具体披露、搜索、拒绝披露与持续义务","verified-primary","O.24 rr.1,3,7,8,13,15A","https://www.civiljustice.hk/gaz_sub_leg/documents/rhc/RHC_Order_24.pdf"),
   A("Tullett Prebon (Hong Kong) Ltd v Chan Yeung Fong Nick","HCA 2197/2009; [2011] HKEC 761","HKCFI","相关性、具体披露与比例限制","verified-web","[10]-[19],[64]-[85]","https://vlex.hk/vid/tullett-prebon-hong-kong-862792558"),
   A("Civil Procedure Rules Part 31","CPR rr.31.5-31.12A","E&W rules","英格兰标准披露、控制、合理搜索、清单及持续义务","verified-primary","rr.31.5-31.12A","https://www.justice.gov.uk/courts/procedure-rules/civil/rules/part31"),
   A("Practice Direction 57AD","PD57AD paras 1,3,6-10","E&W practice direction","Business and Property Courts 的按争点披露 Models A-E","verified-primary","paras 1,3,6-10","https://www.justice.gov.uk/courts/procedure-rules/civil/rules/part-57a-business-and-property-courts/practice-direction-57ad-disclosure-in-the-business-and-property-courts")],
 "stages":[
  S("DS-1","范围与控制门槛","Scope and control gateway","conjunctive",
    "须先确定适用制度及当前争点；被请求的文件或自然类别须存在、落入该制度的披露范围，并在被申请人的管有、保管或权力（香港）或控制（英格兰）内。任何拒绝披露理由须按适用程序明确提出。",
    [F("DS-regime","已确定适用法域、规则及披露模式","Applicable jurisdiction, rule and disclosure model identified",required=True),
     F("DS-live-issue","文件对应当前诉辩争点或 Issues for Disclosure","Connected to a live pleaded issue or Issue for Disclosure",required=True),
     F("DS-document","文件或按性质界定的自然类别存在","Document or naturally defined class exists",required=True),
     F("DS-relevance","达到适用法域的内容或调查线索门槛","Applicable content or train-of-inquiry threshold met",required=True),
     F("DS-control","属于管有、保管、权力或控制范围","Within possession, custody, power or control",required=True),
      F("DS-withholding","如主张拒绝披露，已识别并依规则提出特权或其他理由","Any privilege or other withholding ground identified and claimed where applicable",role="exception",note="只有实际主张拒绝披露时才适用；不存在拒绝理由不是要件缺口。")],
    jurisdiction_rules={"HK":"具体披露申请还须以证据支持文件存在及管有、保管或权力；不得仅作 fishing。","EN":"先区分 CPR 31 普通制度、法院特别命令及 PD57AD Models A-E。"}),
  S("DS-2","具体披露、搜索与限缩","Specific disclosure, search and tailoring","threshold-discretion",
     "只有额外披露或搜索为公正处理争议而合理必要时才进入命令裁量。法院可按争点、期间、保管人、资料源、格式及搜索方法限缩，兼顾证明价值、成本、压迫性、替代来源、特权与保护措施。",
    [F("DS-necessity","额外披露或搜索为公正处理当前争点而合理必要","Additional disclosure or search is reasonably necessary for fair disposal",gate=True),
     F("DS-specificity","文件或类别按性质具体界定","Specificity of the document or class",role="discretion",evidence="文件类别、期间、保管人及资料源"),
     F("DS-yield","预期证明价值及争点重要性","Expected probative yield and importance",role="discretion"),
     F("DS-burden","数量、复杂程度、成本及人力负担","Volume, complexity, cost and effort",role="discretion"),
     F("DS-access","检索难度及替代来源","Retrieval difficulty and alternative sources",role="discretion"),
      F("DS-search-design","期间、保管人、资料库、格式及搜索方法","Search design and limits",role="discretion"),
      F("DS-protection","特权、保密、删节、保密圈或分阶段披露","Privilege, confidentiality and protective measures",role="discretion")],
     jurisdiction_rules={"HK":"适用 O.1A 与 O.24 rr.8、13、15A 的必要性和比例控制。","EN":"适用 CPR 31.5/31.7 或 PD57AD 所选 Model；Model E 仅在例外案件使用。"}),
   S("DS-3","持续披露义务","Continuing duty of disclosure","conjunctive",
     "披露义务持续至程序终结。已经作出披露后，如发现应披露的新文件或先前遗漏，负有义务的一方须及时通知其他方，并依适用规则补充清单、披露或查阅安排；这是一项持续义务，不是法院权衡中的可选因素。",
     [F("DS-continuing","适用的披露义务持续至程序终结","Applicable disclosure duty continues until the proceedings conclude",required=True),
      F("DS-supplement","如发现新文件或遗漏，已及时通知并补充披露","Newly discovered or omitted documents are promptly notified and disclosed where applicable",required=True,role="conditional-check",note="只有发现落入适用披露范围的新文件或遗漏时，补充行动才被触发。")],
     applies_when={"stage_id":"DS-1","factor_ids":["DS-relevance","DS-control"]},
     jurisdiction_rules={"HK":"RHC O.24 r.13 规定持续披露义务。","EN":"CPR 31.11 规定持续披露义务；PD57AD 案件另依其持续义务条文核对。"})]})

M.append({"id":"EASE","area":"土地 Land","zh":"地役权","en":"Easements","jurisdiction":"HK/EN","role":"spear","role_zh":"矛",
 "top_type":"conjunctive+disjunctive-gateway","corpus_hits":63,
 "note":"先判断所主张权利能否成为地役权，再分别选择明示、默示或时效取得路径。香港多层大厦共同业主间的使用权可能由公契创设，不能未经文书与 Cap 344 分析直接当作普通法地役权。范围、过度使用、消灭、登记及优先权须在具体案件另行核对。",
 "jurisdiction_rules":{
   "HK":"资格结构承接普通法；取得可经明示、默示或时效。香港时效取得主要采用 lost modern grant，并不直接适用英国 Prescription Act 1832。",
   "EN":"适用 Ellenborough 四项资格要求及 Regency Villas 的现代解释；明示、默示和传统三种时效路径须分别分析。"},
 "authorities":[
   A("Re Ellenborough Park","[1955] EWCA Civ 4; [1956] Ch 131","EWCA","地役权四项资格要求","verified-primary","pp 163-164","https://www.bailii.org/ew/cases/EWCA/Civ/1955/4.html"),
   A("Regency Villas Title Ltd v Diamond Resorts (Europe) Ltd","[2018] UKSC 57","UKSC","现代解释、便利需役地与可授予权利边界","verified-primary","[39]-[81]","https://www.supremecourt.uk/cases/uksc-2017-0083"),
   A("China Field Ltd v Appeal Tribunal (Buildings) (No 2)","(2009) 12 HKCFAR 342","HKCFA","香港普通法地役权及建筑物语境","verified-web","[41]-[48],[71],[73]-[87]","https://babelcite.com/case/68220"),
   A("Loyal Luck Trading Ltd v Tam Chun Wah","[2008] 4 HKLRD 681","HKCA","CPO s.16、Wheeldon 与通道默示取得","verified-web",None,"https://babelcite.com/case/60637")],
 "stages":[
  S("EA-1","地役权资格","Easement characteristics","conjunctive",
    "须有可识别的需役地与供役地；权利客观上便利需役地的正常使用或享用；两地所有及占用并非完全统一；权利内容须足够确定、合法且能够成为授予标的，不实质排除供役地主的占有，也不要求其持续支出或提供服务。",
    [F("EA-tenements","存在可识别的需役地与供役地","Identifiable dominant and servient tenements",required=True),
     F("EA-accommodation","权利便利需役地而非仅给个人利益","Right accommodates the dominant tenement",required=True),
     F("EA-diversity","两地所有及占用并非完全统一","Diversity of ownership or occupation",required=True),
     F("EA-certainty","权利的性质、区域、期间及使用方式足够明确","Sufficient certainty of nature, area, duration and use",required=True),
     F("EA-capacity","权利合法且当事人有能力授予和受领","Lawful and capable grantor and grantee",required=True),
     F("EA-no-ouster","不实质独占或排除供役地主","No substantial ouster of the servient owner",required=True),
     F("EA-no-positive-duty","不强制供役地主持续支出或提供服务","No continuing positive expenditure or service by servient owner",required=True)]),
  S("EA-2","取得路径","Mode of acquisition","disjunctive-gateway",
    "申请人须证明至少一条取得路径：有效明示授予或保留、适用法承认的默示取得，或时效取得。每条路径仍须分别满足其自身要件。",
    [F("EA-express","有效明示授予或保留","Valid express grant or reservation",evidence="文书、地段图、登记及实际范围"),
     F("EA-implied","适用法承认的默示取得路径","Recognised implied acquisition route",evidence="处分时使用、必要性、共同意图及文书背景"),
     F("EA-prescription","适用法承认的时效取得路径","Recognised prescriptive acquisition route",evidence="使用期间、性质、中断、许可及授予能力")]),
  S("EA-3","香港时效取得","Hong Kong prescription — lost modern grant","conjunctive",
    "在香港以 lost modern grant 主张时，通常须证明至少连续二十年按权利使用，即不凭武力、不秘密且未经许可，并且在法律上曾存在可作出的有效授予。",
    [F("EA-prescriptive-period","至少二十年连续且按土地性质可期待的使用","At least twenty years of continuous use appropriate to the land",required=True),
     F("EA-as-of-right","使用 nec vi、nec clam、nec precario","Use as of right: without force, secrecy or permission",required=True),
     F("EA-grant-possible","期间内法律上存在能够作出授予的人及可能性","A lawful grant was possible during the period",required=True)],
     applies_when={"stage_id":"EA-2","factor_ids":["EA-prescription"]},
     jurisdiction_rules={"HK":"二十年本身不够；容忍或许可使用不能满足 as-of-right。"},
     jurisdictions=["HK"]),
  S("EA-4","默示取得的分支","Implied acquisition routes","disjunctive-gateway",
    "默示权利必须落入适用法承认的一条具体路径；不得只因长期便利或合理需要便推定存在。",
    [F("EA-necessity","严格必要的地役权","Easement of strict necessity"),
     F("EA-common-intention","为落实双方共同意图所必要","Necessary to give effect to common intention"),
     F("EA-nonderogation","不得减损授予原则","Non-derogation from grant"),
     F("EA-wheeldon","Wheeldon v Burrows 条件满足","Wheeldon v Burrows conditions met"),
     F("EA-statutory-implied","适用的法定默示条款满足","Applicable statutory implication satisfied")],
    jurisdiction_rules={"HK":"须分别核对 CPO s.16、Wheeldon、必要性、共同意图及不得减损授予；它们不是一个宽松的总体公平测试。","EN":"另核对 Law of Property Act 1925 s.62 及保留与授予规则。"})]})

M.append({"id":"DMC","area":"土地 Land","zh":"公契与大厦管理","en":"DMC and building management","jurisdiction":"HK","role":"spear","role_zh":"矛",
 "top_type":"conjunctive+threshold-discretion+defence","corpus_hits":65,
 "note":"这是公契执行、共有部分分类与法团管理义务组成的事项族，不是假定所有大厦都有同一实体条款。必须读取该大厦已登记公契、第一份转让、有效决议及 Cap 344。Centre Chase [2026] HKCFA 26 是法团 s.18(1)(c) 义务及 waiver／acquiescence 的现行控制性权威。",
 "jurisdiction_rules":{"HK":"法团成立后，与共有部分有关的业主权利、权力、特权及职责原则上由法团依 s.16 行使；公契、第一份转让及 Cap 344 共同决定分类、义务、权限与救济。"},
 "authorities":[
   A("Building Management Ordinance","Cap 344 ss.2,8(2),16,18,29A,34C,34E,34F,34I,34K and Schedules","HK legislation","公契法定效力、共有部分、法团权限和管理义务","verified-primary","ss.2,8(2),16,18,29A,34C,34E,34F,34I,34K","https://www.buildingmgt.gov.hk/en/Policy_and_Legislation/3_1.html"),
   A("Kung Ming Tak Tong Co Ltd v Park Solid Enterprises Ltd","(2008) 11 HKCFAR 403","HKCFA","公契解释、共有部分及执行结构","verified-web","[18]-[20],[39]-[50]","https://babelcite.com/case/62498"),
   A("Incorporated Owners of Westlands Garden v Oey Chiou Ling","[2011] 2 HKLRD 421","HKCA","法团地位与共有部分权利","verified-web","[15]-[17],[25]-[41]","https://babelcite.com/case/75296"),
   A("Centre Chase Investment Ltd v Incorporated Owners of Castle Peak Road International Industrial Building","[2026] HKCFA 26; FACV 2/2026","HKCFA","s.18(1)(c) 的合理管理义务；批准、弃权和默许的边界","verified-primary","[4]-[13],[40]-[59],[67]-[70],[82]-[85]","https://legalref.judiciary.hk/lrs/common/ju/ju_frame.jsp?DIS=181958")],
 "stages":[
  S("BM-1","公契义务、共有部分与适格主体","DMC obligation, common parts and standing","conjunctive",
    "须根据已登记公契、第一份转让及 Cap 344 分类涉案位置或权利，识别明示条款或法定加入／当作违反公契的义务，证明相关行为，并确认由法团或其他适格主体执行。违法建筑及公共安全要求须另作硬性审查。",
    [F("BM-instrument","已取得并解释有效注册公契与第一份转让","Registered DMC and first assignment obtained and construed",required=True),
     F("BM-bound-party","相关业主、占用人或法团受该义务约束或有权执行","Relevant party is bound or entitled to enforce",required=True),
     F("BM-classification","涉案位置或权利已分类为专有、共有或获指定专用","Area or right classified as exclusive, common or designated-use",required=True),
     F("BM-obligation","已识别明示条款或 Cap 344 的适用义务","Express covenant or applicable Cap 344 obligation identified",required=True),
     F("BM-conduct","转用、占用、阻塞、失修或其他实际行为已证明","Relevant conversion, occupation, obstruction, disrepair or conduct proved",required=True),
     F("BM-breach","该行为落入所识别义务的违反范围","Conduct falls within the identified breach",required=True),
     F("BM-standing","法团或其他申请人具备适格性及权限","Applicant has standing and authority",required=True),
      F("BM-legality","违法建筑、公共安全及健康问题已独立核对","Illegality, public safety and health separately checked",role="scope-check")]),
  S("BM-2","法团执行义务与管理裁量","IO enforcement duty and managerial discretion","threshold-discretion",
    "当 s.18(1)(c) 的公契控制、管理或行政义务被触发，管委会须认真并合理考虑投诉。法律不要求每宗投诉立即全面诉讼；法团可按具体情况调查、要求纠正、分阶段行动、和解、部分执行、暂缓、弃权或默许，但须在权限内、善意并以合理方式决定。",
    [F("BM-duty-engaged","投诉涉及法团为控制、管理或行政大厦而须执行的公契义务","Section 18(1)(c) management duty is engaged",gate=True),
     F("BM-type","违反事项的性质及法律依据","Nature and legal basis of breach",role="discretion"),
     F("BM-seriousness","严重性、持续时间及实际影响","Seriousness, duration and practical impact",role="discretion"),
     F("BM-safety","违法、公共安全或健康风险","Illegality, public safety or health risk",role="discretion"),
     F("BM-common-interest","全体业主及管理目的","Collective interests and management purpose",role="discretion"),
     F("BM-consistency","类似个案的一致处理及整体公平","Consistency and overall fairness",role="discretion"),
     F("BM-resources","成本、业主负担、人员及时间","Cost, owner burden, staff and time",role="discretion"),
     F("BM-options","调查、纠正、和解、分阶段行动及成功机会","Available responses and prospects",role="discretion"),
     F("BM-governance","权限、决议、资料、理由、善意与合理过程","Authority, resolutions, information, reasons and good-faith process",role="discretion")]),
  S("BM-3","批准、弃权与默许","Approval, waiver and acquiescence","disjunctive-gateway",
    "共有部分转作自用可按 s.34I 经所需有效决议批准。除违法或公共安全事项外，普通私法的 waiver 或 acquiescence 可对法团适用，但迟延本身不会自动成立；必须证明所援引抗辩的通常要件及具体范围，并复核管理决定是否认真、合理。",
    [F("BM-valid-resolution","有权限机关以有效决议批准具体使用","Valid authorised resolution approves the particular use",evidence="权限、法定人数、表决、批准范围及期间"),
     F("BM-waiver","弃权的通常要件就具体权利成立","Ordinary elements of waiver are established",evidence="知悉、明确选择或具法律意义的行为及范围"),
     F("BM-acquiescence","默许的通常要件就具体行为成立","Ordinary elements of acquiescence are established",evidence="知悉、表示或不作为、信赖、不公平及范围")],
    jurisdiction_rules={"HK":"Centre Chase 否定法团一概无权弃权的旧线；涉及违法、公共安全或健康的事项不能藉私法弃权规避。"})]})

DOCTRINAL_ROLES = {
    "CONTRACT": {"CT-1": "claim-elements", "CT-2": "internal-test", "CT-3": "remedy"},
    "PENALTY": {"PEN-1": "defence", "PEN-2": "defence"},
    "NMS": {"NMS-1": "claim-elements", "NMS-2": "claim-elements", "NMS-3": "claim-elements"},
    "PE": {"PE-1": "claim-elements", "PE-2": "internal-test", "PE-3": "remedy"},
    "CICT": {"CICT-1": "claim-elements", "CICT-2": "quantification"},
    "RT": {"RT-1": "claim-elements", "RT-2": "rebuttal"},
    "AP": {"AP-1": "claim-elements", "AP-2": "internal-test"},
    "EASE": {"EA-1": "claim-elements", "EA-2": "claim-elements", "EA-3": "internal-test", "EA-4": "internal-test"},
    "DMC": {"BM-1": "claim-elements", "BM-2": "internal-test", "BM-3": "defence"},
    "NUIS": {
        "NU-1": "claim-elements", "NU-2": "claim-elements", "NU-3": "claim-elements",
        "NU-4": "internal-test", "NU-5": "claim-elements", "NU-6": "defence", "NU-7": "remedy",
    },
    "ILLEG": {"IL-1": "defence"},
    "UI": {"UI-1": "claim-elements", "UI-2": "claim-elements", "UI-3": "rebuttal"},
    "LEASE": {"LS-1": "internal-test", "LS-2": "internal-test"},
    "NYC": {"NY-1": "defence", "NY-2": "procedure-gateway", "NY-3": "procedure-discretion"},
    "ARBCH": {"AC-1": "procedure-gateway"},
    "LPP": {"LPP-1": "procedure-gateway", "LPP-2": "procedure-gateway", "LPP-3": "procedure-gateway", "LPP-4": "rebuttal"},
    "DISC": {"DS-1": "procedure-gateway", "DS-2": "procedure-discretion", "DS-3": "procedure-duty"},
    "CECO": {"CE-1": "internal-test"},
    "VEIL": {"VL-1": "internal-test", "VL-2": "internal-test"},
}

for module in M:
    roles = DOCTRINAL_ROLES.get(module["id"], {})
    stage_ids = {stage["id"] for stage in module["stages"]}
    if set(roles) != stage_ids:
        raise ValueError("doctrinal role map mismatch for " + module["id"])
    for stage in module["stages"]:
        stage["doctrinal_role"] = roles[stage["id"]]
    enrich_module(module)

REG={"generated":"2026-09-10","version":"0.5",
 "principle":"每个判断阶段先按 test_type 分类；只有多因素权衡使用数值份量区间。诉讼姿态（矛／盾）与事项轨道（实体／程序／管辖）分别记录，均不是法律要件。hklandlaw 计数只表示语料覆盖，不决定判断逻辑、权威等级或权重。",
 "test_types":TEST_TYPES,
 "posture_catalog":POSTURE_CATALOG,
 "track_catalog":TRACK_CATALOG,
 "doctrinal_role_catalog":DOCTRINAL_ROLE_CATALOG,
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
