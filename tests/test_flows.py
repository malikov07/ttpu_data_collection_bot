"""End-to-end bot flows through the real dispatcher and database."""

from __future__ import annotations

from datetime import date

import pytest
from aiogram import methods
from sqlalchemy import select

from app.callbacks import AdminCb, EditFieldCb, StaffCb
from app.db import repo
from app.db.models import Account, AuditLog, DocType, DocumentKind, Gender, StaffRole
from app.services.vision import DocumentResult
from tests.conftest import id_card_result, passport_result

pytestmark = pytest.mark.asyncio
ADMIN = 1  # in ADMIN_IDS


async def setup_groups(h, names="SE-24-01, SE-24-02"):
    admin = h.user(ADMIN, "Admin")
    await h.text(admin, "/start")
    await h.click(admin, "lang:en")
    await h.text(admin, "/admin")
    await h.click(admin, AdminCb(action="add_groups").pack())
    await h.text(admin, names)
    return admin


async def start_registration(h, uid, lang="en"):
    u = h.user(uid, "Vali", username=f"vali{uid}")
    await h.text(u, "/start")
    await h.click(u, f"lang:{lang}")
    await h.click(u, "reg:consent")
    return u


async def send_documents(h, u):
    """Permanent address and school certificate; the optional temporary address and form 086 skipped."""
    await h.document(u, "address.pdf", "application/pdf")
    await h.click(u, "reg:skip")
    await h.document(u, "school.pdf", "application/pdf")
    await h.click(u, "reg:skip")


async def register(h, uid=100, group="SE-24-01", lang="en", **passport):
    h.vision.documents[f"pass-{uid}"] = passport_result(**passport)
    u = await start_registration(h, uid, lang)
    await h.photo(u, f"pass-{uid}")
    await h.click(u, "reg:correct")
    await h.contact(u, "998901234567")
    await h.text(u, group)
    await h.photo(u, f"face-{uid}", size=(600, 800))
    await h.document(u, f"cv{uid}.pdf", "application/pdf")
    await send_documents(h, u)
    await h.click(u, "reg:certs_done")  # no certificates
    await h.click(u, "reg:submit")
    return u


async def student(h, uid):
    async with h.sessions() as s:
        return await repo.get_student_by_tg(s, uid)


async def test_passport_registration(h):
    await setup_groups(h)
    h.vision.documents["pass-100"] = passport_result()
    u = await start_registration(h, 100)
    assert "Document" in h.tg.texts(100)[-1] and "1/11" in h.tg.texts(100)[-1]

    await h.photo(u, "pass-100")
    check = h.tg.texts(100)[-1]
    assert "Aliyev" in check and "Vali" in check and "Karimovich" in check and "AB1234567" in check
    assert "32103051234567" in check
    await h.click(u, "reg:correct")
    await h.contact(u, "998901234567")
    await h.text(u, "se-24-01")
    await h.photo(u, "face-100", size=(600, 800))
    await h.document(u, "cv.pdf", "application/pdf")
    assert "Permanent address" in h.tg.texts(100)[-1] and "my.gov.uz" in h.tg.texts(100)[-1]
    assert ("Skip ›", "reg:skip") not in h.buttons()  # required
    await h.document(u, "address.pdf", "application/pdf")
    assert "Temporary address" in h.tg.texts(100)[-1] and ("Skip ›", "reg:skip") in h.buttons()
    await h.photo(u, "temp-1")
    await h.photo(u, "temp-2")
    await h.click(u, "reg:done")
    assert "School certificate" in h.tg.texts(100)[-1]
    await h.photo(u, "school-1")
    await h.click(u, "reg:done")
    assert "form 086" in h.tg.texts(100)[-1]
    await h.document(u, "086.pdf", "application/pdf")
    await h.click(u, "reg:certs_done")  # no certificates
    review = h.tg.last(methods.SendPhoto)  # review card shows the 3x4 photo
    assert review.photo == "face-100" and "Aliyev Vali Karimovich" in review.caption
    await h.click(u, "reg:submit")
    assert any("Done!" in t for t in h.tg.texts(100))

    s = await student(h, 100)
    assert (s.last_name, s.first_name, s.middle_name) == ("Aliyev", "Vali", "Karimovich")
    assert s.full_name == "Aliyev Vali Karimovich"
    assert s.birth_date == date(2005, 3, 21) and s.gender == Gender.MALE
    assert (s.doc_type, s.doc_number, s.doc_expiry) == (DocType.PASSPORT, "AB1234567", date(2031, 5, 20))
    assert s.pinfl == "32103051234567" and s.nationality == "UZB"
    assert s.phone == "+998901234567" and s.group.name == "SE-24-01"
    assert {d.kind for d in s.documents} == set(DocumentKind)
    assert [f["file_id"] for f in s.document(DocumentKind.TEMP_ADDRESS).files] == ["temp-1", "temp-2"]
    assert s.document(DocumentKind.MEDICAL).files[0]["name"] == "086.pdf"
    # Old screens are deleted as the student moves on: the chat stays short.
    assert sum(isinstance(r, methods.DeleteMessage) for r in h.tg.requests) >= 5


