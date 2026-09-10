# -*- coding: utf-8 -*-
"""Canonical metadata for typed legal-test logic.

Machine identifiers are stable API values.  Chinese labels describe the legal
aggregation rule; numeric weights are only an implementation detail of the
``balancing`` type.
"""

CANONICAL_TEST_TYPE_IDS = (
    "conjunctive",
    "disjunctive-gateway",
    "balancing",
    "threshold-discretion",
    "presumption-rebuttal",
)

TEST_TYPES = {
    "conjunctive": {
        "zh": "合取要件",
        "en": "All required elements must be satisfied (AND)",
        "scoring": "不计分；逐项确认必要要件",
        "output": "缺失要件清单",
        "examples": ["misrepresentation E1–E5", "deceit"],
    },
    "disjunctive-gateway": {
        "zh": "择一门槛",
        "en": "At least one item from a closed list (OR)",
        "scoring": "记录成立项；最强项供后续裁量参考",
        "output": "已打开的门槛",
        "examples": [
            "RHC O.11 r.1(1) service-out gateways",
            "NY Convention Art V grounds",
        ],
    },
    "balancing": {
        "zh": "多因素权衡",
        "en": "Multi-factor balance; no single factor is automatically decisive",
        "scoring": "正向因素合计减反向因素合计，并传播事实与份量区间",
        "output": "情景区间、关键摇摆因素、待补证据",
        "examples": [
            "forum non conveniens",
            "lease vs licence",
            "CECO s.3(1) reasonableness",
        ],
    },
    "threshold-discretion": {
        "zh": "门槛后裁量",
        "en": "Threshold first, followed by a separate discretion",
        "scoring": "门槛与裁量分成两个阶段判断",
        "output": "门槛结果、裁量结果",
        "examples": ["exclusive jurisdiction clause — strong cause"],
    },
    "presumption-rebuttal": {
        "zh": "推定与反驳",
        "en": "Trigger a presumption, shift the evidential burden, then test rebuttal",
        "scoring": "分别记录触发、责任转移与反驳；不把推定换算成权重",
        "output": "推定状态、举证责任、反驳结果",
        "examples": ["presumed undue influence", "resulting trust presumptions"],
    },
}

SOURCE_CATALOG = {
    "hklandlaw": {
        "label": "hklandlaw",
        "domain": "hklandlaw.wordpress.com",
        "unit": "article",
        "unit_zh": "篇",
        "description": "语料文章覆盖数；不是判断逻辑、权威等级或模型权重。",
    }
}


# Litigation position is deliberately separate from legal-test logic.  A
# module may be used in more than one pleading posture, while procedure and
# jurisdiction describe the track on which the issue is decided rather than a
# competing posture.
POSTURE_CATALOG = {
    "spear": {
        "zh": "矛",
        "en": "Spear",
        "description": "作为请求、反请求或程序申请主动提出。",
    },
    "shield": {
        "zh": "盾",
        "en": "Shield",
        "description": "用于回应、限制或阻却对方的请求。",
    },
}

TRACK_CATALOG = {
    "merits": {
        "zh": "实体与救济",
        "en": "Merits & remedies",
        "description": "处理权利、责任、抗辩、定性或救济。",
    },
    "procedure": {
        "zh": "程序",
        "en": "Procedure",
        "description": "处理诉讼、仲裁、承认或执行步骤。",
    },
    "jurisdiction": {
        "zh": "管辖",
        "en": "Jurisdiction",
        "description": "处理法院能否及应否审理争议。",
    },
}


