"""
LAWA 监督员 v2.0 — 独立守护进程

v2.0 增强（2026-05-31）:
1. 独立守护进程（--daemon），不依赖 OpenClaw cron
2. LLM 透测：真实调用 companion 端点，检测卡顿/超时
3. 会话锁死检测：监控 session 最后活跃时间

用法:
  python3 scripts/supervisor.py check        # 单次巡检
  python3 scripts/supervisor.py daemon       # 守护进程模式
  python3 scripts/supervisor.py start        # 进入高强度监控
  python3 scripts/supervisor.py restart      # 强制重启后端
  python3 scripts/supervisor.py status       # 状态
  python3 scripts/supervisor.py log          # 最近日志
"""
import json
import os
import sys
import time
import signal
import urllib.request
import urllib.error
import subprocess
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ── config ──
LAWA_DIR = Path("/mnt/d/OpenClawData2workspace/Projects/LAWA")
BACKEND_URL = "http://localhost:6288"
FRONTEND_URL = "http://localhost:6289"
COMPANION_URL = f"{BACKEND_URL}/api/v1/companion/correct"
HEALTH_ENDPOINT = f"{BACKEND_URL}/health"
DB_PATH = LAWA_DIR / "data" / "lawa.db"

# OpenClaw sessions dir (for lock detection)
OPENCLAW_DATA = Path("/home/kezhigang/.openclaw-second")
SESSIONS_DIR = OPENCLAW_DATA / "logs"

STATE_FILE = Path(__file__).parent / "supervisor_state.json"
LOG_FILE = LAWA_DIR / "logs" / "supervisor.log"

# ── thresholds ──
LLM_TIMEOUT_SEC = 12        # companion 聊天超时（秒）
LLM_WARN_LATENCY_SEC = 8    # 延迟警告阈值
SESSION_LOCK_MINUTES = 60   # 会话超过此时间无活动视为锁死（放宽至60min）
HEALTH_CHECK_INTERVAL = 120  # 常规巡检间隔（秒）
INTENSIVE_INTERVAL = 60     # 高强度间隔（秒）
MAX_CONSECUTIVE_FAILURES = 3

# 守护进程 PID 文件
PID_FILE = Path(__file__).parent / "supervisor.pid"


def now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_dt():
    return datetime.now(timezone.utc)


def log(msg: str):
    ts = now_ts()
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def load_state() -> dict:
    default = {
        "mode": "normal",
        "consecutive_failures": 0,
        "last_check": None,
        "last_restart": None,
        "last_alert": None,
        "total_restarts": 0,
        "total_checks": 0,
        "llm_latency_history": [],
    }
    if STATE_FILE.exists():
        data = json.loads(STATE_FILE.read_text())
        for k, v in default.items():
            data.setdefault(k, v)
        return data
    return default


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


# ═══════════════════════════════════════
#  检查模块
# ═══════════════════════════════════════

def check_url(url: str, timeout: int = 5) -> tuple[bool, str, float]:
    """返回 (ok, msg, latency_seconds)"""
    t0 = time.time()
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=timeout)
        body = resp.read().decode("utf-8", errors="replace")[:500]
        latency = time.time() - t0
        return True, body, latency
    except urllib.error.URLError as e:
        latency = time.time() - t0
        return False, str(e.reason), latency
    except Exception as e:
        latency = time.time() - t0
        return False, str(e), latency


def check_db() -> tuple[bool, str]:
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("SELECT 1")
        tables = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
        conn.close()
        return True, f"OK ({tables} tables)"
    except Exception as e:
        return False, str(e)


