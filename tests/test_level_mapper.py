"""
测试：语言等级映射系统 — CEFR ↔ HSK
"""
from src.services.level_mapper import (
    CEFRLevel,
    HSKLevel,
    get_level_gap,
    hsk_to_cefr,
    cefr_to_hsk,
    get_level_descriptor,
    CEFR_DESCRIPTORS,
    HSK_DESCRIPTORS,
    CEFR_TO_HSK,
    HSK_TO_CEFR,
    LEVEL_NUMERIC,
    ASSESSMENT_DIMENSIONS,
)


class TestLevelEnums:
    def test_cefr_levels_order(self):
        """CEFR 等级顺序正确"""
        levels = [CEFRLevel.A1, CEFRLevel.A2, CEFRLevel.B1,
                   CEFRLevel.B2, CEFRLevel.C1, CEFRLevel.C2]
        assert levels[0] == "A1"
        assert levels[-1] == "C2"
        assert len(levels) == 6

    def test_hsk_levels_order(self):
        """HSK 等级顺序正确"""
        levels = [HSKLevel.HSK1, HSKLevel.HSK2, HSKLevel.HSK3,
                   HSKLevel.HSK4, HSKLevel.HSK5, HSKLevel.HSK6]
        assert levels[0] == "HSK1"
        assert levels[-1] == "HSK6"
        assert len(levels) == 6


class TestLevelMapping:
    def test_cefr_to_hsk_all(self):
        """CEFR → HSK 全映射"""
        assert cefr_to_hsk("A1") == "HSK1"
        assert cefr_to_hsk("A2") == "HSK2"
        assert cefr_to_hsk("B1") == "HSK3"
        assert cefr_to_hsk("B2") == "HSK4"
        assert cefr_to_hsk("C1") == "HSK5"
        assert cefr_to_hsk("C2") == "HSK6"

    def test_hsk_to_cefr_all(self):
        """HSK → CEFR 全映射"""
        assert hsk_to_cefr("HSK1") == "A1"
        assert hsk_to_cefr("HSK2") == "A2"
        assert hsk_to_cefr("HSK3") == "B1"
        assert hsk_to_cefr("HSK4") == "B2"
        assert hsk_to_cefr("HSK5") == "C1"
        assert hsk_to_cefr("HSK6") == "C2"

    def test_roundtrip_mapping(self):
        """CEFR → HSK → CEFR 往返一致"""
        for cefr in ["A1", "A2", "B1", "B2", "C1", "C2"]:
            hsk = cefr_to_hsk(cefr)
            back = hsk_to_cefr(hsk)
            assert back == cefr, f"Roundtrip failed for {cefr}: got {back}"

    def test_invalid_input(self):
        """无效输入返回 None"""
        assert cefr_to_hsk("D1") is None
        assert cefr_to_hsk("") is None
        assert hsk_to_cefr("HSK0") is None
        assert hsk_to_cefr("B1") is None  # 不是HSK格式


class TestLevelGap:
    def test_same_level_zero_gap(self):
        """同等级差距为0"""
        assert get_level_gap("B1", "B1") == 0
        assert get_level_gap("HSK3", "HSK3") == 0

    def test_positive_gap(self):
        """目标等级更高 → 正值"""
        assert get_level_gap("A1", "C1") == 4
        assert get_level_gap("HSK1", "HSK6") == 5

    def test_negative_gap(self):
        """目标等级更低 → 负值"""
        assert get_level_gap("B2", "A1") == -3

    def test_cross_system_gap(self):
        """跨系统差距（CEFR vs HSK）"""
        # A1=1, HSK6=6 → gap=5
        assert get_level_gap("A1", "HSK6") == 5
        # HSK6=6, B2=4 → gap=-2
        assert get_level_gap("HSK6", "B2") == -2

    def test_unknown_level_returns_zero(self):
        """未知等级当前值=0，只取目标值"""
        assert get_level_gap("???", "B1") == 3  # B1=3, ???=0 → 3-0=3


class TestLevelDescriptors:
    def test_cefr_descriptors_have_all_fields(self):
        """每个CEFR等级都有必要字段"""
        required = ["label", "description", "vocabulary", "grammar", "reading", "writing", "speaking"]
        for level in CEFRLevel:
            desc = CEFR_DESCRIPTORS[level]
            for field in required:
                assert field in desc, f"{level} missing {field}"

    def test_hsk_descriptors_have_all_fields(self):
        """每个HSK等级都有必要字段"""
        required = ["label", "cefr_aligned", "vocabulary", "characters", "description"]
        for level in HSKLevel:
            desc = HSK_DESCRIPTORS[level]
            for field in required:
                assert field in desc, f"{level} missing {field}"

    def test_get_descriptor_valid(self):
        """正确获取等级描述"""
        en_desc = get_level_descriptor("B1", "en")
        assert en_desc["label"] == "进阶级 / Intermediate"
        assert "~2000-2500 words" in en_desc["vocabulary"]

        zh_desc = get_level_descriptor("HSK4", "zh")
        assert zh_desc["vocabulary"] == 1200
        assert zh_desc["cefr_aligned"] == "B2"

    def test_get_descriptor_invalid(self):
        """无效等级返回空字典"""
        assert get_level_descriptor("Z9", "en") == {}
        assert get_level_descriptor("", "zh") == {}


class TestAssessmentDimensions:
    def test_english_dimensions(self):
        """英文评估维度"""
        dims = ASSESSMENT_DIMENSIONS["en"]
        assert "grammar" in dims
        assert "vocabulary" in dims
        assert "reading" in dims
        assert "writing" in dims
        assert "speaking" in dims
        assert len(dims) == 5

    def test_chinese_dimensions(self):
        """中文评估维度（多一个汉字）"""
        dims = ASSESSMENT_DIMENSIONS["zh"]
        assert "characters" in dims
        assert len(dims) == 6


class TestBidirectionalConsistency:
    """双向映射一致性检查"""
    def test_cefr_to_hsk_map_complete(self):
        assert len(CEFR_TO_HSK) == 6

    def test_hsk_to_cefr_map_complete(self):
        assert len(HSK_TO_CEFR) == 6

    def test_cefr_and_hsk_same_numeric_range(self):
        """CEFR和HSK都在1-6范围内"""
        for level_name, value in LEVEL_NUMERIC.items():
            assert 1 <= value <= 6, f"{level_name} = {value} out of range"