# The legacy ``role`` field remains stable for API compatibility.  This table
# supplies the non-exclusive, two-axis classification used by new clients.
MODULE_LITIGATION_PROFILES = {
    "HKJUR": {
        "litigation_postures": ["spear", "shield"],
        "litigation_track": "jurisdiction",
        "primary_posture": None,
        "legal_kind": "jurisdiction-gateway",
        "role_confidence": "contextual",
        "litigation_note": "送达与主张管辖可由原告提出；暂缓或管辖异议通常由被告提出，具体举证责任随阶段改变。",
    },
    "CONTRACT": {
        "litigation_postures": ["spear", "shield"],
        "litigation_track": "merits",
        "primary_posture": "spear",
        "legal_kind": "cause-of-action",
        "role_confidence": "typical",
        "litigation_note": "违约通常作为请求或反请求提出；损害远隔性等内部争点可用于限制赔偿。",
    },
    "PE": {
        "litigation_postures": ["shield", "spear"],
        "litigation_track": "merits",
        "primary_posture": "shield",
        "legal_kind": "equitable-doctrine",
        "role_confidence": "contextual",
        "litigation_note": "可作为独立请求寻求确认或衡平救济，也可在管有或执行争议中作为抗辩；“盾而非矛”通常指允诺禁反言。",
    },
    "CICT": {
        "litigation_postures": ["spear", "shield"],
        "litigation_track": "merits",
        "primary_posture": "spear",
        "legal_kind": "proprietary-doctrine",
        "role_confidence": "contextual",
        "litigation_note": "通常用于主动确认实益权益，也可在管有、出售或受益权争议中作为抗辩或反请求。",
    },
    "RT": {
        "litigation_postures": ["spear", "shield"],
        "litigation_track": "merits",
        "primary_posture": "spear",
        "legal_kind": "evidential-presumption",
        "role_confidence": "contextual",
        "litigation_note": "一方可主张归复信托推定，另一方可提出赠与或其他证据反驳；姿态与举证责任随阶段变化。",
    },
    "AP": {
        "litigation_postures": ["spear", "shield"],
        "litigation_track": "merits",
        "primary_posture": "spear",
        "legal_kind": "title-doctrine",
        "role_confidence": "contextual",
        "litigation_note": "可用于申请登记或确认权利，也可在业主收回管有的诉讼中作为抗辩；具体路径取决于法域及登记制度。",
    },
    "NUIS": {
        "litigation_postures": ["spear", "shield"],
        "litigation_track": "merits",
        "primary_posture": "spear",
        "legal_kind": "cause-of-action",
        "role_confidence": "typical",
        "litigation_note": "私人妨害由土地权益人作为诉因主动提出；被告可在责任边界及抗辩阶段抵抗请求，法院在责任成立后选择救济。",
    },
    "ILLEG": {
        "litigation_postures": ["shield"],
        "litigation_track": "merits",
        "primary_posture": "shield",
        "legal_kind": "defence",
        "role_confidence": "typical",
    },
    "UI": {
        "litigation_postures": ["shield", "spear"],
        "litigation_track": "merits",
        "primary_posture": "shield",
        "legal_kind": "avoidance-doctrine",
        "role_confidence": "contextual",
        "litigation_note": "可主动请求撤销交易，也可在管有或执行程序中抵抗执行。",
    },
    "LEASE": {
        "litigation_postures": ["spear", "shield"],
        "litigation_track": "merits",
        "primary_posture": None,
        "legal_kind": "classification",
        "role_confidence": "contextual",
        "litigation_note": "租赁或许可是前提定性争点，不是独立诉因；争议双方都可能援引。",
    },
    "NYC": {
        "litigation_postures": ["shield"],
        "litigation_track": "procedure",
        "primary_posture": "shield",
        "legal_kind": "enforcement-defence",
        "role_confidence": "explicit",
        "litigation_note": "第 V(1) 条拒绝事由由被申请人提出并举证；第 V(2) 条的可仲裁性与公共政策可由法院主动审查。",
    },
    "ARBCH": {
        "litigation_postures": ["spear"],
        "litigation_track": "procedure",
        "primary_posture": "spear",
        "legal_kind": "application",
        "role_confidence": "typical",
        "litigation_note": "由挑战方在仲裁程序中主动提出回避申请。",
    },
    "CECO": {
        "litigation_postures": ["spear", "shield"],
        "litigation_track": "merits",
        "primary_posture": None,
        "legal_kind": "statutory-control",
        "role_confidence": "contextual",
        "litigation_note": "用于审查并可能击破免责条款；提出免责的一方与反对免责的一方都会围绕合理性使用本测试。",
    },
    "VEIL": {
        "litigation_postures": ["spear"],
        "litigation_track": "merits",
        "primary_posture": "spear",
        "legal_kind": "supporting-doctrine",
        "role_confidence": "typical",
        "litigation_note": "揭开公司面纱依附于既存义务或责任，是极有限的归责原则，并非独立诉因。",
    },
}


