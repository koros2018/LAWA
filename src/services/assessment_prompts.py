"""
LAWA 评估 Prompt 模板

中英文评估的所有 LLM Prompt 集中管理
"""

# ══════════════════════════════════════════
# 英文评估 Prompts
# ══════════════════════════════════════════

EN_ASSESSMENT_SYSTEM = """You are a CEFR English proficiency assessment expert. You design adaptive tests and evaluate responses against CEFR standards (A1-C2).

Your evaluation dimensions:
- Grammar: tense accuracy, sentence structure, article usage, preposition usage
- Vocabulary: word choice precision, collocation, range, register appropriateness
- Reading: comprehension accuracy, inference ability, main idea grasping
- Writing: organization, coherence, argument development, tone
- Speaking: fluency, pronunciation patterns, interaction ability (when applicable)

For each question, you must:
1. Assign a precise difficulty level (easy/medium/hard) aligned with CEFR
2. Score objectively using rubrics
3. Provide concise, actionable feedback
4. Update the user's estimated CEFR level based on cumulative performance

Output all results in structured JSON format."""

EN_GRAMMAR_TEST_PROMPT = """Design {count} English grammar multiple-choice questions at approximately CEFR {level} level.

Topic focus: {topics}
Question format: multiple_choice with 4 options

For each question provide:
1. A natural English sentence with a grammatical gap
2. Four options (A/B/C/D), with one correct
3. A brief explanation of why the correct answer is right
4. The specific grammar rule being tested

Return as JSON:
{
  "questions": [
    {
      "question_text": "...",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
      "correct_answer": "B",
      "explanation": "...",
      "grammar_rule": "...",
      "difficulty": "medium",
      "cefr_level": "{level}"
    }
  ]
}"""

EN_READING_TEST_PROMPT = """Create an English reading comprehension test at CEFR {level} level.

Generate:
1. A {word_count}-word passage about: {topic}
2. {count} comprehension questions (mix of multiple_choice and open_ended)

The passage should be authentic, engaging, and appropriate for {level} learners.

Return as JSON:
{
  "passage": "...",
  "questions": [
    {
      "type": "multiple_choice|open_ended",
      "question_text": "...",
      "options": ["..."],  // only for multiple_choice
      "correct_answer": "...",
      "skill_tested": "main_idea|detail|inference|vocabulary",
      "difficulty": "medium"
    }
  ]
}"""

EN_WRITING_PROMPT = """Design an English writing assessment for CEFR {level} level.

Task type: {task_type} (email|essay|report|story)
Topic: {topic}
Expected length: {word_count} words

Provide:
1. Clear task instructions
2. Evaluation rubric (scoring criteria)
3. Model answer for reference

Return as JSON:
{
  "task_instruction": "...",
  "rubric": {
    "grammar": {"weight": 0.25, "criteria": "..."},
    "vocabulary": {"weight": 0.25, "criteria": "..."},
    "organization": {"weight": 0.25, "criteria": "..."},
    "content": {"weight": 0.25, "criteria": "..."}
  },
  "model_answer": "..."
}"""

EN_VOCABULARY_TEST_PROMPT = """Generate {count} English vocabulary questions at CEFR {level} level.



Topic focus: {topics}

Task type: {task_type} (multiple_choice|fill_blank|matching)



For each question provide:

- A contextual sentence with a target word or gap

- 4 options for multiple_choice, or the correct word for fill_blank

- The correct answer

- A brief explanation of the word meaning/usage



Return as JSON:

{

  "questions": [

    {

      "type": "multiple_choice|fill_blank",

      "question_text": "...",

      "options": ["..."],

      "correct_answer": "...",

      "explanation": "...",

      "word_level": "A1-C2",

      "difficulty": "easy|medium|hard"

    }

  ]

}"""



EN_LISTENING_PROMPT = """Design an English listening comprehension question at CEFR {level} level.

Topic: {topics}

Create a short spoken passage (50-100 words) that the learner will HEAR (not read).
Then ask 1-2 comprehension questions about what they heard.

IMPORTANT: The passage text must be provided in a field called 'audio_text' so it can be read aloud.

Return JSON:
{
  "type": "listening",
  "audio_text": "The passage to be read aloud (50-100 words of natural spoken English)",
  "question_text": "Comprehension question about the audio passage",
  "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
  "correct_answer": "B",
  "difficulty": "easy|medium|hard",
  "cefr_level": "{level}",
  "transcript_hint": "Key words to listen for"
}"""

