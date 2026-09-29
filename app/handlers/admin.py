"""Admin panel in the bot: groups, staff accounts, settings."""

from __future__ import annotations

import contextlib
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import keyboards as kb
from app.callbacks import AdminCb
from app.config import Settings
from app.db import repo
from app.db.models import Account, Group, StaffRole, Student, User
from app.db.repo import Access
from app.i18n import Translator, menu_buttons, variants
from app.services import edupage
from app.services.backup import run_backup
from app.services.passwords import normalize_username
from app.services.prefs import Prefs, load_prefs, save_prefs
from app.services.validators import parse_group_names
from app.states import AdminStates
from app.views import account_roles

log = logging.getLogger(__name__)
router = Router(name="admin")


def is_admin(_event: object, access: Access) -> bool:
    return access.is_admin


router.message.filter(is_admin)
router.callback_query.filter(is_admin)

TEXT = (F.text, ~F.text.startswith("/"), ~F.text.in_(menu_buttons()))


def actor(access: Access, telegram_id: int) -> str:
    return repo.actor_of(access, telegram_id)


async def render_panel(session: AsyncSession, _: Translator, prefs: Prefs) -> str:
    return _(
        "admin.panel",
        students=await session.scalar(select(func.count(Student.id))) or 0,
        groups=await session.scalar(select(func.count(Group.id)).where(Group.is_active.is_(True))) or 0,
        accounts=await session.scalar(select(func.count(Account.id))) or 0,
        registration=_("admin.open") if prefs.registration_open else _("admin.closed"),
    )


@router.message(Command("admin"))
@router.message(F.text.in_(variants("btn.admin")))
async def cmd_admin(message: Message, state: FSMContext, session: AsyncSession, _: Translator, prefs: Prefs) -> None:
    await state.clear()
    await message.answer(await render_panel(session, _, prefs), reply_markup=kb.admin_panel_kb(_))


@router.callback_query(AdminCb.filter(F.action == "panel"))
async def on_panel(cb: CallbackQuery, state: FSMContext, session: AsyncSession, _: Translator, settings: Settings) -> None:
    await state.clear()
    await cb.answer()
    prefs = await load_prefs(session, settings)
    await cb.message.edit_text(await render_panel(session, _, prefs), reply_markup=kb.admin_panel_kb(_))


@router.message(Command("backup"))
async def cmd_backup(
    message: Message, user: User, _: Translator, settings: Settings, bot: Bot, sessions: async_sessionmaker[AsyncSession]
) -> None:
    status = await message.answer(_("backup.started"))
    try:
        await run_backup(bot, settings, sessions, chat_ids=[user.id])
    except Exception:
        log.exception("Manual backup failed")
        await message.answer(_("backup.failed"))
    finally:
        with contextlib.suppress(Exception):
            await status.delete()


# ------------------------------------------------------------------ groups


async def _groups_view(session: AsyncSession, _: Translator, settings: Settings, page: int = 0):
    groups = await repo.list_groups(session, active_only=False)
    return _("admin.groups", n=len(groups)), kb.admin_groups_kb(_, groups, page, edupage=bool(settings.edupage_url))


@router.callback_query(AdminCb.filter(F.action == "groups"))
async def on_groups(
    cb: CallbackQuery, callback_data: AdminCb, state: FSMContext, session: AsyncSession, _: Translator, settings: Settings
) -> None:
    await state.clear()
    text, markup = await _groups_view(session, _, settings, callback_data.page)
    await cb.answer()
    await cb.message.edit_text(text, reply_markup=markup)


