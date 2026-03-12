"""角色管理服務層。"""

from __future__ import annotations

import json
import random
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.character import Character
from app.models.job_mastery import JobMastery


def _load_jobs() -> dict:
    path = Path(__file__).parent.parent.parent / "data" / "jobs.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)



def _check_job_available(
    char: Character, target_job: int, job_data: dict, masteries: dict[int, int],
) -> str | None:
    """檢查轉職條件，回傳 None 表示可轉職，否則回傳錯誤訊息。"""
    reqs = job_data.get("stat_requirements", {})
    stat_map = {"str": char.str_, "mag": char.mag, "fai": char.fai, "vit": char.vit,
                "dex": char.dex, "spd": char.spd, "cha": char.cha, "karma": char.karma}
    for stat, required in reqs.items():
        if stat_map.get(stat, 0) < required:
            return f"{stat.upper()} 不足（需要 {required}）"

    prereqs = job_data.get("prerequisite_masteries", {})
    jobs = _load_jobs()
    for job_id_str, req_level in prereqs.items():
        job_id = int(job_id_str)
        if masteries.get(job_id, 0) < req_level:
            prereq_name = jobs.get(str(job_id), {}).get("name", f"職業{job_id}")
            return f"需要{prereq_name}精通達到 {req_level}"
    return None


def get_job_requirements(
    char: Character, job_data: dict, masteries: dict[int, int],
) -> list[dict]:
    """回傳完整轉職條件列表，每項含 label / required / current / met。"""
    _STAT_LABELS = {"str": "STR", "mag": "MAG", "fai": "FAI", "vit": "VIT",
                    "dex": "DEX", "spd": "SPD", "cha": "CHA", "karma": "業"}
    stat_map = {"str": char.str_, "mag": char.mag, "fai": char.fai, "vit": char.vit,
                "dex": char.dex, "spd": char.spd, "cha": char.cha, "karma": char.karma}
    jobs = _load_jobs()
    result = []

    for stat, required in job_data.get("stat_requirements", {}).items():
        current = stat_map.get(stat, 0)
        result.append({
            "label": _STAT_LABELS.get(stat, stat.upper()),
            "required": required,
            "current": current,
            "met": current >= required,
        })

    for job_id_str, req_level in job_data.get("prerequisite_masteries", {}).items():
        job_id = int(job_id_str)
        current = masteries.get(job_id, 0)
        prereq_name = jobs.get(str(job_id), {}).get("name", f"職業{job_id}")
        result.append({
            "label": f"{prereq_name} 熟練度",
            "required": req_level,
            "current": current,
            "met": current >= req_level,
        })

    return result


def change_job(db: Session, char: Character, target_job: int) -> dict:
    if target_job < 0 or target_job > 30:
        return {"error": "無效的職業"}
    if target_job == char.job_class:
        return {"error": "已經是該職業"}

    jobs = _load_jobs()
    job_key = str(target_job)
    if job_key not in jobs:
        return {"error": "找不到職業資料"}

    # 取得所有職業精通度
    all_masteries = {
        m.job_class: m.mastery_level
        for m in db.query(JobMastery).filter(JobMastery.character_id == char.id).all()
    }
    # 包含當前職業的最新 job_level
    all_masteries[char.job_class] = char.job_level

    # 檢查轉職條件（能力值門檻 + 前置職業精通）
    err = _check_job_available(char, target_job, jobs[job_key], all_masteries)
    if err:
        return {"error": f"無法轉職: {err}"}

    # 保存當前職業的熟練度
    mastery = (
        db.query(JobMastery)
        .filter(JobMastery.character_id == char.id, JobMastery.job_class == char.job_class)
        .first()
    )
    if mastery:
        mastery.mastery_level = char.job_level
    else:
        mastery = JobMastery(
            character_id=char.id, job_class=char.job_class, mastery_level=char.job_level
        )
        db.add(mastery)

    # 讀取新職業的熟練度
    new_mastery = (
        db.query(JobMastery)
        .filter(JobMastery.character_id == char.id, JobMastery.job_class == target_job)
        .first()
    )
    target_mastery_level = new_mastery.mastery_level if new_mastery else 0

    # 轉職懲罰：精通 < 20 時能力值 -10%（Perl: stats -= stats/10）
    if settings.job_change_penalty and target_mastery_level < 20:
        # Perl 順序：先扣 STR~CHA，再用已扣過的 STR 算 karma 扣除
        char.str_ = int(char.str_) - int(char.str_ // 10)
        char.mag = int(char.mag) - int(char.mag // 10)
        char.fai = int(char.fai) - int(char.fai // 10)
        char.vit = int(char.vit) - int(char.vit // 10)
        char.dex = int(char.dex) - int(char.dex // 10)
        char.spd = int(char.spd) - int(char.spd // 10)
        char.cha = int(char.cha) - int(char.cha // 10)
        # Perl: $chara[20] = int($chara[20]) - int($chara[7] / 5) — 用已減少的 STR
        char.karma = int(char.karma) - int(char.str_ // 5)

        # 能力值下限
        if char.str_ < 9: char.str_ = 9
        if char.mag < 8: char.mag = 8
        if char.fai < 8: char.fai = 8
        if char.vit < 9: char.vit = 9
        if char.dex < 9: char.dex = 9
        if char.spd < 8: char.spd = 8
        if char.cha < 8: char.cha = 8
        if char.karma < 0: char.karma = 1

    # 轉職
    char.job_class = target_job
    char.job_level = target_mastery_level if target_mastery_level else 1  # Perl: if(!$chara[33]){$chara[33]=1}
    char.tactic_id = 0  # Perl: $chara[30] = 0（戰術重置）
    db.commit()

    return {
        "message": f"已轉職為{jobs[job_key]['name']}",
        "job_class": char.job_class,
        "job_level": char.job_level,
    }


def _load_tactics() -> dict:
    path = Path(__file__).parent.parent.parent / "data" / "tactics.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_available_tactic_ids(char: Character, masteries: dict[int, int]) -> set[int]:
    """回傳角色可使用的戰技 ID 集合。"""
    tactics = _load_tactics()
    mastered_jobs = {j for j, lv in masteries.items() if lv >= 60}
    available = set()
    for k, v in tactics.items():
        tid = int(k)
        tac_jobs = set(v.get("job_classes", []))
        if not ((tid == 0) or (char.job_class in tac_jobs) or (tac_jobs & mastered_jobs)):
            continue
        if v.get("mastery_required") and char.job_class not in mastered_jobs and not (tac_jobs & mastered_jobs):
            continue
        available.add(tid)
    return available


def change_tactic(db: Session, char: Character, tactic_id: int) -> dict:
    masteries = {
        m.job_class: m.mastery_level
        for m in db.query(JobMastery).filter(JobMastery.character_id == char.id).all()
    }
    masteries[char.job_class] = char.job_level
    allowed = get_available_tactic_ids(char, masteries)
    if tactic_id not in allowed:
        return {"error": "無法使用此戰技"}
    char.tactic_id = tactic_id
    db.commit()
    return {"message": "已變更戰術", "tactic_id": tactic_id}