EN_SPEAKING_PROMPT = """Design an English speaking assessment prompt at CEFR {level} level.



Topic: {topics}

Task type: {task_type} (monologue|dialogue|presentation|roleplay)



Provide:

1. A clear speaking task description

2. Key vocabulary/phrases to include

3. Expected duration: 1-3 minutes

4. Evaluation criteria



Return as JSON:

{

  "task_instruction": "...",

  "prompt_questions": ["..."],

  "key_vocabulary": ["..."],

  "expected_duration_seconds": 60,

  "rubric": {

    "fluency": {"weight": 0.3, "criteria": "..."},

    "grammar": {"weight": 0.25, "criteria": "..."},

    "vocabulary": {"weight": 0.25, "criteria": "..."},

    "content": {"weight": 0.2, "criteria": "..."}

  }

}"""



ZH_VOCABULARY_TEST_PROMPT = """Generate {count} Chinese vocabulary questions at HSK {level} level.



Topic: {topics}

Task type: {task_type}



Return as JSON with questions array."""



ZH_SPEAKING_PROMPT = """Design a Chinese speaking assessment prompt at HSK {level} level.



Topic: {topics}

Task type: {task_type}



Return as JSON with task instructions, prompts, and rubric."""
EN_SCORING_PROMPT = """Score the following English writing response against CEFR {level} standards.

Task: {task_description}
User's Response: "{user_response}"

Evaluate on these dimensions (each 0-10):
1. Grammar - accuracy and range
2. Vocabulary - precision, range, collocation
3. Organization - coherence, structure, paragraphing
4. Content - relevance, development, completeness

For each dimension:
- Give a score (0-10)
- Estimate the CEFR level demonstrated
- Provide specific examples from the text
- Give one actionable improvement tip

Also provide:
- Overall CEFR estimate
- Top 2 strengths
- Top 2 areas for improvement

Return as JSON:
{
  "overall_cefr": "B1",
  "scores": {
    "grammar": {"score": 7, "cefr_level": "B1", "examples": ["..."], "tip": "..."},
    "vocabulary": {"score": 6, "cefr_level": "A2", "examples": ["..."], "tip": "..."},
    "organization": {"score": 8, "cefr_level": "B2", "examples": ["..."], "tip": "..."},
    "content": {"score": 7, "cefr_level": "B1", "examples": ["..."], "tip": "..."}
  },
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "feedback": "Overall feedback here..."
}"""

EN_REPORT_PROMPT = """Generate a comprehensive English proficiency assessment report.

User Profile:
- Current estimated level: {level}
- Test completed: {questions_count} questions across {dimensions}

Dimension Scores: {dimension_scores}

Create a report with:
1. Executive summary (2-3 sentences)
2. Detailed breakdown per dimension
3. CEFR level justification
4. Strengths and weaknesses
5. Recommended next steps (specific, actionable)
6. Estimated time to reach next CEFR level with daily practice

Return as JSON:
{
  "summary": "...",
  "dimension_details": { ... },
  "cefr_justification: "...",
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "recommendations": ["...", "..."],
  "next_level_estimate": {"target": "B2", "estimated_weeks": 12}
}"""


# ══════════════════════════════════════════
# 中文评估 Prompts
# ══════════════════════════════════════════

ZH_ASSESSMENT_SYSTEM = """你是一位HSK汉语水平评估专家。你设计自适应测试题，严格按照HSK标准（1-6级）评分。

评估维度：
- 汉字：识读、书写、部首理解
- 词汇：词汇量、近义词辨析、成语使用
- 语法：语序、虚词、句式结构
- 阅读：理解能力、推断能力、主旨把握
- 写作：结构、连贯性、表达准确度
- 口语：流利度、发音、互动能力

对每道题，你需要：
1. 明确标注HSK难度等级
2. 使用评分标准客观打分
3. 提供简洁、可执行的反馈建议
4. 根据累积表现更新用户的HSK等级估计

所有输出使用结构化JSON格式。"""

ZH_CHARACTER_TEST_PROMPT = """设计{count}道HSK {level}级别的汉字测试题。

题型混合：
- 看拼音写汉字
- 选词填空（同音字/形近字辨析）
- 部首/偏旁识别

每道题提供：
1. 题目文本
2. 正确答案
3. 考察点说明
4. HSK等级

返回JSON格式：
{
  "questions": [
    {
      "type": "write_character|choose_character|identify_radical",
      "question_text": "...",
      "correct_answer": "...",
      "point": "考察点",
      "difficulty": "easy|medium|hard",
      "hsk_level": "HSK3"
    }
  ]
}"""

ZH_GRAMMAR_TEST_PROMPT = """设计{count}道HSK {level}级别的中文语法测试题。

语法范围：{topics}
题型：选择题（4个选项）

每道题提供：
1. 一个包含语法考点的中文句子（含空缺）
2. 四个选项
3. 正确答案和解释
4. 对应的语法规则

返回JSON格式：
{
  "questions": [
    {
      "question_text": "...",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
      "correct_answer": "B",
      "explanation": "...",
      "grammar_rule": "...",
      "difficulty": "medium",
      "hsk_level": "{level}"
    }
  ]
}"""

