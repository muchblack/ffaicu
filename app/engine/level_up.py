"""升級邏輯。"""

from __future__ import annotations

import json
import random
from pathlib import Path

from app.config import settings


def check_level_up(
    level: int,
    exp: int,
    job_class: int,
    stats: dict[str, int],
    max_hp: int,
) -> tuple[int, int, dict[str, int], int]:
    """檢查並執行升級。回傳 (new_level, new_exp, new_stats, new_max_hp)。"""
    jobs = _load_jobs()
    job_def = jobs.get(str(job_class), {})
    levelup_ranges = job_def.get("levelup_ranges", [2, 2, 2, 2, 2, 2, 2, 1])
    stat_names = ["str", "mag", "fai", "vit", "dex", "spd", "cha", "karma"]

    new_level = level
    new_exp = exp
    new_stats = dict(stats)
    new_max_hp = max_hp
    level_ups = 0

    while new_exp >= new_level * settings.lv_up and new_level < settings.chara_max_lv:
        new_exp -= new_level * settings.lv_up
        new_level += 1
        level_ups += 1

        # 各能力值依職業定義的成長範圍加算（50% 機率觸發，比照原版）
        for i, stat_name in enumerate(stat_names):
            if random.randint(0, 1) == 0:
                growth = levelup_ranges[i] if i < len(levelup_ranges) else 1
                new_stats[stat_name] = min(
                    new_stats.get(stat_name, 0) + random.randint(0, max(1, growth) - 1) + 1,
                    settings.chara_max_stat,
                )

        # HP 成長：rand(VIT) * 3 + VIT（比照原版）
        vit = new_stats.get("vit", 0)
        hp_growth = random.randint(0, max(1, vit) - 1) * 3 + vit
        new_max_hp = min(new_max_hp + hp_growth, settings.chara_max_hp)

    return new_level, new_exp, new_stats, new_max_hp


_jobs_cache: dict | None = None


def _load_jobs() -> dict:
    global _jobs_cache
    if _jobs_cache is None:
        path = Path(__file__).parent.parent.parent / "data" / "jobs.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                _jobs_cache = json.load(f)
        else:
            _jobs_cache = {}
    return _jobs_cache