@router.callback_query(AdminCb.filter(F.action == "edupage"))
async def on_edupage_import(
    cb: CallbackQuery, state: FSMContext, session: AsyncSession, access: Access, _: Translator, settings: Settings
) -> None:
    await state.clear()
    await cb.answer()
    if not settings.edupage_url:
        return
    await cb.message.edit_text(_("admin.edupage_loading"))
    try:
        names = await edupage.fetch_group_names(settings.edupage_url)
    except edupage.EdupageError as e:
        log.warning("EduPage import failed: %s", e)
        text, markup = await _groups_view(session, _, settings)
        await cb.message.edit_text(_("admin.edupage_failed") + "\n\n" + text, reply_markup=markup)
        return
    result = await repo.import_groups(session, names)
    await repo.audit(
        session, actor(access, cb.from_user.id), "group.import", entity="group",
        summary=f"EduPage: +{len(result.added)}", details={"added": ", ".join(result.added)} if result.added else None,
    )
    await session.commit()
    report = _(
        "admin.edupage_done",
        total=len(names),
        added=escape(", ".join(result.added)) or "—",
        existing=len(result.existing),
    )
    if result.missing:
        report += "\n\n" + _("admin.edupage_missing", names=escape(", ".join(result.missing)))
    text, markup = await _groups_view(session, _, settings)
    await cb.message.edit_text(report + "\n\n" + text, reply_markup=markup)


@router.callback_query(AdminCb.filter(F.action == "add_groups"))
async def on_add_groups(cb: CallbackQuery, state: FSMContext, _: Translator) -> None:
    await state.set_state(AdminStates.add_groups)
    await cb.answer()
    await cb.message.edit_text(_("admin.add_groups_prompt"), reply_markup=kb.cancel_kb(_))


@router.message(AdminStates.add_groups, *TEXT)
async def on_group_names(
    message: Message, state: FSMContext, session: AsyncSession, access: Access, _: Translator, settings: Settings
) -> None:
    parsed = parse_group_names(message.text)
    if parsed.invalid:
        await message.answer(_("admin.groups_invalid", names=escape(", ".join(parsed.invalid))))
    if not parsed.valid:
        return
    added, existing = await repo.add_groups(session, parsed.valid)
    if added:
        await repo.audit(session, actor(access, message.from_user.id), "group.add", entity="group", summary=", ".join(added))
    await session.commit()
    await state.clear()
    await message.answer(_("admin.groups_added", added=escape(", ".join(added)) or "—", existing=escape(", ".join(existing)) or "—"))
    text, markup = await _groups_view(session, _, settings)
    await message.answer(text, reply_markup=markup)


async def _group_card(session: AsyncSession, _: Translator, group: Group, page: int):
    n = await repo.count_students(session, group.id)
    status = _("admin.group_active") if group.is_active else _("admin.group_hidden")
    return _("admin.group_card", group=escape(group.name), n=n, status=status), kb.admin_group_kb(_, group, page)


@router.callback_query(AdminCb.filter(F.action == "group"))
async def on_group(cb: CallbackQuery, callback_data: AdminCb, session: AsyncSession, _: Translator) -> None:
    group = await session.get(Group, callback_data.id)
    await cb.answer()
    if group is None:
        return
    text, markup = await _group_card(session, _, group, callback_data.page)
    await cb.message.edit_text(text, reply_markup=markup)


@router.callback_query(AdminCb.filter(F.action == "toggle"))
async def on_group_toggle(cb: CallbackQuery, callback_data: AdminCb, session: AsyncSession, access: Access, _: Translator) -> None:
    group = await session.get(Group, callback_data.id)
    await cb.answer()
    if group is None:
        return
    group.is_active = not group.is_active
    await repo.audit(
        session, actor(access, cb.from_user.id), "group.edit", entity="group", entity_id=group.id,
        summary=group.name, details={"is_active": [not group.is_active, group.is_active]},
    )
    await session.commit()
    text, markup = await _group_card(session, _, group, callback_data.page)
    await cb.message.edit_text(text, reply_markup=markup)


@router.callback_query(AdminCb.filter(F.action == "rename"))
async def on_rename(cb: CallbackQuery, callback_data: AdminCb, state: FSMContext, session: AsyncSession, _: Translator) -> None:
    group = await session.get(Group, callback_data.id)
    await cb.answer()
    if group is None:
        return
    await state.set_state(AdminStates.rename_group)
    await state.update_data(group_id=group.id)
    await cb.message.edit_text(_("admin.rename_prompt", group=escape(group.name)), reply_markup=kb.cancel_kb(_))


