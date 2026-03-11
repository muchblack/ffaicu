"""前端視圖路由 — 將 API 結果渲染成 HTML 模板。"""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db
from app.models.champion import Champion
from app.models.character import Character
from app.models.item_catalog import AccessoryCatalog, ArmorCatalog, WeaponCatalog
from app.models.message import BroadcastMessage, Message
from app.models.monster import Monster
from app.models.zone_config import ZoneConfig
from app.models.online_player import OnlinePlayer
from app.models.warehouse import WarehouseItem
from app.services import auth_service, battle_service, character_service, ranking_service, shop_service
from app.services import skill_file_service

router = APIRouter(prefix="/view", tags=["頁面"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _get_user(db: Session, token: str | None) -> Character | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        cid = payload.get("sub")
        if cid:
            return db.query(Character).filter(Character.id == cid).first()
    except JWTError:
        pass
    return None


def _load_jobs() -> dict:
    path = Path(__file__).parent.parent.parent / "data" / "jobs.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# === 首頁 ===
@router.get("/home", response_class=HTMLResponse)
def view_home(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None)):
    user = _get_user(db, ffa_token)
    now = int(time.time())
    champion = db.query(Champion).first()
    online = db.query(OnlinePlayer).filter(OnlinePlayer.last_seen > now - 1800).all()
    return templates.TemplateResponse("home.html", {
        "request": request, "user": user, "champion": champion,
        "online_count": len(online),
        "online_players": [{"name": p.character_name, "level": p.level} for p in online],
    })


# === 登入 ===
@router.post("/login")
def view_login(request: Request, db: Session = Depends(get_db), id: str = Form(), password: str = Form()):
    host = request.client.host if request.client else ""
    char = auth_service.authenticate(db, id, password, host)
    if not char:
        return templates.TemplateResponse("home.html", {
            "request": request, "user": None, "champion": None,
            "online_count": 0, "online_players": [],
            "flash_message": "帳號或密碼錯誤", "flash_type": "error",
        })
    token = auth_service.create_access_token(char.id)
    resp = RedirectResponse("/view/status", status_code=303)
    resp.set_cookie("ffa_token", token, httponly=True, samesite="strict", max_age=60*60*24*30)
    return resp


# === 登録 ===
@router.get("/register", response_class=HTMLResponse)
def view_register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register")
def view_register(
    request: Request, db: Session = Depends(get_db),
    id: str = Form(), password: str = Form(), password_recovery: str = Form(),
    name: str = Form(), sex: int = Form(default=1), job_class: int = Form(default=0),
):
    existing = db.query(Character).filter((Character.id == id) | (Character.name == name)).first()
    if existing:
        return templates.TemplateResponse("register.html", {
            "request": request, "flash_message": "帳號或名稱已被使用", "flash_type": "error",
        })
    host = request.client.host if request.client else ""
    char = auth_service.register_character(db, id, password, password_recovery, name, "", "", sex, 0, job_class, host)
    token = auth_service.create_access_token(char.id)
    resp = RedirectResponse("/view/status", status_code=303)
    resp.set_cookie("ffa_token", token, httponly=True, samesite="strict", max_age=60*60*24*30)
    return resp


# === 狀態 ===
@router.get("/status", response_class=HTMLResponse)
def view_status(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None)):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")

    # 每日重置剩餘戰鬥次數
    battle_service._reset_daily_battles(user)

    # 更新線上狀態
    now = int(time.time())
    online = db.query(OnlinePlayer).filter(OnlinePlayer.character_id == user.id).first()
    if online:
        online.last_seen = now
    else:
        db.add(OnlinePlayer(character_id=user.id, character_name=user.name, last_seen=now, level=user.level))
    db.commit()

    jobs = _load_jobs()
    job_name = jobs.get(str(user.job_class), {}).get("name", "不明")
    champion = db.query(Champion).first()
    cooldown = battle_service.check_cooldown(user, settings.b_time)

    # 從 DB 查有魔物且已開放的區域，按 _ZONE_ORDER 排序
    zones_with_monsters = {z for z, in db.query(Monster.zone).distinct()}
    closed_zones = {zc.zone for zc in db.query(ZoneConfig).filter(ZoneConfig.open == False).all()}
    hunt_zones = [z for z in _ZONE_ORDER if z in zones_with_monsters and z not in closed_zones]

    return templates.TemplateResponse("status.html", {
        "request": request, "char": user, "equip": user.equipment,
        "job_name": job_name, "champion": champion, "cooldown": cooldown,
        "inn_cost": user.level * settings.yado_dai,
        "hunt_zones": hunt_zones, "zone_labels": _ZONE_LABELS,
    })


# === 宿屋 ===
@router.post("/inn")
def view_inn(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None)):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    cost = user.level * settings.yado_dai
    if user.gold >= cost and user.current_hp < user.max_hp:
        user.gold -= cost
        user.current_hp = user.max_hp
        db.commit()
    return RedirectResponse("/view/status", status_code=303)


# === 戦闘 ===
@router.post("/battle/champion")
def view_battle_champion(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None)):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    result = battle_service.fight_champion(db, user)
    return templates.TemplateResponse("battle_result.html", {"request": request, "result": result})


@router.post("/battle/monster")
def view_battle_monster(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None), zone: str = Form(default="normal")):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    result = battle_service.fight_monster(db, user, zone)
    return templates.TemplateResponse("battle_result.html", {"request": request, "result": result})


@router.get("/battle/select", response_class=HTMLResponse)
def view_battle_select_list(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None)):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    opponents = db.query(Character).filter(Character.id != user.id).order_by(Character.level.desc()).limit(50).all()
    return templates.TemplateResponse("select_battle.html", {"request": request, "opponents": opponents})


@router.post("/battle/select")
def view_battle_select(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None), opponent_id: str = Form()):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    result = battle_service.fight_pvp(db, user, opponent_id)
    return templates.TemplateResponse("battle_result.html", {"request": request, "result": result})


# === 修改密碼 ===

@router.get("/change-password", response_class=HTMLResponse)
def view_change_password(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None)):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    return templates.TemplateResponse("change_password.html", {
        "request": request, "error": None, "success": None,
    })