def _stage_position(postures, primary_posture, litigation_note, court_own_motion=False):
    """Build one explicit stage-level litigation-position record."""
    return {
        "litigation_postures": postures,
        "primary_posture": primary_posture,
        "court_own_motion": court_own_motion,
        "litigation_note": litigation_note,
    }


# Stage positions identify who ordinarily invokes or carries the issue at that
# point in the legal test.  They do not encode which factual result the stage
# favours.  Every current stage is listed so a new stage cannot silently inherit
# a potentially inaccurate module-level posture.
STAGE_LITIGATION_POSITIONS = {
    "HKJUR": {
        "HKJUR-1": _stage_position(
            ["spear"], "spear",
            "主张香港管辖及申请域外送达的一方须指出适用的送达门槛。",
        ),
        "HKJUR-2": _stage_position(
            ["shield"], "shield",
            "申请暂缓或提出不方便法院异议的一方，以此阶段抵抗在香港继续审理。",
        ),
        "HKJUR-3": _stage_position(
            ["spear"], "spear",
            "原请求方可证明转往替代法院会丧失正当司法利益，以维持其香港诉讼。",
        ),
        "HKJUR-4": _stage_position(
            ["spear", "shield"], None,
            "管辖条款可用于主动申请暂缓或禁诉，也可用于抵抗在非约定法院继续审理；法院另行行使裁量。",
        ),
    },
    "CONTRACT": {
        "CT-1": _stage_position(
            ["spear"], "spear", "请求违约救济的一方须证明合同、条款、违反、因果关系与损失。",
        ),
        "CT-2": _stage_position(
            ["spear"], "spear", "无辜方以条款定性及违约后果支持终止、拒绝履行或损害赔偿请求。",
        ),
        "CT-3": _stage_position(
            ["shield"], "shield", "违约方通常以损害远隔性限制请求方可获赔偿的范围。",
        ),
    },
    "PE": {
        "PE-1": _stage_position(
            ["shield", "spear"], None, "三要件既可支持独立衡平请求，也可用于抵抗严格法律权利的执行。",
        ),
        "PE-2": _stage_position(
            ["shield", "spear"], None, "整体不合情理性判断沿用该禁反言在具体案件中的请求或抗辩姿态。",
        ),
        "PE-3": _stage_position(
            ["spear", "shield"], "spear", "主张衡平的一方通常请求法院量定救济；作为抗辩成立时法院亦会调整最终命令。",
        ),
    },
    "CICT": {
        "CICT-1": _stage_position(
            ["spear", "shield"], "spear", "可主动请求确认实益权益，也可用该权益抵抗管有、出售或处分请求。",
        ),
        "CICT-2": _stage_position(
            ["spear", "shield"], "spear", "份额量化承接已主张的实益权益，诉答姿态取决于请求或反请求的结构。",
        ),
    },
    "RT": {
        "RT-1": _stage_position(
            ["spear", "shield"], None, "当事人可主动主张归复信托推定，也可凭该推定抵抗登记业权人的请求。",
        ),
        "RT-2": _stage_position(
            ["shield", "spear"], "shield", "反驳方以赠与、借贷或同期证据抵抗推定所支持的实益权益主张。",
        ),
    },
    "AP": {
        "AP-1": _stage_position(
            ["spear", "shield"], "spear", "占有人可申请确认或登记权利，也可在纸面业主收回管有时提出抗辩。",
        ),
        "AP-2": _stage_position(
            ["spear", "shield"], "spear", "事实占有因素服务于同一权利主张或管有抗辩，不另行改变姿态。",
        ),
    },
    "NUIS": {
        "NU-1": _stage_position(
            ["spear"], "spear", "原告须证明其享有受私人妨害保护的土地权益，并且所诉干扰针对土地利益。",
        ),
        "NU-2": _stage_position(
            ["spear"], "spear", "原告须把所诉损害置于侵占、物理损害或舒适便利干扰的一项受承认路径。",
        ),
        "NU-3": _stage_position(
            ["spear", "shield"], "spear", "原告须证明既有实际干扰或损害；请求预防性救济时，须证明适用法所要求的迫近威胁。",
        ),
        "NU-4": _stage_position(
            ["spear", "shield"], None, "原告证明舒适便利干扰达到客观实质门槛；被告可援引普通通常且适当顾及邻地的互惠边界。",
        ),
        "NU-5": _stage_position(
            ["spear", "shield"], "spear", "原告承担归责、可诉损害或迫近危害、因果与可预见性的证明责任；被告可否认任何必要环节。",
        ),
        "NU-6": _stage_position(
            ["shield"], "shield", "被告承担证明法定授权、时效权利、同意或其他适用抗辩的责任。",
        ),
        "NU-7": _stage_position(
            ["spear", "shield"], None, "既有责任或预防性救济门槛成立后，双方可就禁制令、赔偿、减除费用及公共利益对救济选择的影响陈词。",
        ),
    },
    "ILLEG": {
        "IL-1": _stage_position(
            ["shield"], "shield", "被请求承担责任的一方通常以违法性及比例原则阻却或限制救济。",
        ),
    },
    "UI": {
        "UI-1": _stage_position(
            ["shield", "spear"], "shield", "受影响方可抵抗交易执行，也可主动请求撤销交易。",
        ),
        "UI-2": _stage_position(
            ["shield", "spear"], "shield", "主张推定不当影响的一方须证明信任关系及需要解释的交易。",
        ),
        "UI-3": _stage_position(
            ["shield", "spear"], None, "交易受益方提出独立意见等证据反驳推定；其姿态随执行请求或撤销之诉而改变。",
        ),
    },
    "LEASE": {
        "LS-1": _stage_position(
            ["spear", "shield"], None, "租赁定性可支持占有人主动确认权利，也可抵抗收回管有或许可终止。",
        ),
        "LS-2": _stage_position(
            ["spear", "shield"], None, "实质重于形式的判断沿用定性争议的双向姿态。",
        ),
    },
    "NYC": {
        "NY-1": _stage_position(
            ["shield"], "shield", "被申请人承担举证责任，以第 V(1) 条任一封闭事由抵抗裁决的承认或执行。",
        ),
        "NY-2": _stage_position(
            [], None, "可仲裁性与执行地公共政策由执行法院依职权审查，不归入任一方的矛或盾。", True,
        ),
        "NY-3": _stage_position(
            ["shield"], "shield", "拒绝事由成立后由法院行使剩余裁量；它通常承接被申请人的执行抗辩，并非新的拒绝事由。",
        ),
    },
    "ARBCH": {
        "AC-1": _stage_position(
            ["spear"], "spear", "挑战方主动提出仲裁员回避申请，并证明存在对公正性的正当怀疑。",
        ),
    },
    "CECO": {
        "CE-1": _stage_position(
            ["spear", "shield"], None, "一方以合理性审查攻击免责条款，援引条款的一方则以其有效性抵抗责任。",
        ),
    },
    "VEIL": {
        "VL-1": _stage_position(
            ["spear"], "spear", "请求把既存义务归于公司幕后主体的一方须指出隐匿或规避原则。",
        ),
        "VL-2": _stage_position(
            ["spear"], "spear", "请求揭开公司面纱的一方还须跨过不存在足够常规替代救济的限制。",
        ),
    },
}


