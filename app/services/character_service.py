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


def allocate_stat(db: Session, char: Character, stat_name: str) -> dict:
    valid = {"str", "mag", "fai", "vit", "dex", "spd", "cha"}
    if stat_name not in valid:
        return {"error": f"無效的能力值: {stat_name}"}

    # karma 作為可分配點數
    if char.karma <= 0:
        return {"error": "沒有可分配的點數"}

    attr = "str_" if stat_name == "str" else stat_name
    current = getattr(char, attr)
    if current >= settings.chara_max_stat:
        return {"error": "能力值已達上限"}

    setattr(char, attr, current + 1)
    char.karma -= 1
    db.commit()
    return {"message": f"{stat_name}提升了1點", stat_name: current + 1, "karma": char.karma}


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
    if target_mastery_level < 20:
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


def change_tactic(db: Session, char: Character, tactic_id: int) -> dict:
    char.tactic_id = tactic_id
    db.commit()
    return {"message": "已變更戰術", "tactic_id": tactic_id}
