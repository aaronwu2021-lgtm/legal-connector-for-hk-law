# -*- coding: utf-8 -*-
import json

from _paths import emit

E = "editorial-prior"; U = "unassigned"
def F(i,zh,en,w=None,ev=None,note=None):
    d={"id":i,"zh":zh,"en":en,"weight":w,"evidence":ev}
    if note: d["note"]=note
    if w is None: d["weight_status"]=U
    return d
def S(i,zh,en,tt,rule,factors,ws=None,cf=None,note=None):
    d={"id":i,"zh":zh,"en":en,"test_type":tt,"rule":rule,"factors":factors}
    if ws: d["weight_source"]=ws
    if cf: d["counter_factors"]=cf
    if note: d["weight_note"]=note
    return d
def A(c,cite,court,role,v="unverified"): return {"case":c,"cite":cite,"court":court,"role":role,"verified":v}

M=[]

M.append({"id":"CONTRACT","area":"合同 Contract","zh":"违约","en":"Breach of contract","jurisdiction":"EN/HK/SG",
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

M.append({"id":"PE","area":"衡平 Equity","zh":"财产禁反言","en":"Proprietary estoppel","jurisdiction":"EN/HK/SG",
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

M.append({"id":"CICT","area":"衡平 Equity","zh":"共同意图推定信托","en":"Common intention constructive trust","jurisdiction":"EN/HK/SG",
 "top_type":"conjunctive+balancing","corpus_hits":134,
 "note":"成立是合取,量化是权重衡量(整体交易过程)。语料里出现频次第四。",
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

M.append({"id":"RT","area":"衡平 Equity","zh":"归复信托与预付推定","en":"Resulting trust / presumption of advancement","jurisdiction":"EN/HK/SG",
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

M.append({"id":"AP","area":"土地 Land","zh":"逆权占有","en":"Adverse possession","jurisdiction":"HK/EN",
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

M.append({"id":"NUIS","area":"侵权 Tort","zh":"私人妨害","en":"Private nuisance","jurisdiction":"EN/HK/SG",
 "top_type":"balancing","corpus_hits":11,
 "note":"典型的权重衡量:是否合理使用,由多因素综合。此处给出编者先验。",
 "authorities":[A("Fearn v Tate Gallery","[2023] UKSC 4","UKSC","普通使用与视觉侵扰"),
   A("Cambridge Water v Eastern Counties Leather","[1994] 2 AC 264","HL","可预见性")],
 "stages":[
  S("NU-1","是否构成不合理干扰","Unreasonable interference","balancing",
    "综合地点性质、干扰程度与持续时间、时间段、原告是否异常敏感、被告是否恶意、社会效用。",
    [F("NU-locality","地点性质","Character of the locality",0.22,"分区用途;周边实际状况"),
     F("NU-severity","干扰的强度","Severity of the interference",0.22,"测量数据;证人证言"),
     F("NU-duration","持续时间与频率","Duration and frequency",0.18,"日志;时间记录"),
     F("NU-timing","发生时段","Time of day",0.10,"记录"),
     F("NU-malice","被告恶意","Malice on the defendant's part",0.16,"通讯记录",
       "有恶意时权重显著上升,可使本属合理的使用变为不合理"),
     F("NU-utility","社会效用","Social utility of the defendant's activity",0.12,"用途证据")],
    ws=E, cf=[F("NU-sensitivity","原告异常敏感","Abnormal sensitivity of the claimant",-0.20,"用途异常性"),
              F("NU-common-use","被告属土地的普通使用","Ordinary use of land (Fearn)",-0.25,"同区可比用法")],
    note="先验依据学理常见排序,未经回归校准。")]})

M.append({"id":"ILLEG","area":"合同 Contract","zh":"违法性抗辩","en":"Illegality (Patel v Mirza)","jurisdiction":"EN/HK/SG",
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

M.append({"id":"UI","area":"衡平 Equity","zh":"不当影响","en":"Undue influence","jurisdiction":"EN/HK/SG",
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

M.append({"id":"LEASE","area":"土地 Land","zh":"租赁抑或许可","en":"Lease or licence","jurisdiction":"HK/EN/SG",
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

M.append({"id":"NYC","area":"仲裁 Arbitration","zh":"纽约公约执行抗辩","en":"Enforcement — NY Convention Art V","jurisdiction":"HK/SG/EN",
 "top_type":"disjunctive-gateway","corpus_hits":0,
 "note":"全法律里最天然的机器可读要件表:封闭清单,任一项成立即可拒绝执行,举证责任在被申请人(V(2) 除外)。",
 "authorities":[A("New York Convention 1958 Art V","—","—","封闭的拒绝执行事由清单"),
   A("Hebei Import & Export v Polytek Engineering","(1999) 2 HKCFAR 111","CFA","香港公共政策标准")],
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

M.append({"id":"ARBCH","area":"仲裁 Arbitration","zh":"仲裁员回避","en":"Arbitrator challenge","jurisdiction":"HK/SG/EN",
 "top_type":"balancing","corpus_hits":0,
 "note":"示范法 art 12 的「正当怀疑」是客观旁观者标准,典型的权重衡量。",
 "authorities":[A("UNCITRAL Model Law art 12","—","—","正当怀疑标准"),
   A("Halliburton v Chubb","[2020] UKSC 48","UKSC","多重委任与披露义务"),
   A("Arbitration Ordinance","Cap 609","—","香港采纳示范法")],
 "stages":[
  S("AC-1","正当怀疑","Justifiable doubts","balancing",
    "客观、知情的旁观者是否会认为存在对公正性的真实可能怀疑。",
    [F("AC-multiple-appointments","重叠委任","Overlapping appointments"),
     F("AC-nondisclosure","未披露本应披露的事项","Failure to disclose"),
     F("AC-financial","财务利益","Financial interest"),
     F("AC-relationship","与一方或代理人的关系","Relationship with a party or counsel"),
     F("AC-prior-views","就同一争点已表达立场","Previously expressed views"),
     F("AC-market-practice","该领域的惯常做法","Custom of the particular field")])]})

M.append({"id":"CECO","area":"合同 Contract","zh":"免责条款合理性","en":"Reasonableness of an exemption clause","jurisdiction":"HK",
 "top_type":"balancing","corpus_hits":0,
 "note":"直接接住失实陈述模块的 D1 抗辩:Cap 284 s.4 把 non-reliance 条款送进 Cap 71 s.3(1) 的合理性审查。",
 "authorities":[A("Control of Exemption Clauses Ordinance","Cap 71 s.3(1) & Sch 2","—","合理性要求与指引清单"),
   A("Chang Pui Yin v Bank of Singapore","[2017] 4 HKLRD 458","HKCA","对非成熟客户条款不合理","web"),
   A("Green Park Properties v Dorku","(2001) 4 HKCFAR 448","CFA","整体协议条款未过合理性","web")],
 "stages":[
  S("CE-1","合理性","Reasonableness","balancing",
    "订约时是否为公平合理的条款,参照双方议价能力、是否获诱因、是否知悉、履行可行性等。",
    [F("CE-bargaining","议价能力对比","Relative bargaining strength"),
     F("CE-inducement","是否因接受条款而获诱因","Inducement to agree"),
     F("CE-knowledge","是否知悉或应知条款存在","Knowledge of the term"),
     F("CE-practicable","履行条件是否实际可行","Practicability of compliance"),
     F("CE-bespoke","是否为特别订制的货品","Special order goods"),
     F("CE-sophistication","客户成熟程度","Sophistication of the customer")])]})

M.append({"id":"VEIL","area":"公司 Company","zh":"揭开公司面纱","en":"Piercing the corporate veil","jurisdiction":"EN/HK/SG",
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

REG={"generated":"2026-08-25","version":"0.2",
 "principle":"分类(test_type)由学理支持,可核验;权重是编者先验,须回归校准。未赋权重的因素自动进入维护队列。",
 "modules":M}
emit('registry', REG, indent=1)
n_f=sum(len(s.get('factors',[]))+len(s.get('counter_factors',[])) for m in M for s in m['stages'])
n_w=sum(1 for m in M for s in m['stages'] for f in s.get('factors',[])+s.get('counter_factors',[]) if f.get('weight') is not None)
print(f"modules: {len(M)}  stages: {sum(len(m['stages']) for m in M)}  factors: {n_f}")
print(f"weighted: {n_w}  unassigned: {n_f-n_w}  ({100*(n_f-n_w)//n_f}% 待校准)")
import collections
print("test_type 分布:", dict(collections.Counter(s['test_type'] for m in M for s in m['stages'])))