ZH_READING_TEST_PROMPT = """创建一篇HSK {level}级别的中文阅读测试。

生成：
1. 一篇约{word_count}字的文章，主题：{topic}
2. {count}道理解题（选择题和开放题混合）

文章应该自然、有趣，适合{level}水平的学习者。

返回JSON格式：
{
  "passage": "...",
  "questions": [
    {
      "type": "multiple_choice|open_ended",
      "question_text": "...",
      "options": ["..."],
      "correct_answer": "...",
      "skill_tested": "main_idea|detail|inference|vocabulary",
      "difficulty": "medium"
    }
  ]
}"""

ZH_WRITING_PROMPT = """设计一道HSK {level}级别的中文写作题。

任务类型：{task_type}（信件|短文|报告|故事）
主题：{topic}
建议字数：{word_count}字

提供：
1. 清晰的写作任务说明
2. 评分标准
3. 参考范文

返回JSON格式：
{
  "task_instruction": "...",
  "rubric": {
    "characters": {"weight": 0.15, "criteria": "汉字书写正确性"},
    "vocabulary": {"weight": 0.25, "criteria": "词汇丰富度和准确性"},
    "grammar": {"weight": 0.25, "criteria": "语法正确性和复杂度"},
    "organization": {"weight": 0.20, "criteria": "结构和连贯性"},
    "content": {"weight": 0.15, "criteria": "内容相关性和完整性"}
  },
  "model_answer": "..."
}"""

ZH_SCORING_PROMPT = """按照HSK {level}标准批改以下中文写作回答。

写作任务：{task_description}
学生回答："{user_response}"

从以下维度评分（每题0-10分）：
1. 汉字 - 书写正确性
2. 词汇 - 丰富度和准确性
3. 语法 - 正确性和复杂度
4. 结构 - 连贯性和组织
5. 内容 - 相关性和完整性

每个维度：
- 给出分数
- 评估对应的HSK等级
- 从文本中举出具体例子
- 给出一个改进建议

同时提供：
- 整体HSK等级估计
- 2个优势
- 2个待改进点

返回JSON格式：
{
  "overall_hsk": "HSK4",
  "scores": { ... },
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "feedback": "整体反馈..."
}"""

ZH_REPORT_PROMPT = """生成一份中文水平评估综合报告。

用户信息：
- 当前估计等级：{level}
- 完成题目：{questions_count}题，覆盖{all_dimensions}个维度

维度分数：{dimension_scores}

生成报告包含：
1. 总体摘要（2-3句话）
2. 各维度详细分析
3. HSK等级判定依据
4. 优势与不足
5. 具体可行的下一步学习建议
6. 按每日学习时间估算达到下一级所需时间

返回JSON格式：
{
  "summary": "...",
  "dimension_details": { ... },
  "hsk_justification": "...",
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "recommendations": ["...", "..."],
  "next_level_estimate": {"target": "HSK5", "estimated_weeks": 12}
}"""


# ── Prompt 选择器 ──
def get_system_prompt(lang: str) -> str:
    """获取对应语言的系统Prompt"""
    return EN_ASSESSMENT_SYSTEM if lang == "en" else ZH_ASSESSMENT_SYSTEM


def get_test_prompt(dimension: str, lang: str) -> str:
    """获取对应维度的测试题生成Prompt"""
    prompts = {
        "en": {
            "grammar": EN_GRAMMAR_TEST_PROMPT,
            "vocabulary": EN_VOCABULARY_TEST_PROMPT,
            "reading": EN_READING_TEST_PROMPT,
            "writing": EN_WRITING_PROMPT,
            "speaking": EN_SPEAKING_PROMPT,
            "listening": EN_LISTENING_PROMPT,
        },
        "zh": {
            "characters": ZH_CHARACTER_TEST_PROMPT,
            "vocabulary": ZH_VOCABULARY_TEST_PROMPT,
            "grammar": ZH_GRAMMAR_TEST_PROMPT,
            "reading": ZH_READING_TEST_PROMPT,
            "writing": ZH_WRITING_PROMPT,
            "speaking": ZH_SPEAKING_PROMPT,
        },
    }
    return prompts.get(lang, {}).get(dimension, "")


def get_scoring_prompt(lang: str) -> str:
    """获取对应语言的评分Prompt"""
    return EN_SCORING_PROMPT if lang == "en" else ZH_SCORING_PROMPT


def get_report_prompt(lang: str) -> str:
    """获取对应语言的报告生成Prompt"""
    return EN_REPORT_PROMPT if lang == "en" else ZH_REPORT_PROMPT
