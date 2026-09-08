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
    """Add explicit logic and source metadata without removing legacy fields."""
    module["logic_types"] = ordered_logic_types(module)
    hits = module.get("corpus_hits")
    module["source_counts"] = {} if hits is None else {"hklandlaw": hits}
    return module
