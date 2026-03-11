from pydantic import BaseModel


class CharacterSummary(BaseModel):
    id: str
    name: str
    level: int
    job_class: int
    current_hp: int
    max_hp: int
    gold: int

    model_config = {"from_attributes": True}


class CharacterStatus(BaseModel):
    id: str
    name: str
    sex: int
    image_id: int
    level: int
    job_class: int
    job_level: int
    current_hp: int
    max_hp: int
    exp: int
    gold: int
    bank_savings: int
    str_: int
    mag: int
    fai: int
    vit: int
    dex: int
    spd: int
    cha: int
    karma: int
    battle_count: int
    win_count: int
    battle_cry: str
    available_battles: int
    tactic_id: int
    title_rank: int

    model_config = {"from_attributes": True}