@router.post("/change-password", response_class=HTMLResponse)
def view_change_password_post(
    request: Request,
    db: Session = Depends(get_db),
    ffa_token: str = Cookie(default=None),
    current_password: str = Form(...),
    recovery_word: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    from app.services.auth_service import hash_password, verify_password

    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")

    if not verify_password(current_password, user.password_hash):
        return templates.TemplateResponse("change_password.html", {
            "request": request, "error": "目前密碼錯誤", "success": None,
        })
    if recovery_word != user.password_recovery:
        return templates.TemplateResponse("change_password.html", {
            "request": request, "error": "密語錯誤", "success": None,
        })
    if new_password != confirm_password:
        return templates.TemplateResponse("change_password.html", {
            "request": request, "error": "新密碼不一致", "success": None,
        })
    if len(new_password) < 4:
        return templates.TemplateResponse("change_password.html", {
            "request": request, "error": "新密碼至少 4 個字元", "success": None,
        })

    user.password_hash = hash_password(new_password)
    db.commit()
    return templates.TemplateResponse("change_password.html", {
        "request": request, "error": None, "success": "密碼已變更成功！",
    })


# === 商店 ===
_ACCESSORY_SKILL_NAMES = {
    0: "-", 1: "HP小回復", 2: "HP中回復", 3: "HP大回復",
    4: "減傷12.5%", 5: "減傷25%", 6: "減傷50%",
    7: "攻擊+50%", 8: "攻擊x2", 9: "攻擊x3",
    10: "靈氣", 11: "乙太療癒", 12: "神聖", 13: "隕石",
    14: "乙太極光", 15: "次元傳送", 16: "減傷12.5%",
    17: "攻擊+50%", 18: "減傷25%", 19: "-",
    20: "減傷50%+攻擊x3", 21: "大十字", 22: "反彈",
    23: "完全回復", 24: "封印解放",
}


def _get_accessory_skill_names() -> dict[int, str]:
    return _ACCESSORY_SKILL_NAMES


def _shop_view(request: Request, db: Session, user: Character, shop_type: str):
    equip = user.equipment
    job = user.job_class
    if shop_type == "weapon":
        items_raw = (db.query(WeaponCatalog)
                     .filter(WeaponCatalog.shop_tier == job)
                     .order_by(WeaponCatalog.price).all())
        items = [{"id": w.id, "name": w.name, "stat_value": w.attack, "price": w.price} for w in items_raw]
        current = {"name": equip.weapon_name, "stat_label": "攻擊力", "stat_value": equip.weapon_attack} if equip and equip.weapon_name != "徒手" else None
        return "武器店", "攻擊力", items, current
    elif shop_type == "armor":
        items_raw = (db.query(ArmorCatalog)
                     .filter(ArmorCatalog.shop_tier == job)
                     .order_by(ArmorCatalog.price).all())
        items = [{"id": a.id, "name": a.name, "stat_value": a.defense, "price": a.price} for a in items_raw]
        current = {"name": equip.armor_name, "stat_label": "防禦力", "stat_value": equip.armor_defense} if equip and equip.armor_name != "布衣" else None
        return "防具店", "防禦力", items, current
    else:
        items_raw = (db.query(AccessoryCatalog)
                     .filter(AccessoryCatalog.shop_tier == job)
                     .order_by(AccessoryCatalog.price).all())
        skill_names = _get_accessory_skill_names()
        items = []
        for a in items_raw:
            bonuses = []
            for stat, label in [("str_bonus", "STR"), ("mag_bonus", "MAG"), ("fai_bonus", "FAI"),
                                ("vit_bonus", "VIT"), ("dex_bonus", "DEX"), ("spd_bonus", "SPD"),
                                ("cha_bonus", "CHA"), ("karma_bonus", "業")]:
                v = getattr(a, stat, 0)
                if v:
                    bonuses.append(f"{label}+{v}")
            for stat, label in [("accuracy_bonus", "命中"), ("evasion_bonus", "迴避"), ("critical_bonus", "暴擊")]:
                v = getattr(a, stat, 0)
                if v:
                    bonuses.append(f"{label}+{v}")
            items.append({
                "id": a.id, "name": a.name, "price": a.price,
                "bonuses": "　".join(bonuses) if bonuses else "-",
                "skill_name": skill_names.get(a.skill_id, "-"),
                "description": a.description or "",
            })
        current = {"name": equip.accessory_name, "stat_label": "效果", "stat_value": "-"} if equip and equip.accessory_name != "無" else None
        return "飾品店", "效果", items, current


@router.get("/shop", response_class=HTMLResponse)
def view_shop(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None), type: str = Query(default="weapon")):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    shop_name, stat_label, items, current = _shop_view(request, db, user, type)
    type_en_map = {"weapon": "WEAPON SHOP", "armor": "ARMOR SHOP", "accessory": "ACCESSORY SHOP"}
    return templates.TemplateResponse("shop.html", {
        "request": request, "shop_name": shop_name, "shop_type": type,
        "shop_type_en": type_en_map.get(type, ""),
        "stat_label": stat_label, "items": items, "current_item": current,
        "gold": int(user.gold), "bank": int(user.bank_savings),
    })


@router.post("/shop/{shop_type}/buy")
def view_shop_buy(shop_type: str, request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None), item_id: int = Form()):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    if shop_type == "weapon":
        shop_service.buy_weapon(db, user, item_id)
    elif shop_type == "armor":
        shop_service.buy_armor(db, user, item_id)
    else:
        shop_service.buy_accessory(db, user, item_id)
    return RedirectResponse(f"/view/shop?type={shop_type}", status_code=303)


@router.post("/shop/{shop_type}/sell")
def view_shop_sell(shop_type: str, request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None)):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    if shop_type == "weapon":
        shop_service.sell_weapon(db, user)
    elif shop_type == "armor":
        shop_service.sell_armor(db, user)
    else:
        shop_service.sell_accessory(db, user)
    return RedirectResponse(f"/view/shop?type={shop_type}", status_code=303)


# === 銀行 ===
@router.get("/bank", response_class=HTMLResponse)
def view_bank(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None)):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    return templates.TemplateResponse("bank.html", {"request": request, "gold": int(user.gold), "bank": int(user.bank_savings)})


@router.post("/bank/deposit")
def view_bank_deposit(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None), amount: int = Form()):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    amt = amount * 1000
    if user.gold >= amt:
        user.gold -= amt
        user.bank_savings += amt
        db.commit()
    return RedirectResponse("/view/bank", status_code=303)


@router.post("/bank/withdraw")
def view_bank_withdraw(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None), amount: int = Form()):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    amt = amount * 1000
    if user.bank_savings >= amt:
        user.bank_savings -= amt
        user.gold += amt
        db.commit()
    return RedirectResponse("/view/bank", status_code=303)


# === 転職 ===
@router.get("/job", response_class=HTMLResponse)
def view_job(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None)):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    jobs = _load_jobs()
    from app.models.job_mastery import JobMastery
    from app.services.character_service import _check_job_available
    masteries = {m.job_class: m.mastery_level for m in db.query(JobMastery).filter(JobMastery.character_id == user.id).all()}
    masteries[user.job_class] = user.job_level
    job_list = []
    for k, v in jobs.items():
        jid = int(k)
        m = masteries.get(jid, 0)
        err = _check_job_available(user, jid, v, masteries) if jid != user.job_class else None
        job_list.append({
            "id": jid, "name": v["name"], "mastery": m, "mastered": m >= 60,
            "available": err is None and jid != user.job_class,
            "locked_reason": err,
        })
    current_name = jobs.get(str(user.job_class), {}).get("name", "不明")
    return templates.TemplateResponse("job_change.html", {
        "request": request, "jobs": job_list, "current_job": user.job_class,
        "current_job_name": current_name, "current_job_level": user.job_level,
    })


@router.post("/job/change")
def view_job_change(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None), job_class: int = Form()):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    character_service.change_job(db, user, job_class)
    return RedirectResponse("/view/job", status_code=303)


# === 排行榜 ===
@router.get("/ranking", response_class=HTMLResponse)
def view_ranking(request: Request, db: Session = Depends(get_db), category: str = Query(default="level")):
    rankings = ranking_service.get_ranking(db, category)
    return templates.TemplateResponse("ranking.html", {
        "request": request, "rankings": rankings, "current": category,
        "categories": list(ranking_service.RANKING_CATEGORIES.keys()),
    })