def check_llm_responsiveness() -> tuple[bool, str, float]:
    """
    🆕 真实 LLM 透测：发送对话到 companion endpoint
    超时 = LLM_TIMEOUT_SEC（卡顿/拒绝服务检测）
    延迟 > LLM_WARN_LATENCY_SEC 发出警告
    """
    t0 = time.time()
    try:
        payload = json.dumps({
            "text": "Hello",
            "lang": "en",
            "user_level": "B1",
        }).encode()
        req = urllib.request.Request(
            COMPANION_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SEC)
        body = json.loads(resp.read().decode())
        latency = round(time.time() - t0, 2)

        # 检查响应是否包含实际内容（非空）
        reply = body.get("reply", "") or body.get("message", "") or str(body)
        if not reply or len(reply) < 2:
            return False, f"empty response ({latency}s)", latency

        if latency > LLM_WARN_LATENCY_SEC:
            return True, f"slow ({latency}s, reply:{len(reply)}c)", latency
        return True, f"OK ({latency}s)", latency

    except urllib.error.HTTPError as e:
        latency = round(time.time() - t0, 2)
        body = ""
        try:
            body = e.read().decode()[:200]
        except Exception:
            pass
        return False, f"HTTP {e.code}: {body} ({latency}s)", latency
    except Exception as e:
        latency = round(time.time() - t0, 2)
        err = str(e)[:150]
        return False, f"{err} ({latency}s)", latency


def check_session_health() -> tuple[bool, str]:
    """
    🆕 会话锁死检测：检查 OpenClaw cron runs 健康度
    检测是否有 cron 任务卡住超过阈值
    """
    cron_runs_dir = OPENCLAW_DATA / "cron" / "runs"
    if not cron_runs_dir.exists():
        return True, "cron dir not found (skipped)"

    try:
        stale_jobs = []
        now = _now_dt()
        threshold = now - timedelta(minutes=SESSION_LOCK_MINUTES)

        for run_file in cron_runs_dir.glob("*.jsonl"):
            mtime = datetime.fromtimestamp(run_file.stat().st_mtime, tz=timezone.utc)
            size = run_file.stat().st_size
            # 文件最近30分钟内有修改 → 活跃；超过阈值 → 可能卡住
            # 但注意：已完成的 cron run 文件不会继续更新，这是正常的
            # 只告警那些文件特别大（>5KB）且很久没更新的（可能写入卡死）
            if mtime < threshold and size > 5000:
                stale_jobs.append({
                    "job": run_file.stem[:12],
                    "last_active": mtime.strftime("%H:%M"),
                    "idle_min": round((now - mtime).total_seconds() / 60, 1),
                })

        if stale_jobs:
            return False, f"{len(stale_jobs)} stale cron runs"
        run_count = len(list(cron_runs_dir.glob("*.jsonl")))
        return True, f"OK ({run_count} cron runs)"

    except Exception as e:
        return True, f"check error: {str(e)[:80]}"


# ═══════════════════════════════════════
#  自动修复
# ═══════════════════════════════════════