@router.message(AdminStates.rename_group, *TEXT)
async def on_rename_value(message: Message, state: FSMContext, session: AsyncSession, access: Access, _: Translator) -> None:
    group = await session.get(Group, (await state.get_data()).get("group_id", 0))
    parsed = parse_group_names(message.text)
    if group is None or len(parsed.valid) != 1 or parsed.invalid:
        await message.answer(_("admin.groups_invalid", names=escape(message.text[:40])))
        return
    name = parsed.valid[0]
    other = await repo.get_group_by_name(session, name)
    if other is not None and other.id != group.id:
        await message.answer(_("admin.name_taken"))
        return
    old = group.name
    group.name = name
    await repo.audit(
        session, actor(access, message.from_user.id), "group.edit", entity="group", entity_id=group.id,
        summary=name, details={"name": [old, name]},
    )
    await session.commit()
    await state.clear()
    text, markup = await _group_card(session, _, group, 0)
    await message.answer(text, reply_markup=markup)


@router.callback_query(AdminCb.filter(F.action == "gdel"))
async def on_group_delete(cb: CallbackQuery, callback_data: AdminCb, session: AsyncSession, _: Translator) -> None:
    group = await session.get(Group, callback_data.id)
    await cb.answer()
    if group is None:
        return
    await cb.message.edit_text(
        _("admin.group_delete_confirm", group=escape(group.name)),
        reply_markup=kb.confirm_kb(
            _, yes=AdminCb(action="gdel_ok", id=group.id).pack(), no=AdminCb(action="group", id=group.id, page=callback_data.page).pack()
        ),
    )


@router.callback_query(AdminCb.filter(F.action == "gdel_ok"))
async def on_group_delete_ok(
    cb: CallbackQuery, callback_data: AdminCb, session: AsyncSession, access: Access, _: Translator, settings: Settings
) -> None:
    group = await session.get(Group, callback_data.id)
    if group is None:
        await cb.answer()
        return
    name = group.name
    deleted = await repo.remove_group(session, group)
    await repo.audit(
        session, actor(access, cb.from_user.id), "group.delete" if deleted else "group.hide", entity="group",
        entity_id=callback_data.id, summary=name,
    )
    await session.commit()
    await cb.answer(_("admin.group_deleted") if deleted else _("admin.group_hidden_instead"), show_alert=not deleted)
    text, markup = await _groups_view(session, _, settings)
    await cb.message.edit_text(text, reply_markup=markup)


# ------------------------------------------------------------------ accounts


async def _accounts_view(session: AsyncSession, _: Translator):
    accounts = await repo.list_accounts(session)
    return _("admin.accounts", n=len(accounts)), kb.admin_accounts_kb(_, accounts)


def _account_text(_: Translator, a: Account) -> str:
    telegram = (
        (f"@{escape(a.user.username)}" if a.user and a.user.username else str(a.telegram_id))
        if a.telegram_id
        else _("admin.telegram_none")
    )
    return _(
        "admin.account_card",
        name=escape(a.label),
        username=escape(a.username),
        roles=account_roles(_, a),
        telegram=telegram,
        status=_("admin.account_active") if a.is_active else _("admin.account_disabled"),
    )


@router.callback_query(AdminCb.filter(F.action == "accounts"))
async def on_accounts(cb: CallbackQuery, state: FSMContext, session: AsyncSession, _: Translator) -> None:
    await state.clear()
    text, markup = await _accounts_view(session, _)
    await cb.answer()
    await cb.message.edit_text(text, reply_markup=markup)


@router.callback_query(AdminCb.filter(F.action == "account"))
async def on_account(cb: CallbackQuery, callback_data: AdminCb, session: AsyncSession, _: Translator) -> None:
    account = await repo.get_account(session, callback_data.id)
    await cb.answer()
    if account is not None:
        await cb.message.edit_text(_account_text(_, account), reply_markup=kb.admin_account_kb(_, account))


async def _guard_self_or_last_admin(session: AsyncSession, account: Account, access: Access) -> str | None:
    if account.id == access.account_id:
        return "admin.cannot_self"
    if any(r.role == StaffRole.ADMIN for r in account.roles) and account.is_active and await repo.count_admins(session) <= 1:
        return "admin.last_admin"
    return None