# === 訊息 ===
@router.get("/message", response_class=HTMLResponse)
def view_message(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None)):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    inbox = db.query(Message).filter(Message.recipient_id == user.id).order_by(Message.created_at.desc()).limit(30).all()
    broadcasts = db.query(BroadcastMessage).order_by(BroadcastMessage.created_at.desc()).limit(10).all()
    return templates.TemplateResponse("message.html", {
        "request": request,
        "inbox": [{"sender_name": m.sender_name, "content": m.content} for m in inbox],
        "broadcasts": [{"sender_name": b.sender_name, "content": b.content} for b in broadcasts],
    })


@router.post("/message/send")
def view_message_send(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None), recipient_id: str = Form(), content: str = Form()):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    recipient = db.query(Character).filter(Character.id == recipient_id).first()
    if recipient:
        msg = Message(sender_id=user.id, sender_name=user.name, recipient_id=recipient_id, content=content, created_at=int(time.time()))
        db.add(msg)
        db.commit()
    return RedirectResponse("/view/message", status_code=303)


# === 武道会 ===
@router.get("/tournament", response_class=HTMLResponse)
def view_tournament(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None)):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    # 簡易顯示：透過 API 呼叫
    return templates.TemplateResponse("battle_result.html", {
        "request": request,
        "result": {"outcome": "info", "rounds": 0, "battle_log": ["請透過 API 開催武道會: POST /tournament"]},
    })


# === 倉庫 ===
def _warehouse_items(db: Session, user: Character):
    """查詢倉庫物品並聯結目錄資料。"""
    wh_items = db.query(WarehouseItem).filter(WarehouseItem.character_id == user.id).order_by(WarehouseItem.item_type, WarehouseItem.slot_index).all()
    weapons, armors, accessories = [], [], []
    for w in wh_items:
        if w.item_type == "weapon":
            cat = db.query(WeaponCatalog).filter(WeaponCatalog.id == w.catalog_id).first()
            if cat:
                weapons.append({"wh_id": w.id, "name": cat.name, "attack": cat.attack, "price": cat.price})
        elif w.item_type == "armor":
            cat = db.query(ArmorCatalog).filter(ArmorCatalog.id == w.catalog_id).first()
            if cat:
                armors.append({"wh_id": w.id, "name": cat.name, "defense": cat.defense, "price": cat.price})
        elif w.item_type == "accessory":
            cat = db.query(AccessoryCatalog).filter(AccessoryCatalog.id == w.catalog_id).first()
            if cat:
                accessories.append({"wh_id": w.id, "name": cat.name, "description": cat.description or "-", "price": cat.price})
    return weapons, armors, accessories


@router.get("/warehouse", response_class=HTMLResponse)
def view_warehouse(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None)):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    weapons, armors, accessories = _warehouse_items(db, user)
    return templates.TemplateResponse("warehouse.html", {
        "request": request, "char": user, "equip": user.equipment,
        "weapons": weapons, "armors": armors, "accessories": accessories,
    })


@router.post("/warehouse/equip")
def view_warehouse_equip(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None), warehouse_item_id: int = Form()):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    wh = db.query(WarehouseItem).filter(WarehouseItem.id == warehouse_item_id, WarehouseItem.character_id == user.id).first()
    if not wh:
        return RedirectResponse("/view/warehouse", status_code=303)
    equip = user.equipment
    # 將目前裝備存回倉庫，再裝上新的
    if wh.item_type == "weapon":
        if equip.weapon_name != "徒手":
            # 找到目前武器的 catalog_id
            old_cat = db.query(WeaponCatalog).filter(WeaponCatalog.name == equip.weapon_name).first()
            if old_cat:
                db.add(WarehouseItem(character_id=user.id, item_type="weapon", catalog_id=old_cat.id, slot_index=0))
        cat = db.query(WeaponCatalog).filter(WeaponCatalog.id == wh.catalog_id).first()
        if cat:
            equip.weapon_name = cat.name
            equip.weapon_attack = cat.attack
            equip.weapon_accuracy = cat.accuracy_bonus
    elif wh.item_type == "armor":
        if equip.armor_name != "布衣":
            old_cat = db.query(ArmorCatalog).filter(ArmorCatalog.name == equip.armor_name).first()
            if old_cat:
                db.add(WarehouseItem(character_id=user.id, item_type="armor", catalog_id=old_cat.id, slot_index=0))
        cat = db.query(ArmorCatalog).filter(ArmorCatalog.id == wh.catalog_id).first()
        if cat:
            equip.armor_name = cat.name
            equip.armor_defense = cat.defense
            equip.armor_evasion = cat.evasion_bonus
    elif wh.item_type == "accessory":
        if equip.accessory_name != "無":
            old_cat = db.query(AccessoryCatalog).filter(AccessoryCatalog.name == equip.accessory_name).first()
            if old_cat:
                db.add(WarehouseItem(character_id=user.id, item_type="accessory", catalog_id=old_cat.id, slot_index=0))
        cat = db.query(AccessoryCatalog).filter(AccessoryCatalog.id == wh.catalog_id).first()
        if cat:
            equip.accessory_name = cat.name
            equip.accessory_skill_id = cat.skill_id
            equip.acs_str = cat.str_bonus
            equip.acs_mag = cat.mag_bonus
            equip.acs_fai = cat.fai_bonus
            equip.acs_vit = cat.vit_bonus
            equip.acs_dex = cat.dex_bonus
            equip.acs_spd = cat.spd_bonus
            equip.acs_cha = cat.cha_bonus
            equip.acs_karma = cat.karma_bonus
            equip.acs_accuracy = cat.accuracy_bonus
            equip.acs_evasion = cat.evasion_bonus
            equip.acs_critical = cat.critical_bonus
    db.delete(wh)
    db.commit()
    return RedirectResponse("/view/warehouse", status_code=303)


@router.post("/warehouse/unequip")
def view_warehouse_unequip(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None), item_type: str = Form()):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    equip = user.equipment
    count = db.query(WarehouseItem).filter(WarehouseItem.character_id == user.id, WarehouseItem.item_type == item_type).count()
    if count >= settings.item_max:
        return RedirectResponse("/view/warehouse", status_code=303)
    if item_type == "weapon" and equip.weapon_name != "徒手":
        cat = db.query(WeaponCatalog).filter(WeaponCatalog.name == equip.weapon_name).first()
        if cat:
            db.add(WarehouseItem(character_id=user.id, item_type="weapon", catalog_id=cat.id, slot_index=count))
        equip.weapon_name = "徒手"
        equip.weapon_attack = 0
        equip.weapon_accuracy = 0
    elif item_type == "armor" and equip.armor_name != "布衣":
        cat = db.query(ArmorCatalog).filter(ArmorCatalog.name == equip.armor_name).first()
        if cat:
            db.add(WarehouseItem(character_id=user.id, item_type="armor", catalog_id=cat.id, slot_index=count))
        equip.armor_name = "布衣"
        equip.armor_defense = 0
        equip.armor_evasion = 0
    elif item_type == "accessory" and equip.accessory_name != "無":
        cat = db.query(AccessoryCatalog).filter(AccessoryCatalog.name == equip.accessory_name).first()
        if cat:
            db.add(WarehouseItem(character_id=user.id, item_type="accessory", catalog_id=cat.id, slot_index=count))
        equip.accessory_name = "無"
        equip.accessory_skill_id = 0
        equip.acs_str = equip.acs_mag = equip.acs_fai = equip.acs_vit = 0
        equip.acs_dex = equip.acs_spd = equip.acs_cha = equip.acs_karma = 0
        equip.acs_accuracy = equip.acs_evasion = equip.acs_critical = 0
    db.commit()
    return RedirectResponse("/view/warehouse", status_code=303)