def restart_backend() -> tuple[bool, str]:
    """重启 LAWA 后端"""
    try:
        subprocess.run(
            ["pkill", "-f", "uvicorn src.main:app.*6288"],
            capture_output=True, timeout=5,
        )
        time.sleep(2)
        env = os.environ.copy()
        subprocess.Popen(
            ["python3", "-m", "uvicorn", "src.main:app",
             "--host", "0.0.0.0", "--port", "6288"],
            cwd=str(LAWA_DIR),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(4)
        ok, msg, _ = check_url(HEALTH_ENDPOINT)
        return ok, f"restarted: {msg[:100]}"
    except Exception as e:
        return False, str(e)


def alert_ke(message: str):
    """通过 OpenClaw 通知 Ke（写入 alert log，由 cron agent 转发）"""
    log(f"🚨 ALERT: {message}")
    # 也写入告警文件
    alert_file = LAWA_DIR / "logs" / "alerts.log"
    alert_file.parent.mkdir(parents=True, exist_ok=True)
    with open(alert_file, "a") as f:
        f.write(f"[{now_ts()}] {message}\n")


# ═══════════════════════════════════════
#  巡检主逻辑
# ═══════════════════════════════════════

def run_check() -> dict:
    """执行一次全面巡检，返回结果 dict"""
    state = load_state()
    state["total_checks"] += 1
    results = {}
    issues = []

    log("🔍 巡检开始...")

    # 1. 后端健康
    ok, msg, lat = check_url(HEALTH_ENDPOINT)
    results["backend"] = {"ok": ok, "msg": msg[:100], "latency_s": round(lat, 2)}
    log(f"  后端: {'✅' if ok else '❌'} {msg[:80]} ({lat:.1f}s)")

    # 2. 前端
    ok2, msg2, lat2 = check_url(FRONTEND_URL, timeout=3)
    results["frontend"] = {"ok": ok2, "msg": "OK" if ok2 else msg2[:80]}
    log(f"  前端: {'✅' if ok2 else '❌'}")

    # 3. 数据库
    ok3, msg3 = check_db()
    results["database"] = {"ok": ok3, "msg": msg3}
    log(f"  数据库: {'✅' if ok3 else '❌'} {msg3}")

    # 4. 🆕 LLM 透测
    if ok:  # 只有后端在线才测 LLM
        ok4, msg4, lat4 = check_llm_responsiveness()
        results["llm"] = {"ok": ok4, "msg": msg4, "latency_s": lat4}
        log(f"  LLM: {'✅' if ok4 else '❌'} {msg4}")
        # 记录延迟历史
        state["llm_latency_history"].append({"ts": now_ts(), "latency": lat4, "ok": ok4})
        if len(state["llm_latency_history"]) > 100:
            state["llm_latency_history"] = state["llm_latency_history"][-100:]
        if not ok4:
            issues.append(f"LLM: {msg4}")
    else:
        results["llm"] = {"ok": False, "msg": "backend down, skipped", "latency_s": 0}

    # 5. 🆕 会话锁死检测
    ok5, msg5 = check_session_health()
    results["sessions"] = {"ok": ok5, "msg": msg5}
    log(f"  会话: {'✅' if ok5 else '⚠️'} {msg5}")
    if not ok5:
        issues.append(f"会话锁死: {msg5}")

    # 6. 决策 + 自动修复
    # 核心原则：只在后端端口 DOWN 时才重启。LLM延迟≠后端崩。
    backend_failed = not results["backend"]["ok"]
    llm_failed = not results.get("llm", {}).get("ok", True)

    if backend_failed:
        state["consecutive_failures"] += 1
        log(f"  ⚠️ 后端连续失败 {state['consecutive_failures']}/{MAX_CONSECUTIVE_FAILURES}")
        if state["consecutive_failures"] >= MAX_CONSECUTIVE_FAILURES:
            log("  🔄 触发自动重启...")
            ok_r, msg_r = restart_backend()
            results["restart"] = {"ok": ok_r, "msg": msg_r}
            state["total_restarts"] += 1
            state["last_restart"] = now_ts()
            state["consecutive_failures"] = 0
            alert_ke(f"后端自动重启: {'✅' if ok_r else '❌'} {msg_r}")
            log(f"  重启结果: {'✅' if ok_r else '❌'} {msg_r}")
    elif llm_failed:
        # LLM 卡顿/超时 → 仅告警，不重启（外部API慢≠后端崩）
        state["consecutive_failures"] = 0  # 不影响后端失败计数
        llm_msg = results.get("llm", {}).get("msg", "unknown")
        log(f"  ⚠️ LLM响应异常（仅告警，不重启）: {llm_msg}")
        # 每10分钟最多告警一次
        last_llm_alert = state.get("last_llm_alert", "")
        if not last_llm_alert or (datetime.fromisoformat(last_llm_alert.replace('Z','+00:00')).replace(tzinfo=timezone.utc) < _now_dt() - timedelta(minutes=10)):
            alert_ke(f"LLM卡顿警告: {llm_msg}")
            state["last_llm_alert"] = now_ts()
    else:
        state["consecutive_failures"] = 0

    state["last_check"] = now_ts()
    save_state(state)

    # 判决
    all_ok = all(
        results[k]["ok"] for k in results if k not in ("restart", "llm")
    )
    results["issues"] = issues
    results["verdict"] = "✅ ALL OK" if all_ok and not issues else "⚠️ ISSUES"

    log(f"🏁 巡检结束: {results['verdict']}")
    if issues:
        for issue in issues:
            log(f"  🚨 {issue}")

    return results


# ═══════════════════════════════════════
#  守护进程模式
# ═══════════════════════════════════════

def run_daemon():
    """🆕 独立守护进程：不依赖 OpenClaw cron"""
    # 写 PID
    PID_FILE.write_text(str(os.getpid()))

    def handle_signal(signum, frame):
        log(f"收到信号 {signum}，优雅退出...")
        PID_FILE.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    log("🦝 LAWA 监督员守护进程 v2.0 启动")
    log(f"   PID: {os.getpid()}")
    log(f"   interval: {HEALTH_CHECK_INTERVAL}s (normal), {INTENSIVE_INTERVAL}s (intensive)")
    log(f"   LLM timeout: {LLM_TIMEOUT_SEC}s")
    log(f"   session lock threshold: {SESSION_LOCK_MINUTES}min")

    try:
        while True:
            state = load_state()
            interval = INTENSIVE_INTERVAL if state.get("mode") == "intensive" else HEALTH_CHECK_INTERVAL

            result = run_check()

            # 发现严重问题 → 立即通知
            if result.get("issues"):
                # 写入告警标记（OpenClaw cron 会检测并转发）
                alert_file = LAWA_DIR / "logs" / "alerts.log"
                if alert_file.exists():
                    mtime = alert_file.stat().st_mtime
                    age = time.time() - mtime
                    if age < 120:  # 2分钟内有新告警
                        log(f"  📢 有活跃告警，等待处理...")

            log(f"💤 休眠 {interval}s...")
            time.sleep(interval)

    except Exception as e:
        log(f"💥 守护进程异常: {e}")
        PID_FILE.unlink(missing_ok=True)
        raise


# ═══════════════════════════════════════
#  CLI
# ═══════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="LAWA 监督员 v2.0")
    parser.add_argument("action", nargs="?", default="check",
                       choices=["check", "daemon", "start", "stop", "restart", "status", "log"])
    args = parser.parse_args()

    os.chdir(str(LAWA_DIR))

    if args.action == "check":
        result = run_check()
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
        return 0 if result["verdict"] == "✅ ALL OK" else 1

    elif args.action == "daemon":
        run_daemon()
        return 0

    elif args.action == "start":
        state = load_state()
        state["mode"] = "intensive"
        save_state(state)
        log("🦝 达子监督员开工！进入高强度监控模式")
        result = run_check()
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
        return 0

    elif args.action == "stop":
        state = load_state()
        state["mode"] = "normal"
        save_state(state)
        # Kill daemon if running
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                log(f"🛑 已停止守护进程 (PID={pid})")
            except ProcessLookupError:
                pass
            PID_FILE.unlink(missing_ok=True)
        log("🦝 达子监督员收工！恢复常规模式")
        return 0

    elif args.action == "restart":
        ok, msg = restart_backend()
        print(f"Restart: {'✅' if ok else '❌'} {msg}")
        return 0 if ok else 1

    elif args.action == "status":
        state = load_state()
        daemon_running = PID_FILE.exists()
        if daemon_running:
            try:
                pid = int(PID_FILE.read_text().strip())
                os.kill(pid, 0)  # signal 0 = check exists
            except (ProcessLookupError, ValueError):
                daemon_running = False

        # 最近 LLM 延迟
        lat_history = state.get("llm_latency_history", [])
        recent_lat = [h["latency"] for h in lat_history[-10:] if h.get("ok")]

        print(json.dumps({
            **state,
            "daemon_running": daemon_running,
            "llm_avg_latency": round(sum(recent_lat)/len(recent_lat), 2) if recent_lat else None,
        }, indent=2, default=str, ensure_ascii=False))
        return 0

    elif args.action == "log":
        if LOG_FILE.exists():
            lines = LOG_FILE.read_text().strip().split("\n")
            for line in lines[-30:]:
                print(line)
        else:
            print("No logs yet")
        return 0


if __name__ == "__main__":
    sys.exit(main())
