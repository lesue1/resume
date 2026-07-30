"""
 tests/test_ai_scorer.py — AI 评分模块单元测试
=================================================
覆盖核心逻辑：Prompt 构造、JSON 解析、分数计算、异常分数拦截。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from ai_scorer import build_prompt, parse_response, calculate_score, _find_json_end


# ═══════════════════════════════════════════════════════════
# Prompt 构造测试
# ═══════════════════════════════════════════════════════════

def test_build_prompt_includes_jd_and_resume():
    messages = build_prompt("招 Python 后端", "张三 | Python 3年")
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    # 简历内容应被 <resume> 包裹（防注入）
    assert "<resume>" in messages[1]["content"]
    assert "</resume>" in messages[1]["content"]
    assert "张三" in messages[1]["content"]
    assert "招 Python 后端" in messages[1]["content"]


def test_build_prompt_handles_empty_jd():
    messages = build_prompt("", "简历内容")
    assert "（未提供岗位描述" in messages[1]["content"]


def test_build_prompt_handles_empty_resume():
    messages = build_prompt("JD内容", "")
    # 空简历也应该有 <resume> 标签
    assert "<resume>" in messages[1]["content"]
    assert "</resume>" in messages[1]["content"]


# ═══════════════════════════════════════════════════════════
# JSON 解析测试
# ═══════════════════════════════════════════════════════════

def test_parse_valid_json():
    result = parse_response('{"技能匹配度": {"score": 85, "reason": "不错"}}')
    assert result is not None
    assert result["技能匹配度"]["score"] == 85


def test_parse_markdown_wrapped_json():
    result = parse_response('```json\n{"技能匹配度": {"score": 70}}\n```')
    assert result is not None
    assert result["技能匹配度"]["score"] == 70


def test_parse_json_with_prefix_text():
    result = parse_response('这是评语：\n{"技能匹配度": {"score": 60}}')
    assert result is not None
    assert result["技能匹配度"]["score"] == 60


def test_parse_invalid_json_returns_none():
    result = parse_response("这不是 JSON")
    assert result is None


def test_parse_empty_returns_none():
    result = parse_response("")
    assert result is None


def test_parse_none_returns_none():
    result = parse_response(None)
    assert result is None


# ═══════════════════════════════════════════════════════════
# JSON 边界查找测试（_find_json_end）
# ═══════════════════════════════════════════════════════════

def test_find_json_end_simple():
    end = _find_json_end('{"a": 1}', 0)
    assert end == len('{"a": 1}') - 1


def test_find_json_end_nested():
    end = _find_json_end('{"a": {"b": 2}}', 0)
    assert end == len('{"a": {"b": 2}}') - 1


def test_find_json_end_with_string_braces():
    end = _find_json_end('{"a": "hello { world }"}', 0)
    assert end == len('{"a": "hello { world }"}') - 1


def test_find_json_end_not_found():
    end = _find_json_end('{"a": 1', 0)
    assert end == -1


# ═══════════════════════════════════════════════════════════
# 分数计算测试
# ═══════════════════════════════════════════════════════════

def test_calculate_perfect_score():
    scores = {
        "技能匹配度": {"score": 100},
        "经验相关性": {"score": 100},
        "学历匹配度": {"score": 100},
        "项目成果质量": {"score": 100},
        "稳定性成长性": {"score": 100},
    }
    # 权重: 40 + 25 + 15 + 10 + 10 = 100 → perfect = 100
    assert calculate_score(scores) == 100.0


def test_calculate_weighted_average():
    scores = {
        "技能匹配度": {"score": 80},   # 80 × 0.40 = 32.0
        "经验相关性": {"score": 70},   # 70 × 0.25 = 17.5
        "学历匹配度": {"score": 60},   # 60 × 0.15 = 9.0
        "项目成果质量": {"score": 50}, # 50 × 0.10 = 5.0
        "稳定性成长性": {"score": 40}, # 40 × 0.10 = 4.0
    }
    # 32 + 17.5 + 9 + 5 + 4 = 67.5
    score = calculate_score(scores)
    assert abs(score - 67.5) < 0.01


def test_calculate_clamp_out_of_range():
    """分数超出 0-100 会被 clamp。"""
    scores = {
        "技能匹配度": {"score": 150},  # → 100
        "经验相关性": {"score": -10},  # → 0
        "学历匹配度": {"score": 50},
        "项目成果质量": {"score": 50},
        "稳定性成长性": {"score": 50},
    }
    # 100×0.40 + 0×0.25 + 50×0.15 + 50×0.10 + 50×0.10
    # = 40 + 0 + 7.5 + 5 + 5 = 57.5
    score = calculate_score(scores)
    assert abs(score - 57.5) < 0.01


def test_calculate_missing_dimension_defaults_zero():
    """AI 没返回某个维度 → 默认 0 分。"""
    scores = {
        "技能匹配度": {"score": 80},
        "经验相关性": {"score": 70},
        "学历匹配度": {"score": 60},
        # 项目成果质量 和 稳定性成长性 缺失 → 0
    }
    # 80×0.40 + 70×0.25 + 60×0.15 + 0×0.10 + 0×0.10
    # = 32 + 17.5 + 9 = 58.5
    assert abs(calculate_score(scores) - 58.5) < 0.01


def test_calculate_non_dict_dimension():
    """维度值不是 dict → 视为 0。"""
    scores = {
        "技能匹配度": None,
        "经验相关性": "不是 dict",
        "学历匹配度": {"score": 50},
        "项目成果质量": {"score": 50},
        "稳定性成长性": {"score": 50},
    }
    # 前两个维度 → 0, 后面三个 50: 0×0.40 + 0×0.25 + 50×0.15 + 50×0.10 + 50×0.10
    # = 0 + 0 + 7.5 + 5 + 5 = 17.5
    assert abs(calculate_score(scores) - 17.5) < 0.01


# ═══════════════════════════════════════════════════════════
# 直接运行
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