@router.post("/warehouse/discard")
def view_warehouse_discard(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None), warehouse_item_id: int = Form()):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    wh = db.query(WarehouseItem).filter(WarehouseItem.id == warehouse_item_id, WarehouseItem.character_id == user.id).first()
    if wh:
        db.delete(wh)
        db.commit()
    return RedirectResponse("/view/warehouse", status_code=303)


# === 戰術 ===
def _load_tactics() -> dict:
    path = Path(__file__).parent.parent.parent / "data" / "tactics.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@router.get("/tactic", response_class=HTMLResponse)
def view_tactic(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None)):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    tactics = _load_tactics()
    job = user.job_class
    # 精通的職業也可用其戰技
    from app.models.job_mastery import JobMastery
    masteries = {m.job_class: m.mastery_level for m in db.query(JobMastery).filter(JobMastery.character_id == user.id).all()}
    mastered_jobs = {j for j, lv in masteries.items() if lv >= 60}
    # 篩選：普通戰鬥(0) + 目前職業的戰技 + 已精通職業的戰技
    tac_list = []
    for k, v in tactics.items():
        tid = int(k)
        tac_jobs = set(v.get("job_classes", []))
        is_available = (tid == 0) or (job in tac_jobs) or (tac_jobs & mastered_jobs)
        if not is_available:
            continue
        if v.get("mastery_required") and job not in mastered_jobs and not (tac_jobs & mastered_jobs):
            continue
        tac_list.append({"id": tid, "name": v["name"], "description": v["description"]})
    current = tactics.get(str(user.tactic_id), {"name": "普通戰鬥", "description": "普通地戰鬥。"})
    return templates.TemplateResponse("tactic.html", {
        "request": request,
        "current_tactic": user.tactic_id,
        "current_name": current["name"],
        "current_desc": current["description"],
        "tactics": tac_list,
    })


@router.post("/tactic/change")
def view_tactic_change(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None), tactic_id: int = Form()):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    from app.services.character_service import change_tactic
    change_tactic(db, user, tactic_id)
    return RedirectResponse("/view/tactic", status_code=303)


# === 管理後台 ===
def _check_admin_pw(password: str) -> bool:
    return password == settings.admin_password


def _admin_ctx(request: Request, password: str, db: Session) -> dict:
    """管理首頁共用 context。"""
    return {
        "request": request,
        "authed": True,
        "password": password,
        "limit_days": settings.limit_days,
        "total_characters": db.query(Character).count(),
        "total_weapons": db.query(WeaponCatalog).count(),
        "total_armors": db.query(ArmorCatalog).count(),
        "total_accessories": db.query(AccessoryCatalog).count(),
        "total_monsters": db.query(Monster).count(),
    }


@router.get("/admin", response_class=HTMLResponse)
def view_admin(request: Request, db: Session = Depends(get_db), p: str = Query(default="")):
    if not _check_admin_pw(p):
        return templates.TemplateResponse("admin.html", {"request": request, "authed": False})
    return templates.TemplateResponse("admin.html", _admin_ctx(request, p, db))


@router.post("/admin", response_class=HTMLResponse)
def view_admin_login(request: Request, db: Session = Depends(get_db), password: str = Form(default="")):
    if not _check_admin_pw(password):
        return templates.TemplateResponse("admin.html", {
            "request": request, "authed": False,
            "flash_message": "密碼錯誤", "flash_type": "error",
        })
    return templates.TemplateResponse("admin.html", _admin_ctx(request, password, db))


@router.get("/admin/characters", response_class=HTMLResponse)
def view_admin_characters(request: Request, db: Session = Depends(get_db), p: str = Query(default=""), sort: str = Query(default="level")):
    if not _check_admin_pw(p):
        return RedirectResponse("/view/admin")
    jobs = _load_jobs()
    now = int(time.time())

    if sort == "battles":
        chars = db.query(Character).order_by(Character.battle_count.desc()).all()
    elif sort == "last":
        chars = db.query(Character).order_by(Character.last_battle_time.desc()).all()
    else:
        chars = db.query(Character).order_by(Character.level.desc()).all()

    char_list = []
    for c in chars:
        last_bt = int(c.last_battle_time) if c.last_battle_time else 0
        if last_bt > 0:
            deadline = last_bt + settings.limit_days * 86400
            days_left = (deadline - now) // 86400
        else:
            days_left = None
        job_def = jobs.get(str(c.job_class), {})
        char_list.append({
            "id": c.id, "name": c.name, "level": c.level,
            "job_name": job_def.get("name", "???"),
            "battle_count": c.battle_count, "days_left": days_left,
            "protected": c.protected,
        })

    return templates.TemplateResponse("admin_characters.html", {
        "request": request, "password": p, "characters": char_list,
    })


@router.get("/admin/search", response_class=HTMLResponse)
def view_admin_search(request: Request, db: Session = Depends(get_db), p: str = Query(default=""), q: str = Query(default="")):
    if not _check_admin_pw(p):
        return RedirectResponse("/view/admin")
    char = db.query(Character).filter((Character.id == q) | (Character.name == q)).first()
    if not char:
        return templates.TemplateResponse("admin.html", {
            **_admin_ctx(request, p, db),
            "flash_message": f"找不到角色: {q}", "flash_type": "error",
        })
    jobs = _load_jobs()
    job_def = jobs.get(str(char.job_class), {})
    return templates.TemplateResponse("admin_detail.html", {
        "request": request, "password": p,
        "char": {
            "id": char.id, "name": char.name, "level": char.level,
            "job_name": job_def.get("name", "???"), "job_level": char.job_level,
            "current_hp": char.current_hp, "max_hp": char.max_hp,
            "exp": char.exp, "gold": int(char.gold), "bank": int(char.bank_savings),
            "str_": char.str_, "mag": char.mag, "fai": char.fai, "vit": char.vit,
            "dex": char.dex, "spd": char.spd, "cha": char.cha, "karma": char.karma,
            "battle_count": char.battle_count, "win_count": char.win_count,
            "protected": char.protected,
        },
    })


@router.post("/admin/protect", response_class=HTMLResponse)
def view_admin_protect(request: Request, db: Session = Depends(get_db), password: str = Form(), character_id: str = Form()):
    if not _check_admin_pw(password):
        return RedirectResponse("/view/admin")
    char = db.query(Character).filter(Character.id == character_id).first()
    if char:
        char.protected = 1
        db.commit()
    return RedirectResponse(f"/view/admin/characters?p={password}", status_code=303)


@router.post("/admin/delete", response_class=HTMLResponse)
def view_admin_delete(request: Request, db: Session = Depends(get_db), password: str = Form(), character_id: str = Form()):
    if not _check_admin_pw(password):
        return RedirectResponse("/view/admin")
    char = db.query(Character).filter(Character.id == character_id, Character.protected == 0).first()
    if char:
        db.delete(char)
        db.commit()
    return RedirectResponse(f"/view/admin/characters?p={password}", status_code=303)


