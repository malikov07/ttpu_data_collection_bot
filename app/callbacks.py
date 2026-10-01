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
    # prog (open a program; "" = the programs list) | pick
    action: str
    group_id: int = 0
    program: str = ""


class CertCb(CallbackData, prefix="cert"):
    # student: list | add | type | result | done | submit | del | del_ok
    action: str
    id: int = 0
    value: str = ""


class CertReviewCb(CallbackData, prefix="cr"):
    # staff: queue | student (id = student) | open | ok | no | skip (id = certificate)
    action: str
    id: int = 0


class StaffCb(CallbackData, prefix="st"):
    # groups | group | card | doc | close | edit | efield | egender | egroup | egprog | del | del_ok
    action: str
    group_id: int = 0
    student_id: int = 0
    page: int = 0
    value: str = ""


class AdminCb(CallbackData, prefix="adm"):
    # panel | groups | add_groups | group | rename | toggle | gdel | gdel_ok
    # | accounts | account | new | role | agroup | agroup_prog | skipname | reset | active | adel | adel_ok
    # | settings | set
    action: str
    id: int = 0
    page: int = 0
    value: str = ""
