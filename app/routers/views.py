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
from app.models.online_player import OnlinePlayer
from app.models.warehouse import WarehouseItem
from app.services import auth_service, battle_service, character_service, ranking_service, shop_service

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

    return templates.TemplateResponse("status.html", {
        "request": request, "char": user, "equip": user.equipment,
        "job_name": job_name, "champion": champion, "cooldown": cooldown,
        "inn_cost": user.level * settings.yado_dai,
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


# === 商店 ===
def _shop_view(request: Request, db: Session, user: Character, shop_type: str):
    equip = user.equipment
    if shop_type == "weapon":
        items_raw = db.query(WeaponCatalog).order_by(WeaponCatalog.price).all()
        items = [{"id": w.id, "name": w.name, "stat_value": w.attack, "price": w.price} for w in items_raw]
        current = {"name": equip.weapon_name, "stat_label": "攻擊力", "stat_value": equip.weapon_attack} if equip and equip.weapon_name != "徒手" else None
        return "武器店", "攻擊力", items, current
    elif shop_type == "armor":
        items_raw = db.query(ArmorCatalog).order_by(ArmorCatalog.price).all()
        items = [{"id": a.id, "name": a.name, "stat_value": a.defense, "price": a.price} for a in items_raw]
        current = {"name": equip.armor_name, "stat_label": "防禦力", "stat_value": equip.armor_defense} if equip and equip.armor_name != "布衣" else None
        return "防具店", "防禦力", items, current
    else:
        items_raw = db.query(AccessoryCatalog).order_by(AccessoryCatalog.price).all()
        items = [{"id": a.id, "name": a.name, "stat_value": a.description or "-", "price": a.price} for a in items_raw]
        current = {"name": equip.accessory_name, "stat_label": "效果", "stat_value": "-"} if equip and equip.accessory_name != "無" else None
        return "飾品店", "效果", items, current


@router.get("/shop", response_class=HTMLResponse)
def view_shop(request: Request, db: Session = Depends(get_db), ffa_token: str = Cookie(default=None), type: str = Query(default="weapon")):
    user = _get_user(db, ffa_token)
    if not user:
        return RedirectResponse("/view/home")
    shop_name, stat_label, items, current = _shop_view(request, db, user, type)
    return templates.TemplateResponse("shop.html", {
        "request": request, "shop_name": shop_name, "shop_type": type,
        "stat_label": stat_label, "items": items, "current_item": current,
        "gold": int(user.gold),
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
