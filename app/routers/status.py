import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models.champion import Champion
from app.models.character import Character
from app.models.online_player import OnlinePlayer

router = APIRouter(prefix="/status", tags=["狀態"])


@router.get("")
def get_status(
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    now = int(time.time())

    # 更新線上狀態
    online = db.query(OnlinePlayer).filter(OnlinePlayer.character_id == current_user.id).first()
    if online:
        online.last_seen = now
        online.level = current_user.level
    else:
        online = OnlinePlayer(
            character_id=current_user.id,
            character_name=current_user.name,
            last_seen=now,
            level=current_user.level,
        )
        db.add(online)
    db.commit()

    # 載入裝備
    equip = current_user.equipment

    # 冠軍資料
    champion = db.query(Champion).first()

    # 戰鬥冷卻
    battle_cooldown = max(0, settings.b_time - (now - current_user.last_battle_time))

    return {
        "character": {
            "id": current_user.id,
            "name": current_user.name,
            "level": current_user.level,
            "job_class": current_user.job_class,
            "job_level": current_user.job_level,
            "current_hp": current_user.current_hp,
            "max_hp": current_user.max_hp,
            "exp": current_user.exp,
            "gold": current_user.gold,
            "bank_savings": current_user.bank_savings,
            "str": current_user.str_,
            "mag": current_user.mag,
            "fai": current_user.fai,
            "vit": current_user.vit,
            "dex": current_user.dex,
            "spd": current_user.spd,
            "cha": current_user.cha,
            "karma": current_user.karma,
            "battle_count": current_user.battle_count,
            "win_count": current_user.win_count,
            "available_battles": current_user.available_battles,
            "tactic_id": current_user.tactic_id,
            "title_rank": current_user.title_rank,
        },
        "equipment": {
            "weapon_name": equip.weapon_name if equip else "徒手",
            "weapon_attack": equip.weapon_attack if equip else 0,
            "armor_name": equip.armor_name if equip else "布衣",
            "armor_defense": equip.armor_defense if equip else 0,
            "accessory_name": equip.accessory_name if equip else "無",
        } if equip else None,
        "champion": {
            "character_name": champion.character_name,
            "win_streak": champion.win_streak,
        } if champion else None,
        "battle_cooldown": battle_cooldown,
    }


@router.post("/inn")
def use_inn(
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    cost = current_user.level * settings.yado_dai
    if current_user.current_hp >= current_user.max_hp:
        raise HTTPException(status_code=400, detail="HP已滿")
    # 與商店同步：持有金不足時自動從銀行補差額
    from app.services.shop_service import _deduct_gold
    err = _deduct_gold(current_user, cost)
    if err:
        raise HTTPException(status_code=400, detail=err)

    current_user.current_hp = current_user.max_hp
    db.commit()

    return {
        "message": f"HP已完全恢復（{cost}G）",
        "current_hp": current_user.current_hp,
        "gold": int(current_user.gold),
        "bank_savings": int(current_user.bank_savings),
    }
