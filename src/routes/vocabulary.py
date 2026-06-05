"""
LAWA 词汇 API 路由

POST /api/v1/vocabulary/extract — 从导师回复提取生词并保存
GET  /api/v1/vocabulary/queue   — 获取待复习队列
POST /api/v1/vocabulary/review  — 提交复习结果
GET  /api/v1/vocabulary/list    — 词汇列表
GET  /api/v1/vocabulary/stats   — 复习统计
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.services.vocabulary import vocabulary_service

router = APIRouter(prefix="/api/v1/vocabulary", tags=["vocabulary"])


@router.post("/extract")
async def extract_and_save(payload: dict, db: AsyncSession = Depends(get_db)):
    """
    从导师回复中提取生词并持久化到DB

    payload: { user_id, lang, tutor_reply, user_level?, session_id? }
    """
    user_id = payload.get("user_id")
    lang = payload.get("lang", "en")
    tutor_reply = payload.get("tutor_reply", "")
    user_level = payload.get("user_level", "B1")
    session_id = payload.get("session_id")

    if not user_id or not tutor_reply:
        raise HTTPException(400, "user_id and tutor_reply required")

    # LLM 提取生词
    words = await vocabulary_service.extract_vocabulary(tutor_reply, lang, user_level)

    # 保存到DB（去重）
    saved = await vocabulary_service.save_vocabulary(
        db, user_id, lang, words, session_id
    )

    return {
        "extracted": len(words),
        "saved": len(saved),
        "vocabulary": words,
    }


@router.get("/queue")
async def get_queue(
    user_id: str,
    lang: str = "en",
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """获取该用户待复习词汇"""
    queue = await vocabulary_service.get_review_queue(db, user_id, lang, limit)
    return {"due_count": len(queue), "queue": queue}


@router.post("/review")
async def submit_review(payload: dict, db: AsyncSession = Depends(get_db)):
    """
    提交复习评分

    payload: { vocab_id, quality: 0-5 }
    """
    vocab_id = payload.get("vocab_id")
    quality = payload.get("quality", 3)

    if not vocab_id:
        raise HTTPException(400, "vocab_id required")
    if not 0 <= quality <= 5:
        raise HTTPException(400, "quality must be 0-5")

    result = await vocabulary_service.review_vocabulary(db, vocab_id, quality)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.get("/list")
async def list_vocabulary(
    user_id: str,
    lang: str = "en",
    mastered: bool = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """获取词汇列表（可按掌握状态筛选）"""
    return await vocabulary_service.get_vocabulary_list(db, user_id, lang, mastered, limit)


@router.get("/stats")
async def get_stats(
    user_id: str,
    lang: str = "en",
    db: AsyncSession = Depends(get_db),
):
    """获取词汇复习统计"""
    return await vocabulary_service.get_review_stats(db, user_id, lang)