@router.post("/admin/delete-inactive", response_class=HTMLResponse)
def view_admin_delete_inactive(request: Request, db: Session = Depends(get_db), password: str = Form()):
    if not _check_admin_pw(password):
        return RedirectResponse("/view/admin")
    cutoff = int(time.time()) - settings.limit_days * 86400
    deleted = db.query(Character).filter(
        Character.last_battle_time < cutoff, Character.protected == 0,
    ).delete()
    db.commit()
    return templates.TemplateResponse("admin.html", {
        **_admin_ctx(request, password, db),
        "flash_message": f"已刪除 {deleted} 個不活躍角色", "flash_type": "success",
    })


# === 職業管理 ===

def _load_jobs_path() -> Path:
    return Path(__file__).parent.parent.parent / "data" / "jobs.json"


def _save_jobs(jobs: dict) -> None:
    import json as _json
    path = _load_jobs_path()
    with open(path, "w", encoding="utf-8") as f:
        _json.dump(jobs, f, ensure_ascii=False, indent=2)
    # 清除引擎快取
    from app.engine.level_up import _load_jobs as _engine_load
    import app.engine.level_up as _lu
    _lu._jobs_cache = None


@router.get("/admin/jobs", response_class=HTMLResponse)
def view_admin_jobs(request: Request, p: str = Query(default="")):
    if not _check_admin_pw(p):
        return RedirectResponse("/view/admin")
    jobs = _load_jobs()
    job_list = []
    for jid in sorted(jobs.keys(), key=lambda x: int(x)):
        j = jobs[jid]
        job_list.append({
            "id": jid, "name": j["name"], "multiplier": j.get("multiplier", 1),
            "levelup_ranges": j.get("levelup_ranges", []),
            "stat_requirements": j.get("stat_requirements", {}),
            "prerequisite_masteries": j.get("prerequisite_masteries", {}),
        })
    return templates.TemplateResponse("admin_jobs.html", {
        "request": request, "password": p, "jobs": job_list,
    })


@router.get("/admin/jobs/edit", response_class=HTMLResponse)
def view_admin_job_edit(request: Request, p: str = Query(default=""), job_id: str = Query(default="")):
    if not _check_admin_pw(p):
        return RedirectResponse("/view/admin")
    jobs = _load_jobs()
    if job_id not in jobs:
        return RedirectResponse(f"/view/admin/jobs?p={p}")
    j = jobs[job_id]
    return templates.TemplateResponse("admin_job_edit.html", {
        "request": request, "password": p, "is_new": False,
        "job": {"id": job_id, **j},
    })


@router.post("/admin/jobs/edit", response_class=HTMLResponse)
def view_admin_job_save(request: Request, password: str = Form(), job_id: str = Form(),
                        name: str = Form(), multiplier: int = Form(),
                        lr_0: int = Form(), lr_1: int = Form(), lr_2: int = Form(),
                        lr_3: int = Form(), lr_4: int = Form(), lr_5: int = Form(),
                        lr_6: int = Form(), lr_7: int = Form(),
                        attack_stats: str = Form(), stat_requirements: str = Form(),
                        prerequisite_masteries: str = Form(default="")):
    if not _check_admin_pw(password):
        return RedirectResponse("/view/admin")
    jobs = _load_jobs()
    if job_id not in jobs:
        return RedirectResponse(f"/view/admin/jobs?p={password}")

    jobs[job_id]["name"] = name
    jobs[job_id]["multiplier"] = multiplier
    jobs[job_id]["levelup_ranges"] = [lr_0, lr_1, lr_2, lr_3, lr_4, lr_5, lr_6, lr_7]
    jobs[job_id]["attack_stats"] = _parse_attack_stats(attack_stats)
    jobs[job_id]["stat_requirements"] = _parse_kv_int(stat_requirements)
    jobs[job_id]["prerequisite_masteries"] = _parse_kv_int(prerequisite_masteries)
    _save_jobs(jobs)
    return RedirectResponse(f"/view/admin/jobs?p={password}", status_code=303)


@router.get("/admin/jobs/add", response_class=HTMLResponse)
def view_admin_job_add(request: Request, p: str = Query(default="")):
    if not _check_admin_pw(p):
        return RedirectResponse("/view/admin")
    jobs = _load_jobs()
    next_id = max((int(k) for k in jobs), default=-1) + 1
    return templates.TemplateResponse("admin_job_edit.html", {
        "request": request, "password": p, "is_new": True,
        "job": {}, "next_id": next_id,
    })


@router.post("/admin/jobs/add", response_class=HTMLResponse)
def view_admin_job_add_save(request: Request, password: str = Form(), job_id: int = Form(),
                            name: str = Form(), multiplier: int = Form(),
                            lr_0: int = Form(), lr_1: int = Form(), lr_2: int = Form(),
                            lr_3: int = Form(), lr_4: int = Form(), lr_5: int = Form(),
                            lr_6: int = Form(), lr_7: int = Form(),
                            attack_stats: str = Form(), stat_requirements: str = Form(),
                            prerequisite_masteries: str = Form(default="")):
    if not _check_admin_pw(password):
        return RedirectResponse("/view/admin")
    jobs = _load_jobs()
    jid = str(job_id)
    jobs[jid] = {
        "name": name,
        "attack_stats": _parse_attack_stats(attack_stats),
        "multiplier": multiplier,
        "levelup_ranges": [lr_0, lr_1, lr_2, lr_3, lr_4, lr_5, lr_6, lr_7],
        "stat_requirements": _parse_kv_int(stat_requirements),
        "prerequisite_masteries": _parse_kv_int(prerequisite_masteries),
    }
    _save_jobs(jobs)
    return RedirectResponse(f"/view/admin/jobs?p={password}", status_code=303)


def _parse_attack_stats(text: str) -> list:
    result = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(",", 1)
        if len(parts) == 2:
            result.append([parts[0].strip(), parts[1].strip()])
    return result or [["rand", "str"]]


def _parse_kv_int(text: str) -> dict:
    result = {}
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(":", 1)
        if len(parts) == 2:
            try:
                result[parts[0].strip()] = int(parts[1].strip())
            except ValueError:
                pass
    return result


# === 道具一覽 ===

@router.get("/admin/items", response_class=HTMLResponse)
def view_admin_items(request: Request, db: Session = Depends(get_db), p: str = Query(default=""), tab: str = Query(default="weapon")):
    if not _check_admin_pw(p):
        return RedirectResponse("/view/admin")

    weapon_count = db.query(WeaponCatalog).count()
    armor_count = db.query(ArmorCatalog).count()
    accessory_count = db.query(AccessoryCatalog).count()

    items = []
    if tab == "weapon":
        items = db.query(WeaponCatalog).order_by(WeaponCatalog.id).all()
    elif tab == "armor":
        items = db.query(ArmorCatalog).order_by(ArmorCatalog.id).all()
    elif tab == "accessory":
        items = db.query(AccessoryCatalog).order_by(AccessoryCatalog.id).all()

    return templates.TemplateResponse("admin_items.html", {
        "request": request, "password": p, "tab": tab, "items": items,
        "weapon_count": weapon_count, "armor_count": armor_count, "accessory_count": accessory_count,
    })


# === 必殺技一覽 ===