async def test_id_card_needs_front_and_patronymic(h):
    await setup_groups(h)
    h.vision.documents["back"] = id_card_result()
    h.vision.fronts["front-bad"] = ("no_face", None)
    h.vision.fronts["front"] = (None, None)
    u = await start_registration(h, 200)
    await h.photo(u, "back")
    assert "front" in h.tg.texts(200)[-1]
    await h.photo(u, "front-bad")
    assert "front side" in h.tg.texts(200)[-1]
    await h.photo(u, "front")
    assert "patronymic" in h.tg.texts(200)[-1]
    await h.text(u, "123")
    assert "letters only" in h.tg.texts(200)[-1]
    await h.text(u, "anvar qizi")
    assert "Anvar qizi" in h.tg.texts(200)[-1]
    await h.click(u, "reg:correct")
    await h.contact(u, "998901234567")
    await h.text(u, "SE-24-02")
    await h.photo(u, "face", size=(600, 800))
    await h.document(u, "cv.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    await send_documents(h, u)
    await h.click(u, "reg:certs_done")  # no certificates
    await h.click(u, "reg:submit")
    s = await student(h, 200)
    assert s.doc_type == DocType.ID_CARD and s.middle_name == "Anvar qizi" and s.gender == Gender.FEMALE
    assert [f["side"] for f in s.document(DocumentKind.PASSPORT).files] == ["back", "front"]


async def test_student_fixes_misread_fields_one_by_one(h):
    """Glare can garble a name: each field has its own button on the check screen."""
    await setup_groups(h)
    h.vision.documents["p"] = passport_result(patronymic="Karimovlch")
    u = await start_registration(h, 150)
    await h.photo(u, "p")
    labels = [text for text, _ in h.buttons()]
    assert {"✏️ Surname", "✏️ Name", "✏️ Patronymic", "✏️ Gender"} <= set(labels)

    await h.click(u, h.button("Patronymic"))
    assert "Now: <code>Karimovlch</code>" in h.tg.texts(150)[-1]
    await h.click(u, h.button("Back"))  # changed their mind: nothing changes
    assert "Karimovlch" in h.tg.texts(150)[-1] and "Is everything correct?" in h.tg.texts(150)[-1]

    await h.click(u, h.button("Patronymic"))
    await h.text(u, "123")
    assert "letters only" in h.tg.texts(150)[-1]
    await h.text(u, "karimovich")
    await h.click(u, h.button("Name"))
    await h.text(u, "Valijon")
    await h.click(u, h.button("Gender"))
    await h.click(u, h.button("Female"))
    check = h.tg.texts(150)[-1]
    assert "Valijon" in check and "Karimovich" in check and "Female" in check
    assert "Is everything correct?" in check

    await h.click(u, "reg:correct")
    await h.contact(u, "998901234567")
    await h.text(u, "SE-24-01")
    await h.photo(u, "face", size=(600, 800))
    await h.document(u, "cv.pdf", "application/pdf")
    await send_documents(h, u)
    await h.click(u, "reg:certs_done")  # no certificates
    # The review has the same per-field buttons.
    await h.click(u, "reg:edit")
    await h.click(u, h.button("Surname"))
    await h.text(u, "Aliyeva")
    assert "Aliyeva Valijon Karimovich" in h.tg.last(methods.SendPhoto).caption
    await h.click(u, "reg:submit")

    s = await student(h, 150)
    assert (s.last_name, s.first_name, s.middle_name, s.gender) == ("Aliyeva", "Valijon", "Karimovich", Gender.FEMALE)
    assert s.doc_number == "AB1234567"  # check-digit protected fields are not editable by the student
    async with h.sessions() as db:
        entry = (await db.scalars(select(AuditLog).where(AuditLog.action == "student.register"))).one()
    # Staff can see what was read from the document and what the student typed instead.
    assert entry.details == {
        "last_name": ["Aliyev", "Aliyeva"],
        "first_name": ["Vali", "Valijon"],
        "middle_name": ["Karimovlch", "Karimovich"],
        "gender": ["male", "female"],
    }


@pytest.mark.parametrize(
    "result, message",
    [
        (DocumentResult("blurry"), "blurry"),
        (DocumentResult("not_found"), "machine-readable"),
        (DocumentResult("partial"), "cut off"),
        (DocumentResult("unreadable"), "reliably"),
        (DocumentResult("expired"), "expired"),
    ],
)
async def test_bad_document_photos_are_rejected(h, result, message):
    await setup_groups(h)
    h.vision.documents["bad"] = result
    u = await start_registration(h, 300)
    await h.photo(u, "bad")
    assert message in h.tg.texts(300)[-1]
    # still waiting for the document; a good photo then works
    h.vision.documents["good"] = passport_result()
    await h.photo(u, "good")
    assert "Is everything correct?" in h.tg.texts(300)[-1]


async def test_age_and_duplicate_document_checks(h):
    await setup_groups(h)
    await register(h, uid=100)
    h.vision.documents["kid"] = passport_result(dob="200101", number="AC1234567", personal="31001201234567")
    h.vision.documents["same"] = passport_result()  # same PINFL + number as student 100
    u = await start_registration(h, 301)
    await h.photo(u, "kid")
    assert "allowed age" in h.tg.texts(301)[-1]
    await h.photo(u, "same")
    assert "already registered" in h.tg.texts(301)[-1]


@pytest.mark.parametrize("error, message", [("no_face", "can't see a face"), ("many_faces", "only you"), ("not_portrait", "vertical")])
async def test_bad_portraits_are_rejected(h, error, message):
    await setup_groups(h)
    h.vision.documents["p"] = passport_result()
    h.vision.portraits["bad"] = error
    u = await start_registration(h, 400)
    await h.photo(u, "p")
    await h.click(u, "reg:correct")
    await h.contact(u, "998901234567")
    await h.text(u, "SE-24-01")
    await h.photo(u, "bad")
    assert message in h.tg.texts(400)[-1]


async def test_submitted_data_is_locked_for_the_student(h):
    await setup_groups(h)
    h.vision.documents["p"] = passport_result()
    u = await start_registration(h, 100)
    await h.photo(u, "p")
    await h.click(u, "reg:correct")
    await h.contact(u, "998901234567")
    await h.text(u, "SE-24-01")
    await h.photo(u, "face", size=(600, 800))
    await h.document(u, "cv.pdf", "application/pdf")
    await send_documents(h, u)
    await h.click(u, "reg:certs_done")  # no certificates
    assert "won't be able to change" in h.tg.last(methods.SendPhoto).caption  # warned before submitting
    await h.click(u, "reg:submit")
    assert any("contact your tutor" in t for t in h.tg.texts(100))

    # The menu has no way to change the data any more.
    menu = h.tg.last(methods.SendMessage).reply_markup
    labels = [b.text for row in menu.keyboard for b in row]
    assert "👤 My profile" in labels and "✏️ Update my data" not in labels and "📝 Fill in my data" not in labels

    # Old buttons and a second review screen can't change it either.
    for attempt in ("✏️ Update my data", "📝 Fill in my data"):
        await h.text(u, attempt)
        assert "can't be changed" in h.tg.texts(100)[-1]
    await h.click(u, "reg:consent")
    assert "can't be changed" in h.tg.texts(100)[-1]
    await h.dp.fsm.storage.set_state(key=_key(h, 100), state="Registration:review")
    await h.dp.fsm.storage.set_data(key=_key(h, 100), data={"doc": {"last_name": "X"}, "group_id": 2, "phone": "+998901111111"})
    await h.click(u, "reg:submit")
    assert "can't be changed" in h.tg.texts(100)[-1]
    s = await student(h, 100)
    assert s.full_name == "Aliyev Vali Karimovich" and s.group.name == "SE-24-01" and s.phone == "+998901234567"


def _key(h, uid):
    from aiogram.fsm.storage.base import StorageKey

    return StorageKey(bot_id=h.bot.id, chat_id=uid, user_id=uid)


async def test_half_filled_form_survives_restart(h):
    from app.db.fsm_storage import DbStorage

    await setup_groups(h)
    h.vision.documents["p"] = passport_result()
    u = await start_registration(h, 600)
    await h.photo(u, "p")
    h.dp.fsm.storage = DbStorage(h.sessions)  # a fresh storage = restarted bot
    await h.click(u, "reg:correct")
    assert "Phone number" in h.tg.texts(600)[-1]


async def test_staff_login_and_lockout(h):
    await setup_groups(h)
    await h.create_account("tutor1", StaffRole.TUTOR)
    t = h.user(700, "Tutor")
    await h.text(t, "/start")
    await h.click(t, "lang:en")
    await h.text(t, "/login")
    await h.text(t, "tutor1")
    password_msg = await h.text(t, "wrong-pass")
    assert "Wrong username or password" in h.tg.texts(700)[-1]
    # the message with the password is deleted from the chat
    assert any(isinstance(r, methods.DeleteMessage) and r.message_id == password_msg for r in h.tg.requests)

    await h.text(t, "/login")
    await h.text(t, "TUTOR1")
    await h.text(t, "Secret123")
    assert any("Signed in as" in x for x in h.tg.texts(700))
    async with h.sessions() as s:
        assert (await repo.get_account_by_username(s, "tutor1")).telegram_id == 700
    await h.text(t, "/students")
    assert "2 groups" in h.tg.texts(700)[-1]

    await h.text(t, "/logout")
    await h.text(t, "/students")
    assert "buttons below" in h.tg.texts(700)[-1]  # no longer staff

    intruder = h.user(701, "X")
    await h.text(intruder, "/start")
    await h.click(intruder, "lang:en")
    for _ in range(5):
        await h.text(intruder, "/login")
        await h.text(intruder, "tutor1")
        await h.text(intruder, "guess")
    await h.text(intruder, "/login")
    assert "Too many attempts" in h.tg.texts(701)[-1]


async def login_bot(h, uid, username):
    u = h.user(uid, username)
    await h.text(u, "/start")
    await h.click(u, "lang:en")
    await h.text(u, "/login")
    await h.text(u, username)
    await h.text(u, "Secret123")
    return u


async def test_leader_sees_own_group_and_edits(h):
    await setup_groups(h)
    await register(h, uid=100, group="SE-24-01")
    await register(h, uid=101, group="SE-24-02", number="AB7654321", personal="32103059999999", surname="KARIMOVA", given="DILNOZA", sex="F")
    await h.create_account("leader1", StaffRole.LEADER, "SE-24-01")
    leader = await login_bot(h, 800, "leader1")

    await h.text(leader, "/students")
    assert "SE-24-01" in h.tg.texts(800)[-1]
    await h.click(leader, h.button("Aliyev"))
    card = h.tg.last(methods.SendPhoto)
    assert "Aliyev Vali Karimovich" in card.caption and "32103051234567" in card.caption

    s1, s2 = await student(h, 100), await student(h, 101)
    await h.click(leader, StaffCb(action="card", student_id=s2.id).pack())
    assert h.tg.last(methods.AnswerCallbackQuery).show_alert  # other group: not visible

    await h.click(leader, StaffCb(action="efield", student_id=s1.id, value="phone").pack())
    await h.text(leader, "91 111 22 33")
    assert (await student(h, 100)).phone == "+998911112233"
    await h.click(leader, StaffCb(action="efield", student_id=s1.id, value="birth_date").pack())
    await h.text(leader, "31.02.2005")
    assert "Invalid value" in h.tg.texts(800)[-1]
    await h.text(leader, "01.01.2004")
    assert (await student(h, 100)).birth_date == date(2004, 1, 1)
    await h.click(leader, StaffCb(action="del", student_id=s1.id).pack())
    assert h.tg.last(methods.AnswerCallbackQuery).show_alert  # only admins delete

    await h.text(leader, "/find karimova")
    assert "Nothing found" in h.tg.texts(800)[-1]
    await h.text(leader, "/export")
    assert h.tg.last(methods.SendDocument).caption.startswith("📊 1 students")


async def test_admin_creates_account_and_toggles_registration(h):
    admin = await setup_groups(h)
    await h.click(admin, AdminCb(action="new").pack())
    await h.text(admin, "Bad Name!")
    assert "Invalid login" in h.tg.texts(ADMIN)[-1]
    await h.text(admin, "leader.two")
    await h.text(admin, "Jasur Rahimov")
    await h.click(admin, AdminCb(action="role", value="leader").pack())
    await h.click(admin, h.button("SE-24-02"))
    created = h.tg.texts(ADMIN)[-1]
    assert "leader.two" in created and "Temporary password" in created
    async with h.sessions() as s:
        account = (await s.scalars(select(Account))).one()
        assert account.must_change_password and account.display_name == "Jasur Rahimov"

    await h.click(admin, AdminCb(action="set", value="registration_open").pack())
    u = h.user(900, "Late")
    await h.text(u, "/start")
    await h.click(u, "lang:en")
    await h.click(u, "reg:consent")
    assert "closed" in h.tg.last(methods.AnswerCallbackQuery).text


async def test_admin_cannot_delete_last_admin(h):
    await setup_groups(h)
    account_id = await h.create_account("boss", StaffRole.ADMIN)
    boss = await login_bot(h, 950, "boss")
    await h.click(boss, AdminCb(action="adel", id=account_id).pack())
    assert "own account" in h.tg.last(methods.AnswerCallbackQuery).text


async def test_foreign_student_registers(h):
    """A Kazakh passport: no PINFL, no patronymic on it, a foreign phone number."""
    await setup_groups(h)
    h.vision.documents["kz"] = passport_result(
        surname="NURLANOVA", given="AIGERIM", number="N12345678", nationality="KAZ", issuing="KAZ",
        personal="", sex="F", patronymic=None,
    )
    h.vision.documents["visa"] = DocumentResult("visa")
    u = await start_registration(h, 160)
    await h.photo(u, "visa")
    assert "visa" in h.tg.texts(160)[-1]
    await h.photo(u, "kz")
    assert "patronymic" in h.tg.texts(160)[-1]
    await h.click(u, h.button("I don't have a patronymic"))
    check = h.tg.texts(160)[-1]
    assert "Nurlanova" in check and "Is everything correct?" in check
    await h.click(u, "reg:correct")
    await h.text(u, "77011234567")
    assert "country code" in h.tg.texts(160)[-1]
    await h.text(u, "+7 701 123 45 67")
    await h.text(u, "SE-24-01")
    await h.photo(u, "face", size=(600, 800))
    await h.document(u, "cv.pdf", "application/pdf")
    await send_documents(h, u)
    await h.click(u, "reg:certs_done")
    await h.click(u, "reg:submit")
    s = await student(h, 160)
    assert (s.last_name, s.first_name, s.middle_name) == ("Nurlanova", "Aigerim", None)
    assert s.nationality == "KAZ" and s.pinfl is None and s.phone == "+77011234567"


async def test_uzbek_documents_still_need_the_patronymic(h):
    await setup_groups(h)
    h.vision.documents["p"] = passport_result(patronymic=None)
    u = await start_registration(h, 170)
    await h.photo(u, "p")
    assert "patronymic" in h.tg.texts(170)[-1]
    assert not any("don't have" in text for text, _ in h.buttons())
    await h.click(u, "reg:no_middle")  # an old or forged button does nothing
    assert "patronymic" in h.tg.texts(170)[-1]


async def test_document_steps(h):
    """Required documents can't be skipped; optional ones can, and the review can drop them again."""
    await setup_groups(h)
    h.vision.documents["p"] = passport_result()
    u = await start_registration(h, 180)
    await h.photo(u, "p")
    await h.click(u, "reg:correct")
    await h.contact(u, "998901234567")
    await h.text(u, "SE-24-01")
    await h.photo(u, "face", size=(600, 800))
    await h.document(u, "cv.pdf", "application/pdf")
    await h.click(u, "reg:skip")  # an old or forged button: the address is required
    assert "Permanent address" in h.tg.texts(180)[-1]
    await h.document(u, "address.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert "PDF or a photo" in h.tg.texts(180)[-1]
    await h.text(u, "hello")
    assert "send a file or a photo" in h.tg.texts(180)[-1]
    await h.click(u, "reg:done")
    assert "at least one page" in h.tg.last(methods.AnswerCallbackQuery).text
    await h.photo(u, "address")
    await h.click(u, "reg:done")
    await h.document(u, "temp.pdf", "application/pdf")
    await h.document(u, "school.pdf", "application/pdf")
    await h.click(u, "reg:skip")
    await h.click(u, "reg:certs_done")
    review = h.tg.last(methods.SendPhoto).caption
    assert "Temporary ✅" in review and "Form 086 —" in review

    # Changed their mind about the temporary address: «Skip» from the review removes it.
    await h.click(u, "reg:edit")
    await h.click(u, h.button("Temporary address"))
    await h.click(u, "reg:skip")
    assert "Temporary —" in h.tg.last(methods.SendPhoto).caption
    await h.click(u, "reg:submit")
    s = await student(h, 180)
    assert {d.kind for d in s.documents} == set(DocumentKind) - {DocumentKind.TEMP_ADDRESS, DocumentKind.MEDICAL}
    assert s.document(DocumentKind.ADDRESS).files[0]["file_id"] == "address"


async def test_registered_student_sends_missing_documents(h):
    """Students who registered before the new documents were added send them from their profile."""
    from app.callbacks import DocCb

    await setup_groups(h)
    u = await register(h, uid=100)
    async with h.sessions() as db:  # registered before: no address, no school certificate
        s = await repo.get_student_by_tg(db, 100)
        for d in [d for d in s.documents if d.kind in (DocumentKind.ADDRESS, DocumentKind.SCHOOL_CERT)]:
            s.documents.remove(d)
        await db.commit()

    await h.text(u, "/start")
    assert "documents are missing" in h.tg.texts(100)[-1]
    await h.text(u, "👤 My profile")
    assert "Tap one below" in h.tg.texts(100)[-1]
    assert [text for text, _ in h.buttons()] == ["🏠 Permanent address", "🏘 Temporary address", "📜 School certificate", "🩺 Form 086"]

    await h.click(u, DocCb(action="add", kind="address").pack())
    assert "my.gov.uz" in h.tg.texts(100)[-1]
    await h.photo(u, "addr-1")
    await h.photo(u, "addr-2")
    await h.click(u, "reg:done")
    assert "Received: <b>🏠 Permanent address</b>" in h.tg.texts(100)[-1]
    assert "🏠 Permanent address" not in [text for text, _ in h.buttons()]
    await h.click(u, DocCb(action="add", kind="address").pack())  # already sent: locked
    assert "already been sent" in h.tg.last(methods.AnswerCallbackQuery).text
    await h.click(u, DocCb(action="add", kind="passport").pack())  # not something they can add
    await h.click(u, DocCb(action="add", kind="school_cert").pack())
    await h.document(u, "school.pdf", "application/pdf")

    s = await student(h, 100)
    assert [f["file_id"] for f in s.document(DocumentKind.ADDRESS).files] == ["addr-1", "addr-2"]
    assert s.document(DocumentKind.SCHOOL_CERT).files[0]["name"] == "school.pdf"
    await h.text(u, "/start")
    assert "missing" not in h.tg.texts(100)[-1]  # only optional ones are left
    async with h.sessions() as db:
        actions = [a.action for a in (await db.scalars(select(AuditLog).where(AuditLog.action == "document.add"))).all()]
    assert len(actions) == 2
