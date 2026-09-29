TEXTS: dict[str, str] = {
    # ---------------------------------------------------------------- common
    "lang.name": "🇬🇧 English",
    "lang.changed": "✅ Language: English",
    "btn.language": "🌐 Language",
    "btn.help": "ℹ️ Help",
    "btn.cancel": "✖️ Cancel",
    "btn.back": "‹ Back",
    "btn.close": "✖️ Close",
    "btn.skip": "Skip ›",
    "btn.done": "✅ Done",
    "btn.yes_delete": "🗑 Yes, delete",
    "btn.no": "No",
    "btn.prev": "‹",
    "btn.next": "›",
    "btn.programs": "‹ Programs",
    "cancelled": "Cancelled.",
    "use_menu": "Please use the buttons below 👇",
    "error.generic": "⚠️ Something went wrong. Please try again.",
    "access_denied": "⛔️ You don't have access to this.",
    "help.student": (
        "ℹ️ <b>Help</b>\n\n"
        "This bot collects your data for Turin Polytechnic University in Tashkent.\n\n"
        "• /start: main menu\n"
        "• /language: change language\n"
        "• /cancel: stop the current action\n\n"
        "Staff members: /login"
    ),
    "help.staff": (
        "ℹ️ <b>Staff help</b>\n\n"
        "• /students: browse students\n"
        "• /find <i>text</i>: search by name, phone, document or @username\n"
        "• /export: Excel file of your students\n"
        "• /logout: disconnect this Telegram from your account\n"
        "• /language, /cancel\n\n"
        "The website offers the same tools on a big screen."
    ),
    "help.admin": "\n\n<b>Admin</b>\n• /admin: groups, accounts, settings",
    # ---------------------------------------------------------------- welcome
    "welcome.new": (
        "🎓 <b>Turin Polytechnic University in Tashkent</b>\n"
        "Student data collection\n\n"
        "It takes about <b>3 minutes</b>. Have these ready:\n"
        "🪪 passport or ID card\n"
        "🖼 a 3×4 photo\n"
        "📄 your CV (PDF or Word)\n\n"
        "🔒 Your data is read <b>on the university's own server</b>. It is never sent to "
        "third-party or AI services, and only your group leader and tutors can see it "
        "(Law of the Republic of Uzbekistan “On Personal Data”).\n\n"
        "Press the button below to agree and start."
    ),
    "btn.consent": "✅ Agree and start",
    "welcome.back": "👋 Welcome back, <b>{name}</b>!",
    "welcome.staff": "👋 Hello, <b>{name}</b>!\n{roles}",
    "role.admin": "🛡 Administrator",
    "role.tutor": "🎓 Tutor: all groups",
    "role.leader": "👥 Group leader: {groups}",
    # ---------------------------------------------------------------- student menu
    "btn.register": "📝 Fill in my data",
    "btn.profile": "👤 My profile",
    "btn.update": "✏️ Update my data",
    "profile": (
        "👤 <b>{name}</b>\n"
        "{group} · {age} y.o.\n\n"
        "🎂 {birth_date}\n"
        "⚧ {gender}\n"
        "📱 {phone}\n"
        "🪪 {document}\n\n"
        "{docs}\n\n"
        "<i>Updated {updated}</i>"
    ),
    # ---------------------------------------------------------------- steps
    "step.document": "🪪 Document",
    "step.check": "🔎 Check your data",
    "step.phone": "📱 Phone number",
    "step.group": "🎓 Group",
    "step.photo": "🖼 3×4 photo",
    "step.cv": "📄 CV",
    "reg.document": (
        "Send a photo of your document:\n\n"
        "• <b>passport</b>: the main page with your photo\n"
        "• <b>ID card</b>: the <b>back</b> side first\n\n"
        "The two lines with <code>&lt;&lt;&lt;</code> at the bottom must be sharp and fully visible."
    ),
    "reg.document_tip": "💡 Good light, no glare, hold the phone straight above the document.",
    "reg.reading": "⏳ Reading your document…",
    "reg.id_front": (
        "Now send the <b>front</b> side of your ID card: the side with your photo."
    ),
    "reg.patronymic": (
        "Type your <b>patronymic</b> exactly as in your document.\n"
        "<i>e.g. Karimovich, Karimovna, Karim oʻgʻli</i>"
    ),
    "reg.check": (
        "<b>Surname:</b> {last_name}\n"
        "<b>Name:</b> {first_name}\n"
        "<b>Patronymic:</b> {middle_name}\n"
        "<b>Date of birth:</b> {birth_date}\n"
        "<b>Gender:</b> {gender}\n"
        "<b>Document:</b> {doc_type} {doc_number}\n"
        "<b>Valid until:</b> {doc_expiry}\n"
        "<b>PINFL:</b> {pinfl}\n\n"
        "Is everything correct?"
    ),
    "reg.check_tip": "Names are read from the photo, and glare can cause mistakes. If something is wrong, tap it to fix.",
    "reg.type_field": "✏️ <b>{field}</b>\nType it exactly as written in your document.\n\nNow: <code>{current}</code>",
    "reg.pick_gender": "Choose your gender:",
    "btn.correct": "✅ Yes, correct",
    "btn.retake": "📷 New photo",
    "reg.phone": "Tap <b>📱 Share my number</b> below, or type it.\n<i>e.g. +998 90 123 45 67</i>",
    "btn.share_phone": "📱 Share my number",
    "reg.group": "Choose your program, then your group.\nOr just type the group name, e.g. <code>IT1-25</code>.",
    "reg.photo": (
        "Send a <b>3×4 photo</b>: a portrait of your face on a plain light background, "
        "like the one in your documents."
    ),
    "reg.photo_tip": "💡 A scan or a clear photo of your printed 3×4 photo is fine.",
    "reg.cv": "Send your <b>CV</b> as a PDF or Word file.\n<i>Photos of pages also work (up to {max}); press «Done» after the last one.</i>",
    "reg.page_added": "📄 Page {n} received. Send the next one or press «Done».",
    "reg.max_pages": "That's the maximum of {max} pages. Press «Done».",
    "reg.checking": "⏳ Checking…",
    "reg.review": (
        "📋 <b>Review</b>\n\n"
        "<b>{name}</b>\n"
        "🎂 {birth_date} · {gender}\n"
        "🪪 {document}\n"
        "📱 {phone}\n"
        "🎓 {group}\n\n"
        "{docs}\n\n"
        "⚠️ <b>Check everything carefully.</b> After you send it, you won't be able to change your data yourself.\n\n"
        "Send it?"
    ),
    "btn.submit": "✅ Submit",
    "btn.edit": "✏️ Change something",
    "reg.edit_which": "What would you like to change?",
    "field.document": "🪪 Document",
    "field.phone": "📱 Phone",
    "field.group": "🎓 Group",
    "field.photo": "🖼 Photo",
    "field.cv": "📄 CV",
    "doc.ok": "✅",
    "doc.missing": "—",
    "docs.line": "🪪 Document {passport}   🖼 Photo {photo}   📄 CV {cv}",
    "reg.done": (
        "🎉 <b>Done! Your data has been submitted.</b>\n\n"
        "If something is wrong, contact your tutor or group leader: they can correct it."
    ),
    "reg.locked": "🔒 Your data has already been submitted and can't be changed in the bot.\nIf something is wrong, contact your tutor or group leader: they can correct it.",
    "reg.closed": "⏸ Data collection is closed right now. Please try again later.",
    # ---------------------------------------------------------------- validation
    "doc_err.not_image": "❌ That isn't a photo. Please send a <b>photo</b> of the document.",
    "doc_err.too_small": "❌ The picture is too small. Take the photo closer, so the document fills the frame.",
    "doc_err.blurry": "❌ The photo is <b>blurry</b>. Hold the phone steady, tap to focus, and try again.",
    "doc_err.not_found": (
        "❌ I can't find the document's machine-readable lines (with <code>&lt;&lt;&lt;</code>).\n"
        "Send the passport main page, or the <b>back</b> side of the ID card."
    ),
    "doc_err.partial": "❌ Part of the document is cut off. Make sure the <b>whole page</b>, including the bottom lines, is in the photo.",
    "doc_err.unreadable": "❌ I couldn't read the document reliably (glare or shadow?). Please take a new photo.",
    "doc_err.expired": "❌ This document has <b>expired</b>. Please send a valid passport or ID card.",
    "doc_err.age": "❌ The date of birth in this document doesn't fit the allowed age. Please send your own document.",
    "doc_err.duplicate": "⛔️ This document is already registered from another Telegram account. Please contact your tutor.",
    "doc_err.front": "❌ This doesn't look like the front side of the ID card (I can't see your photo on it). Please try again.",
    "photo_err.not_image": "❌ Please send a <b>photo</b>.",
    "photo_err.too_small": "❌ The photo is too small (at least 300×400 px).",
    "photo_err.not_portrait": "❌ A 3×4 photo is <b>vertical</b> (taller than wide). Please crop it and send again.",
    "photo_err.blurry": "❌ The photo is blurry. Please send a sharper one.",
    "photo_err.no_face": "❌ I can't see a face. Send a portrait with your face clearly visible.",
    "photo_err.many_faces": "❌ There is more than one face. Send a portrait of <b>only you</b>.",
    "photo_err.face_too_small": "❌ Your face is too small. The face should fill most of the 3×4 photo.",
    "file_err.type": "❌ This file type isn't accepted here.",
    "file_err.size": "❌ The file is too big (max 20 MB).",
    "file_err.expected": "❌ Please send a file or a photo.",
    "err.phone": "❌ That doesn't look like a phone number. e.g. <code>+998901234567</code>",
    "err.foreign_contact": "❌ Please share <b>your own</b> number with the button.",
    "err.name_part": "❌ Use letters only (2–64), e.g. <i>Karimov</i>, <i>Karim oʻgʻli</i>.",
    "err.group_not_found": "❌ No group «{query}». Choose from the list.",
    "err.no_groups": "⚠️ There are no groups yet. Please try again later.",
    "err.no_pages": "Send at least one page first.",
    "err.use_buttons": "Please use the buttons above ☝️",
    "gender.male": "Male",
    "gender.female": "Female",
    "doctype.passport": "Passport",
    "doctype.id_card": "ID card",
    # ---------------------------------------------------------------- staff login
    "login.username": "🔐 <b>Staff sign-in</b>\n\nEnter your <b>username</b>:",
    "login.password": "Now enter your <b>password</b>.\n<i>The message will be deleted right away.</i>",
    "login.ok": "✅ Signed in as <b>{name}</b>. This Telegram is now connected to your account.",
    "login.failed": "❌ Wrong username or password.",
    "login.locked": "⛔️ Too many attempts. Try again in 15 minutes.",
    "login.logged_out": "👋 Signed out. This Telegram is no longer connected to a staff account.",
    "login.not_logged": "You are not signed in.",
    # ---------------------------------------------------------------- staff
    "btn.students": "👥 Students",
    "btn.search": "🔍 Search",
    "btn.export": "📊 Excel",
    "btn.admin": "⚙️ Admin",
    "staff.groups": "👥 <b>Students</b>\n{students} in {groups} groups",
    "staff.no_groups": "No groups yet.",
    "staff.group": "👥 <b>{group}</b> · {n} students",
    "staff.group_empty": "👥 <b>{group}</b>\n\nNo students yet.",
    "staff.card": (
        "🎓 <b>{name}</b>\n"
        "{group} · {age} y.o. · {gender}\n\n"
        "🎂 {birth_date}\n"
        "📱 {phone}\n"
        "✈️ {telegram}\n"
        "🪪 {document}\n"
        "🔢 PINFL {pinfl}\n\n"
        "{docs}\n"
        "<i>Registered {created} · updated {updated}</i>"
    ),
    "btn.passport": "🪪 Document",
    "btn.photo": "🖼 Photo",
    "btn.cv": "📄 CV",
    "btn.edit_student": "✏️ Edit",
    "btn.delete": "🗑 Delete",
    "staff.edit_which": "✏️ What to change for <b>{name}</b>?",
    "sfield.last_name": "Surname",
    "sfield.first_name": "Name",
    "sfield.middle_name": "Patronymic",
    "sfield.birth_date": "Date of birth",
    "sfield.gender": "Gender",
    "sfield.phone": "Phone",
    "sfield.group": "Group",
    "staff.edit_prompt": "Send the new value for <b>{field}</b>.\nNow: <code>{current}</code>",
    "staff.edit_date_prompt": "Send the new date of birth as <b>DD.MM.YYYY</b>.\nNow: <code>{current}</code>",
    "staff.edit_gender": "Choose the gender:",
    "staff.edit_group": "Choose the new group:",
    "staff.saved": "✅ Saved.",
    "staff.invalid_value": "❌ Invalid value. Try again or press «Cancel».",
    "staff.delete_confirm": "Delete <b>{name}</b> ({group}) and all their documents? This can't be undone.",
    "staff.deleted": "🗑 <b>{name}</b> deleted.",
    "staff.not_found": "Student not found.",
    "staff.search_prompt": "🔍 Send a name, phone, document number, PINFL or @username:",
    "staff.search_results": "🔍 «{query}»: {n} found",
    "staff.search_empty": "Nothing found for «{query}».",
    "staff.search_short": "Enter at least 2 characters.",
    "staff.export_caption": "📊 {n} students · {date}",
    "notify.new_student": "🆕 New student in <b>{group}</b>: {name}",
    # ---------------------------------------------------------------- admin
    "admin.panel": (
        "⚙️ <b>Admin</b>\n\n"
        "🎓 Students: <b>{students}</b>\n"
        "🏷 Groups: <b>{groups}</b>\n"
        "👤 Staff accounts: <b>{accounts}</b>\n"
        "📝 Registration: <b>{registration}</b>"
    ),
    "admin.open": "open",
    "admin.closed": "closed",
    "btn.admin_groups": "🏷 Groups",
    "btn.admin_accounts": "👤 Accounts",
    "btn.admin_settings": "🔧 Settings",
    "admin.groups": "🏷 <b>Groups</b> ({n})\nTap a group to manage it.",
    "btn.add_groups": "➕ Add groups",
    "btn.edupage_import": "📥 Import from EduPage",
    "admin.edupage_loading": "⏳ Reading groups from the EduPage timetable…",
    "admin.edupage_done": "✅ <b>EduPage:</b> {total} groups.\n➕ Added: {added}\n✔️ Already here: {existing}",
    "admin.edupage_missing": "⚠️ Here but not on EduPage now (kept; hide them if they graduated): {names}",
    "admin.edupage_failed": "❌ Couldn't read EduPage. Try again later.",
    "admin.add_groups_prompt": "Send group names, one per line or comma-separated.\n<i>e.g.</i> <code>SE-24-01, SE-24-02</code>",
    "admin.groups_added": "✅ Added: {added}\nAlready existed: {existing}",
    "admin.groups_invalid": "❌ Invalid names: {names}",
    "admin.group_card": "🏷 <b>{group}</b>\n{n} students · {status}",
    "admin.group_active": "visible in the bot",
    "admin.group_hidden": "hidden from the bot",
    "btn.rename": "✏️ Rename",
    "btn.hide": "🙈 Hide",
    "btn.show": "👁 Show",
    "admin.rename_prompt": "Send the new name for <b>{group}</b>:",
    "admin.name_taken": "❌ That name is taken.",
    "admin.group_delete_confirm": "Delete <b>{group}</b>? A group with students is hidden instead.",
    "admin.group_deleted": "🗑 Group deleted.",
    "admin.group_hidden_instead": "🙈 The group has students, so it was hidden instead.",
    "admin.accounts": "👤 <b>Staff accounts</b> ({n})",
    "btn.new_account": "➕ New account",
    "admin.account_card": (
        "👤 <b>{name}</b>\n"
        "Login: <code>{username}</code>\n"
        "Roles: {roles}\n"
        "Telegram: {telegram}\n"
        "Status: {status}"
    ),
    "admin.account_active": "active",
    "admin.account_disabled": "disabled",
    "admin.telegram_none": "not connected",
    "btn.reset_password": "🔑 New password",
    "btn.disable": "⏸ Disable",
    "btn.enable": "▶️ Enable",
    "admin.new_username": "➕ <b>New account</b>\n\nSend a <b>login</b> (3–32 characters: a–z, 0–9, dot, dash, underscore):",
    "admin.bad_username": "❌ Invalid login. Use a–z, 0–9, «.», «-», «_» (3–32 characters).",
    "admin.username_taken": "❌ This login is taken.",
    "admin.new_name": "Send the person's <b>full name</b> (shown to others), or press «Skip».",
    "admin.new_role": "Choose the <b>role</b>:",
    "admin.new_group": "Choose the group this person leads:",
    "admin.account_created": (
        "✅ Account created.\n\n"
        "Login: <code>{username}</code>\n"
        "Temporary password: <code>{password}</code>\n\n"
        "Give these to the person privately. They sign in on the website "
        "(and must choose a new password), and send /login to this bot."
    ),
    "admin.password_reset": "🔑 New temporary password for <code>{username}</code>:\n<code>{password}</code>\n\nThey must change it at the next sign-in on the website.",
    "admin.account_delete_confirm": "Delete account <b>{name}</b>?",
    "admin.account_deleted": "🗑 Account deleted.",
    "admin.cannot_self": "You can't do this to your own account.",
    "admin.last_admin": "This is the last admin account.",
    "admin.settings": "🔧 <b>Settings</b>\nTap to switch.",
    "btn.toggle_registration": "{mark} Accept registrations",
    "btn.toggle_notify": "{mark} Notify group leaders",
    # ---------------------------------------------------------------- commands
    "cmd.start": "Main menu",
    "cmd.language": "Change language",
    "cmd.help": "Help",
    "cmd.cancel": "Cancel current action",
    "cmd.login": "Staff sign-in",
    "cmd.students": "Browse students",
    "cmd.find": "Search students",
    "cmd.export": "Excel export",
    "cmd.logout": "Sign out",
    "cmd.admin": "Admin panel",
    "cmd.backup": "Backup now",
    "backup.started": "⏳ Making a backup…",
    "backup.caption": "🗄 <b>Backup</b> · {name}\n👥 Students: {students} · 🎓 Groups: {groups} · {size}",
    "backup.encrypted": "🔐 Encrypted. Open it with 7-Zip, WinRAR or Keka using the backup password (BACKUP_PASSWORD on the server).",
    "backup.not_encrypted": "⚠️ Not encrypted: set BACKUP_PASSWORD on the server. Keep this file private: it holds personal data.",
    "backup.too_big": "It is bigger than Telegram allows (50 MB), so it is kept only on the server.",
    "backup.failed": "❌ The backup failed. Check the server logs.",
}