@router.get("/admin/skills", response_class=HTMLResponse)
def view_admin_skills(request: Request, p: str = Query(default="")):
    if not _check_admin_pw(p):
        return RedirectResponse("/view/admin")

    jobs = _load_jobs()
    data_dir = Path(__file__).parent.parent.parent / "data"

    # 戰術
    tactics_path = data_dir / "tactics.json"
    tactics_raw = {}
    if tactics_path.exists():
        with open(tactics_path, encoding="utf-8") as f:
            tactics_raw = json.load(f)

    tactics = []
    for tid in sorted(tactics_raw.keys(), key=lambda x: int(x)):
        t = tactics_raw[tid]
        job_names = [jobs.get(str(jc), {}).get("name", f"職{jc}") for jc in t.get("job_classes", [])]
        tactics.append({
            "id": tid, "name": t.get("name", ""), "description": t.get("description", ""),
            "mastery_required": t.get("mastery_required", False), "job_names": job_names,
        })

    # 角色技能
    char_skills_path = data_dir / "skills" / "character_skills.json"
    char_skills_raw = {}
    if char_skills_path.exists():
        with open(char_skills_path, encoding="utf-8") as f:
            char_skills_raw = json.load(f)

    char_skills = []
    for sid in sorted(char_skills_raw.keys(), key=lambda x: int(x)):
        s = char_skills_raw[sid]
        if s is None:
            continue
        hissatu = s.get("hissatu")
        atowaza = s.get("atowaza")
        hissatu_desc = ""
        if hissatu and hissatu.get("effects"):
            msgs = [e.get("message", "") for e in hissatu["effects"] if e.get("message")]
            hissatu_desc = " / ".join(msgs) if msgs else "（效果定義）"
        char_skills.append({
            "id": sid, "job_name": jobs.get(sid, {}).get("name", f"職{sid}"),
            "has_hissatu": hissatu is not None, "hissatu_desc": hissatu_desc,
            "has_atowaza": atowaza is not None,
        })

    # 飾品技能
    acs_skills_path = data_dir / "skills" / "accessory_skills.json"
    acs_skills_raw = {}
    if acs_skills_path.exists():
        with open(acs_skills_path, encoding="utf-8") as f:
            acs_skills_raw = json.load(f)

    acs_skills = []
    for aid in sorted(acs_skills_raw.keys(), key=lambda x: int(x)):
        s = acs_skills_raw[aid]
        if s is None:
            continue
        trigger = s.get("trigger", {}).get("type", "?")
        effects = []
        for e in s.get("effects", []):
            etype = e.get("type", "?")
            msg = e.get("message", "")
            effects.append(f"{etype}: {msg}" if msg else etype)
        acs_skills.append({
            "id": aid, "trigger": trigger, "effects": " / ".join(effects),
        })

    return templates.TemplateResponse("admin_skills.html", {
        "request": request, "password": p,
        "tactics": tactics, "char_skills": char_skills, "acs_skills": acs_skills,
    })


# === 技能 JSON 管理 ===

def _describe_phase(phase_data: dict | None) -> str:
    """從 phase 取得描述文字。"""
    if not phase_data:
        return ""
    msgs = [e.get("message", "") for e in phase_data.get("effects", []) if e.get("message")]
    return " / ".join(msgs) if msgs else "（效果定義）"


@router.get("/admin/skills/list", response_class=HTMLResponse)
def view_admin_skill_list(request: Request, p: str = Query(default=""), cat: str = Query(default="character")):
    if not _check_admin_pw(p):
        return RedirectResponse("/view/admin")
    if cat not in skill_file_service.SKILL_FILES:
        cat = "character"

    data = skill_file_service.load_skill_file(cat)
    is_dual = cat in skill_file_service.DUAL_PHASE_CATEGORIES

    skills = []
    for sid in sorted(data.keys(), key=lambda x: int(x)):
        s = data[sid]
        entry = {"id": sid, "is_null": s is None}
        if is_dual:
            hissatu = s.get("hissatu") if s else None
            atowaza = s.get("atowaza") if s else None
            entry["has_hissatu"] = hissatu is not None
            entry["hissatu_desc"] = _describe_phase(hissatu)
            entry["has_atowaza"] = atowaza is not None
            entry["atowaza_desc"] = _describe_phase(atowaza)
        else:
            if s:
                entry["trigger_type"] = s.get("trigger", {}).get("type", "?")
                effect_parts = []
                for e in s.get("effects", []):
                    etype = e.get("type", "?")
                    msg = e.get("message", "")
                    effect_parts.append(f"{etype}: {msg}" if msg else etype)
                entry["effects_desc"] = " / ".join(effect_parts)
            else:
                entry["trigger_type"] = "-"
                entry["effects_desc"] = "-"
        skills.append(entry)

    counts = {}
    for c in skill_file_service.SKILL_FILES:
        d = skill_file_service.load_skill_file(c)
        counts[c] = len(d)

    return templates.TemplateResponse("admin_skill_list.html", {
        "request": request, "password": p, "cat": cat,
        "cat_label": skill_file_service.CATEGORY_LABELS[cat],
        "categories": skill_file_service.CATEGORY_LABELS,
        "is_dual": is_dual, "skills": skills, "counts": counts,
    })


@router.get("/admin/skills/edit", response_class=HTMLResponse)
def view_admin_skill_edit(
    request: Request,
    p: str = Query(default=""),
    cat: str = Query(default="character"),
    id: str = Query(default="0"),
    is_new: str = Query(default="0"),
):
    if not _check_admin_pw(p):
        return RedirectResponse("/view/admin")
    if cat not in skill_file_service.SKILL_FILES:
        cat = "character"

    is_new_flag = is_new == "1"
    skill_data = None if is_new_flag else skill_file_service.get_skill(cat, id)
    is_dual = cat in skill_file_service.DUAL_PHASE_CATEGORIES

    return templates.TemplateResponse("admin_skill_edit.html", {
        "request": request, "password": p, "cat": cat,
        "cat_label": skill_file_service.CATEGORY_LABELS[cat],
        "skill_id": id, "is_new": is_new_flag, "is_dual": is_dual,
        "skill_data": skill_data, "errors": [],
    })