@router.callback_query(AdminCb.filter(F.action == "reset"))
async def on_reset(cb: CallbackQuery, callback_data: AdminCb, session: AsyncSession, access: Access, _: Translator) -> None:
    account = await repo.get_account(session, callback_data.id)
    await cb.answer()
    if account is None:
        return
    password = await repo.reset_password(session, account)
    await repo.audit(session, actor(access, cb.from_user.id), "account.reset_password", entity="account", entity_id=account.id, summary=account.username)
    await session.commit()
    await cb.message.answer(_("admin.password_reset", username=escape(account.username), password=escape(password)))


@router.callback_query(AdminCb.filter(F.action == "active"))
async def on_toggle_active(cb: CallbackQuery, callback_data: AdminCb, session: AsyncSession, access: Access, _: Translator) -> None:
    account = await repo.get_account(session, callback_data.id)
    if account is None:
        await cb.answer()
        return
    if account.is_active and (problem := await _guard_self_or_last_admin(session, account, access)):
        await cb.answer(_(problem), show_alert=True)
        return
    account.is_active = not account.is_active
    if not account.is_active:
        await repo.end_sessions(session, account.id)
    await repo.audit(
        session, actor(access, cb.from_user.id), "account.enable" if account.is_active else "account.disable",
        entity="account", entity_id=account.id, summary=account.username,
    )
    await session.commit()
    await cb.answer()
    await cb.message.edit_text(_account_text(_, account), reply_markup=kb.admin_account_kb(_, account))


@router.callback_query(AdminCb.filter(F.action == "adel"))
async def on_account_delete(cb: CallbackQuery, callback_data: AdminCb, session: AsyncSession, access: Access, _: Translator) -> None:
    account = await repo.get_account(session, callback_data.id)
    if account is None:
        await cb.answer()
        return
    if problem := await _guard_self_or_last_admin(session, account, access):
        await cb.answer(_(problem), show_alert=True)
        return
    await cb.answer()
    await cb.message.edit_text(
        _("admin.account_delete_confirm", name=escape(account.label)),
        reply_markup=kb.confirm_kb(_, yes=AdminCb(action="adel_ok", id=account.id).pack(), no=AdminCb(action="account", id=account.id).pack()),
    )


@router.callback_query(AdminCb.filter(F.action == "adel_ok"))
async def on_account_delete_ok(cb: CallbackQuery, callback_data: AdminCb, session: AsyncSession, access: Access, _: Translator) -> None:
    account = await repo.get_account(session, callback_data.id)
    if account is None or await _guard_self_or_last_admin(session, account, access):
        await cb.answer()
        return
    username = account.username
    await session.delete(account)
    await repo.audit(session, actor(access, cb.from_user.id), "account.delete", entity="account", entity_id=callback_data.id, summary=username)
    await session.commit()
    await cb.answer(_("admin.account_deleted"))
    text, markup = await _accounts_view(session, _)
    await cb.message.edit_text(text, reply_markup=markup)


# --- new account wizard: login -> name -> role -> (group) --------------------


@router.callback_query(AdminCb.filter(F.action == "new"))
async def on_new_account(cb: CallbackQuery, state: FSMContext, _: Translator) -> None:
    await state.set_state(AdminStates.new_username)
    await cb.answer()
    await cb.message.edit_text(_("admin.new_username"), reply_markup=kb.cancel_kb(_))


@router.message(AdminStates.new_username, *TEXT)
async def on_new_username(message: Message, state: FSMContext, session: AsyncSession, _: Translator) -> None:
    username = normalize_username(message.text)
    if username is None:
        await message.answer(_("admin.bad_username"))
        return
    if await repo.get_account_by_username(session, username):
        await message.answer(_("admin.username_taken"))
        return
    await state.update_data(new_username=username)
    await state.set_state(AdminStates.new_name)
    await message.answer(_("admin.new_name"), reply_markup=kb.skip_kb(_, AdminCb(action="skipname").pack()))


@router.message(AdminStates.new_name, *TEXT)
async def on_new_name(message: Message, state: FSMContext, _: Translator) -> None:
    await state.update_data(new_name=" ".join(message.text.split())[:128])
    await state.set_state(None)
    await message.answer(_("admin.new_role"), reply_markup=kb.role_pick_kb(_))