def ordered_logic_types(module):
    """Return canonical overall/stage types once, in explanatory order."""
    result = []
    overall = module.get("top_type")
    if overall in TEST_TYPES:
        result.append(overall)
    for stage in module.get("stages", []):
        test_type = stage.get("test_type")
        if test_type in TEST_TYPES and test_type not in result:
            result.append(test_type)
    return result


def enrich_module(module):
    """Add explicit logic, source and litigation-position metadata."""
    module["logic_types"] = ordered_logic_types(module)
    hits = module.get("corpus_hits")
    module["source_counts"] = {} if hits is None else {"hklandlaw": hits}
    profile = MODULE_LITIGATION_PROFILES.get(module.get("id"))
    if profile is None:
        raise ValueError("missing litigation profile for module " + str(module.get("id")))
    module.update(profile)
    module.pop("court_own_motion", None)
    if not module["litigation_postures"]:
        raise ValueError("litigation_postures cannot be empty for " + module["id"])
    if len(module["litigation_postures"]) != len(set(module["litigation_postures"])):
        raise ValueError("duplicate module litigation posture for " + module["id"])
    if any(posture not in POSTURE_CATALOG for posture in module["litigation_postures"]):
        raise ValueError("unknown litigation posture for " + module["id"])
    if (module.get("primary_posture") is not None
            and module["primary_posture"] not in module["litigation_postures"]):
        raise ValueError("module primary_posture must be one of litigation_postures for " + module["id"])
    if module["litigation_track"] not in TRACK_CATALOG:
        raise ValueError("unknown litigation track for " + module["id"])

    module_id = module["id"]
    positions = STAGE_LITIGATION_POSITIONS.get(module_id)
    if positions is None:
        raise ValueError("missing stage litigation positions for module " + module_id)
    stage_ids = [stage.get("id") for stage in module.get("stages", [])]
    if len(stage_ids) != len(set(stage_ids)):
        raise ValueError("duplicate stage id in module " + module_id)
    if set(stage_ids) != set(positions):
        missing = sorted(set(stage_ids) - set(positions))
        stale = sorted(set(positions) - set(stage_ids))
        raise ValueError(
            "stage litigation position mismatch for " + module_id
            + "; missing=" + str(missing) + "; stale=" + str(stale)
        )
    own_motion_stage_ids = []
    stage_postures = set()
    for stage in module["stages"]:
        position = positions[stage["id"]]
        postures = position.get("litigation_postures")
        primary = position.get("primary_posture")
        own_motion = position.get("court_own_motion")
        note = position.get("litigation_note")
        if not isinstance(postures, list):
            raise ValueError("litigation_postures must be a list for " + stage["id"])
        if len(postures) != len(set(postures)):
            raise ValueError("duplicate litigation posture for " + stage["id"])
        if any(posture not in POSTURE_CATALOG for posture in postures):
            raise ValueError("unknown litigation posture for " + stage["id"])
        if not isinstance(own_motion, bool):
            raise ValueError("court_own_motion must be boolean for " + stage["id"])
        if not postures and not own_motion:
            raise ValueError("empty litigation_postures require court_own_motion for " + stage["id"])
        if primary is not None and primary not in postures:
            raise ValueError("primary_posture must be one of litigation_postures for " + stage["id"])
        if not isinstance(note, str) or not note.strip():
            raise ValueError("litigation_note cannot be empty for " + stage["id"])
        stage.update({
            "litigation_postures": list(postures),
            "litigation_track": module["litigation_track"],
            "primary_posture": primary,
            "court_own_motion": own_motion,
            "litigation_note": note,
        })
        stage_postures.update(postures)
        if own_motion:
            own_motion_stage_ids.append(stage["id"])
    if stage_postures != set(module["litigation_postures"]):
        raise ValueError("module litigation_postures do not summarize stages for " + module_id)
    module["court_own_motion_summary"] = {
        "stage_count": len(own_motion_stage_ids),
        "stage_ids": own_motion_stage_ids,
    }
    return module