@router.post("/admin/skills/save", response_class=HTMLResponse)
def view_admin_skill_save(
    request: Request,
    password: str = Form(...),
    cat: str = Form(...),
    skill_id: str = Form(...),
    is_new: str = Form(default="0"),
    # 扁平格式欄位
    set_null: str = Form(default=""),
    trigger_type: str = Form(default="always"),
    threshold: int = Form(default=80),
    chance: float = Form(default=0.5),
    effects: str = Form(default="[]"),
    # 角色技能雙階段
    hissatu_null: str = Form(default=""),
    hissatu_trigger_type: str = Form(default="skill_rate_check"),
    hissatu_threshold: int = Form(default=80),
    hissatu_chance: float = Form(default=0.5),
    hissatu_effects: str = Form(default="[]"),
    atowaza_null: str = Form(default=""),
    atowaza_trigger_type: str = Form(default="skill_rate_check"),
    atowaza_threshold: int = Form(default=80),
    atowaza_chance: float = Form(default=0.5),
    atowaza_effects: str = Form(default="[]"),
):
    if not _check_admin_pw(password):
        return RedirectResponse("/view/admin")

    is_dual = cat in skill_file_service.DUAL_PHASE_CATEGORIES
    errors: list[str] = []
    skill_data = None

    def _build_trigger(ttype: str, th: int, ch: float) -> dict:
        trigger: dict = {"type": ttype}
        if ttype == "skill_rate_check":
            trigger["threshold"] = th
        elif ttype == "random":
            trigger["chance"] = ch
        return trigger

    def _parse_effects_json(raw: str, label: str) -> list[dict] | None:
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                errors.append(f"{label}: Effects 應為 JSON 陣列")
                return None
            return parsed
        except json.JSONDecodeError as e:
            errors.append(f"{label}: JSON 語法錯誤 — {e}")
            return None

    if is_dual:
        skill_data = {}
        for phase, null_val, tt, th, ch, eff_raw in [
            ("hissatu", hissatu_null, hissatu_trigger_type, hissatu_threshold, hissatu_chance, hissatu_effects),
            ("atowaza", atowaza_null, atowaza_trigger_type, atowaza_threshold, atowaza_chance, atowaza_effects),
        ]:
            if null_val:
                skill_data[phase] = None
            else:
                eff_list = _parse_effects_json(eff_raw, phase)
                if eff_list is not None:
                    skill_data[phase] = {
                        "trigger": _build_trigger(tt, th, ch),
                        "effects": eff_list,
                    }
                else:
                    skill_data[phase] = None
    else:
        if set_null:
            skill_data = None
        else:
            eff_list = _parse_effects_json(effects, "effects")
            if eff_list is not None:
                skill_data = {
                    "trigger": _build_trigger(trigger_type, threshold, chance),
                    "effects": eff_list,
                }

    # 驗證
    if not errors:
        validation_errors = skill_file_service.validate_skill(cat, skill_data)
        errors.extend(validation_errors)

    if errors:
        return templates.TemplateResponse("admin_skill_edit.html", {
            "request": request, "password": password, "cat": cat,
            "cat_label": skill_file_service.CATEGORY_LABELS.get(cat, cat),
            "skill_id": skill_id, "is_new": is_new == "1", "is_dual": is_dual,
            "skill_data": skill_data, "errors": errors,
        })

    skill_file_service.save_skill(cat, skill_id, skill_data)
    return RedirectResponse(
        f"/view/admin/skills/list?p={password}&cat={cat}",
        status_code=303,
    )


@router.post("/admin/skills/delete")
def view_admin_skill_delete(
    password: str = Form(...),
    cat: str = Form(...),
    skill_id: str = Form(...),
):
    if not _check_admin_pw(password):
        return RedirectResponse("/view/admin")
    skill_file_service.delete_skill(cat, skill_id)
    return RedirectResponse(
        f"/view/admin/skills/list?p={password}&cat={cat}",
        status_code=303,
    )


# === 刪除所有記錄 ===

@router.get("/admin/delete-all", response_class=HTMLResponse)
def view_admin_delete_all(request: Request, db: Session = Depends(get_db), p: str = Query(default="")):
    if not _check_admin_pw(p):
        return RedirectResponse("/view/admin")
    return templates.TemplateResponse("admin_delete_all.html", {
        "request": request, "password": p, "confirmed": False,
        "total_characters": db.query(Character).count(),
    })


@router.post("/admin/delete-all", response_class=HTMLResponse)
def view_admin_delete_all_confirm(request: Request, db: Session = Depends(get_db),
                                  password: str = Form(), confirm: str = Form(default=""),
                                  confirm_password: str = Form(default="")):
    if not _check_admin_pw(password) or confirm != "1" or confirm_password != settings.admin_password:
        return templates.TemplateResponse("admin_delete_all.html", {
            "request": request, "password": password, "confirmed": False,
            "total_characters": db.query(Character).count(),
            "flash_message": "密碼錯誤或未確認", "flash_type": "error",
        })
    deleted = db.query(Character).delete()
    db.commit()
    return templates.TemplateResponse("admin_delete_all.html", {
        "request": request, "password": password, "confirmed": True,
        "deleted_count": deleted,
    })


# === 道具編輯 ===

_ITEM_TYPE_LABELS = {"weapon": "武器", "armor": "防具", "accessory": "飾品"}


@router.get("/admin/items/edit", response_class=HTMLResponse)
def view_admin_item_edit(request: Request, db: Session = Depends(get_db),
                         p: str = Query(default=""), tab: str = Query(default="weapon"),
                         item_id: str = Query(default="")):
    if not _check_admin_pw(p):
        return RedirectResponse("/view/admin")

    is_new = item_id == "new"
    item = None
    if not is_new:
        iid = int(item_id)
        if tab == "weapon":
            item = db.query(WeaponCatalog).get(iid)
        elif tab == "armor":
            item = db.query(ArmorCatalog).get(iid)
        elif tab == "accessory":
            item = db.query(AccessoryCatalog).get(iid)
        if not item:
            return RedirectResponse(f"/view/admin/items?p={p}&tab={tab}")

    extra = {}
    if tab == "accessory":
        extra["accessory_skill_names"] = _ACCESSORY_SKILL_NAMES

    return templates.TemplateResponse("admin_item_edit.html", {
        "request": request, "password": p, "tab": tab, "is_new": is_new,
        "item": item, "type_label": _ITEM_TYPE_LABELS.get(tab, "道具"),
        **extra,
    })


@router.post("/admin/items/edit", response_class=HTMLResponse)
def view_admin_item_save(request: Request, db: Session = Depends(get_db),
                         password: str = Form(), tab: str = Form(), is_new: str = Form(),
                         item_id: int = Form(), name: str = Form(),
                         price: int = Form(default=0), shop_tier: int = Form(default=0),
                         # 武器
                         attack: int = Form(default=0), accuracy_bonus: int = Form(default=0),
                         # 防具
                         defense: int = Form(default=0), evasion_bonus: int = Form(default=0),
                         # 飾品
                         skill_id: int = Form(default=0),
                         str_bonus: int = Form(default=0), mag_bonus: int = Form(default=0),
                         fai_bonus: int = Form(default=0), vit_bonus: int = Form(default=0),
                         dex_bonus: int = Form(default=0), spd_bonus: int = Form(default=0),
                         cha_bonus: int = Form(default=0), karma_bonus: int = Form(default=0),
                         critical_bonus: int = Form(default=0),
                         description: str = Form(default="")):
    if not _check_admin_pw(password):
        return RedirectResponse("/view/admin")

    if tab == "weapon":
        item = db.query(WeaponCatalog).get(item_id) if is_new == "0" else None
        if not item:
            item = WeaponCatalog(id=item_id)
            db.add(item)
        item.name = name
        item.attack = attack
        item.price = price
        item.accuracy_bonus = accuracy_bonus
        item.shop_tier = shop_tier

    elif tab == "armor":
        item = db.query(ArmorCatalog).get(item_id) if is_new == "0" else None
        if not item:
            item = ArmorCatalog(id=item_id)
            db.add(item)
        item.name = name
        item.defense = defense
        item.price = price
        item.evasion_bonus = evasion_bonus
        item.shop_tier = shop_tier

    elif tab == "accessory":
        item = db.query(AccessoryCatalog).get(item_id) if is_new == "0" else None
        if not item:
            item = AccessoryCatalog(id=item_id)
            db.add(item)
        item.name = name
        item.price = price
        item.skill_id = skill_id
        item.str_bonus = str_bonus
        item.mag_bonus = mag_bonus
        item.fai_bonus = fai_bonus
        item.vit_bonus = vit_bonus
        item.dex_bonus = dex_bonus
        item.spd_bonus = spd_bonus
        item.cha_bonus = cha_bonus
        item.karma_bonus = karma_bonus
        item.accuracy_bonus = accuracy_bonus
        item.evasion_bonus = evasion_bonus
        item.critical_bonus = critical_bonus
        item.description = description
        item.shop_tier = shop_tier

    db.commit()
    return RedirectResponse(f"/view/admin/items?p={password}&tab={tab}", status_code=303)