@router.callback_query(AdminCb.filter(F.action == "skipname"))
async def on_new_name_skip(cb: CallbackQuery, state: FSMContext, _: Translator) -> None:
    await state.set_state(None)
    await cb.answer()
    await cb.message.edit_text(_("admin.new_role"), reply_markup=kb.role_pick_kb(_))


@router.callback_query(AdminCb.filter(F.action == "role"))
async def on_new_role(cb: CallbackQuery, callback_data: AdminCb, state: FSMContext, session: AsyncSession, access: Access, _: Translator) -> None:
    data = await state.get_data()
    if not data.get("new_username"):
        await cb.answer()
        return
    role = StaffRole(callback_data.value)
    await cb.answer()
    if role == StaffRole.LEADER:
        await state.update_data(new_role=role.value)
        groups = await repo.list_groups(session)
        await cb.message.edit_text(_("admin.new_group"), reply_markup=kb.admin_group_pick_kb(_, groups))
        return
    await _create(cb, state, session, access, _, role, None)


@router.callback_query(AdminCb.filter(F.action == "agroup_page"))
async def on_new_group_page(cb: CallbackQuery, callback_data: AdminCb, session: AsyncSession, _: Translator) -> None:
    await cb.answer()
    await cb.message.edit_reply_markup(reply_markup=kb.admin_group_pick_kb(_, await repo.list_groups(session), callback_data.page))


@router.callback_query(AdminCb.filter(F.action == "agroup"))
async def on_new_group(cb: CallbackQuery, callback_data: AdminCb, state: FSMContext, session: AsyncSession, access: Access, _: Translator) -> None:
    data = await state.get_data()
    group = await session.get(Group, callback_data.id)
    await cb.answer()
    if group is None or data.get("new_role") != StaffRole.LEADER.value:
        return
    await _create(cb, state, session, access, _, StaffRole.LEADER, group.id)


async def _create(cb: CallbackQuery, state: FSMContext, session: AsyncSession, access: Access, _: Translator, role: StaffRole, group_id: int | None) -> None:
    data = await state.get_data()
    await state.clear()
    username = data["new_username"]
    if await repo.get_account_by_username(session, username):
        await cb.message.edit_text(_("admin.username_taken"))
        return
    account, password = await repo.create_account(
        session, username=username, display_name=data.get("new_name"), roles=[(role, group_id)]
    )
    await repo.audit(
        session, actor(access, cb.from_user.id), "account.create", entity="account", entity_id=account.id,
        summary=f"{username} · {role.value}",
    )
    await session.commit()
    log.info("Account %s created from the bot", username)
    await cb.message.edit_text(_("admin.account_created", username=escape(username), password=escape(password)))


# ------------------------------------------------------------------ settings


@router.callback_query(AdminCb.filter(F.action == "settings"))
async def on_settings(cb: CallbackQuery, session: AsyncSession, _: Translator, settings: Settings) -> None:
    prefs = await load_prefs(session, settings)
    await cb.answer()
    await cb.message.edit_text(
        _("admin.settings"),
        reply_markup=kb.admin_settings_kb(_, registration_open=prefs.registration_open, notify_leaders=prefs.notify_leaders),
    )


@router.callback_query(AdminCb.filter(F.action == "set"))
async def on_setting_toggle(
    cb: CallbackQuery, callback_data: AdminCb, session: AsyncSession, user: User, access: Access, _: Translator, settings: Settings
) -> None:
    if callback_data.value not in {"registration_open", "notify_leaders"}:
        await cb.answer()
        return
    prefs = await load_prefs(session, settings)
    old = getattr(prefs, callback_data.value)
    prefs = prefs.model_copy(update={callback_data.value: not old})
    await save_prefs(session, prefs)
    await repo.audit(session, actor(access, user.id), "settings.edit", details={callback_data.value: [old, not old]})
    await session.commit()
    await cb.answer("✅")
    await cb.message.edit_reply_markup(
        reply_markup=kb.admin_settings_kb(_, registration_open=prefs.registration_open, notify_leaders=prefs.notify_leaders)
    )
