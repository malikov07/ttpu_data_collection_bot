from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class LangCb(CallbackData, prefix="lang"):
    code: str


class RegCb(CallbackData, prefix="reg"):
    # consent | correct | retake | done | submit | edit | back | return
    action: str


class EditFieldCb(CallbackData, prefix="ef"):
    # last_name | first_name | middle_name | gender | document | phone | group | photo | cv
    field: str
    value: str = ""  # gender: male | female


class GroupPickCb(CallbackData, prefix="gp"):
    # page | pick
    action: str
    group_id: int = 0
    page: int = 0


class StaffCb(CallbackData, prefix="st"):
    # groups | group | card | doc | close | edit | efield | egender | egroup | egpage | del | del_ok
    action: str
    group_id: int = 0
    student_id: int = 0
    page: int = 0
    value: str = ""


class AdminCb(CallbackData, prefix="adm"):
    # panel | groups | add_groups | group | rename | toggle | gdel | gdel_ok
    # | accounts | account | new | role | agroup | skipname | reset | active | adel | adel_ok
    # | settings | set
    action: str
    id: int = 0
    page: int = 0
    value: str = ""