@router.post("/admin/items/delete", response_class=HTMLResponse)
def view_admin_item_delete(request: Request, db: Session = Depends(get_db),
                           password: str = Form(), tab: str = Form(), item_id: int = Form()):
    if not _check_admin_pw(password):
        return RedirectResponse("/view/admin")

    if tab == "weapon":
        item = db.query(WeaponCatalog).get(item_id)
    elif tab == "armor":
        item = db.query(ArmorCatalog).get(item_id)
    elif tab == "accessory":
        item = db.query(AccessoryCatalog).get(item_id)
    else:
        item = None

    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse(f"/view/admin/items?p={password}&tab={tab}", status_code=303)


# === 魔物與地圖 ===

_ZONE_LABELS = {
    "low": "周邊探索（弱）",
    "normal": "附近的洞窟（強）",
    "high": "暗黑迷宮（很強）",
    "special": "米西迪亞之塔（極強）",
    "isekai": "異世界（Lv300+）",
    "genei": "幻影之城（隨機出現）",
    "boss0": "傳說之地 Lv0 — 傳聞中的祠堂",
    "boss1": "傳說之地 Lv1 — 古老神殿",
    "boss2": "傳說之地 Lv2 — 勇者之洞窟",
    "boss3": "傳說之地 Lv3 — 蓋亞之力",
}
_ZONE_ORDER = ["low", "normal", "high", "special", "genei", "isekai", "boss0", "boss1", "boss2", "boss3"]


@router.get("/admin/monsters", response_class=HTMLResponse)
def view_admin_monsters(request: Request, db: Session = Depends(get_db),
                        p: str = Query(default=""), zone: str = Query(default="low")):
    if not _check_admin_pw(p):
        return RedirectResponse("/view/admin")

    zone_counts = {}
    for z in _ZONE_ORDER:
        zone_counts[z] = db.query(Monster).filter(Monster.zone == z).count()

    monsters = db.query(Monster).filter(Monster.zone == zone).order_by(Monster.id).all()
    closed_zones = {zc.zone for zc in db.query(ZoneConfig).filter(ZoneConfig.open == False).all()}
    return templates.TemplateResponse("admin_monsters.html", {
        "request": request, "password": p, "current_zone": zone,
        "zone_labels": _ZONE_LABELS, "zone_order": _ZONE_ORDER,
        "zone_counts": zone_counts, "monsters": monsters,
        "closed_zones": closed_zones,
    })


@router.get("/admin/monsters/edit", response_class=HTMLResponse)
def view_admin_monster_edit(request: Request, db: Session = Depends(get_db),
                            p: str = Query(default=""), id: int = Query(default=0)):
    if not _check_admin_pw(p):
        return RedirectResponse("/view/admin")
    monster = db.query(Monster).get(id) if id else None
    if not monster:
        return RedirectResponse(f"/view/admin/monsters?p={p}")
    return templates.TemplateResponse("admin_monster_edit.html", {
        "request": request, "password": p, "monster": monster, "is_new": False,
        "zone_labels": _ZONE_LABELS, "zone_order": _ZONE_ORDER,
    })


@router.post("/admin/monsters/edit", response_class=HTMLResponse)
def view_admin_monster_save(request: Request, db: Session = Depends(get_db),
                            password: str = Form(), monster_id: int = Form(),
                            name: str = Form(), zone: str = Form(),
                            exp_reward: int = Form(default=0), damage_range: int = Form(default=0),
                            speed: int = Form(default=0), base_damage: int = Form(default=0),
                            evasion: int = Form(default=0), skill_id: int = Form(default=0),
                            critical_rate: int = Form(default=0), gold_drop: int = Form(default=0)):
    if not _check_admin_pw(password):
        return RedirectResponse("/view/admin")
    monster = db.query(Monster).get(monster_id)
    if not monster:
        return RedirectResponse(f"/view/admin/monsters?p={password}")
    monster.name = name
    monster.zone = zone
    monster.exp_reward = exp_reward
    monster.damage_range = damage_range
    monster.speed = speed
    monster.base_damage = base_damage
    monster.evasion = evasion
    monster.skill_id = skill_id
    monster.critical_rate = critical_rate
    monster.gold_drop = gold_drop
    db.commit()
    return RedirectResponse(f"/view/admin/monsters?p={password}&zone={zone}", status_code=303)


@router.get("/admin/monsters/add", response_class=HTMLResponse)
def view_admin_monster_add(request: Request, p: str = Query(default=""), zone: str = Query(default="low")):
    if not _check_admin_pw(p):
        return RedirectResponse("/view/admin")
    return templates.TemplateResponse("admin_monster_edit.html", {
        "request": request, "password": p, "is_new": True, "default_zone": zone,
        "monster": None,
        "zone_labels": _ZONE_LABELS, "zone_order": _ZONE_ORDER,
    })


@router.post("/admin/monsters/add", response_class=HTMLResponse)
def view_admin_monster_add_save(request: Request, db: Session = Depends(get_db),
                                password: str = Form(),
                                name: str = Form(), zone: str = Form(),
                                exp_reward: int = Form(default=0), damage_range: int = Form(default=0),
                                speed: int = Form(default=0), base_damage: int = Form(default=0),
                                evasion: int = Form(default=0), skill_id: int = Form(default=0),
                                critical_rate: int = Form(default=0), gold_drop: int = Form(default=0)):
    if not _check_admin_pw(password):
        return RedirectResponse("/view/admin")
    monster = Monster(name=name, zone=zone, exp_reward=exp_reward, damage_range=damage_range,
                      speed=speed, base_damage=base_damage, evasion=evasion, skill_id=skill_id,
                      critical_rate=critical_rate, gold_drop=gold_drop)
    db.add(monster)
    db.commit()
    return RedirectResponse(f"/view/admin/monsters?p={password}&zone={zone}", status_code=303)


@router.post("/admin/monsters/delete", response_class=HTMLResponse)
def view_admin_monster_delete(request: Request, db: Session = Depends(get_db),
                              password: str = Form(), monster_id: int = Form(), zone: str = Form(default="low")):
    if not _check_admin_pw(password):
        return RedirectResponse("/view/admin")
    monster = db.query(Monster).get(monster_id)
    if monster:
        db.delete(monster)
        db.commit()
    return RedirectResponse(f"/view/admin/monsters?p={password}&zone={zone}", status_code=303)


@router.post("/admin/monsters/toggle-zone", response_class=HTMLResponse)
def view_admin_toggle_zone(request: Request, db: Session = Depends(get_db),
                           password: str = Form(), zone: str = Form()):
    if not _check_admin_pw(password):
        return RedirectResponse("/view/admin")
    cfg = db.query(ZoneConfig).get(zone)
    if cfg:
        cfg.open = not cfg.open
    else:
        db.add(ZoneConfig(zone=zone, open=False))
    db.commit()
    return RedirectResponse(f"/view/admin/monsters?p={password}&zone={zone}", status_code=303)
