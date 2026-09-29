TEXTS: dict[str, str] = {
    # ---------------------------------------------------------------- common
    "lang.name": "🇺🇿 Oʻzbekcha",
    "lang.changed": "✅ Til: oʻzbekcha",
    "btn.language": "🌐 Til",
    "btn.help": "ℹ️ Yordam",
    "btn.cancel": "✖️ Bekor qilish",
    "btn.back": "‹ Orqaga",
    "btn.close": "✖️ Yopish",
    "btn.skip": "Oʻtkazib yuborish ›",
    "btn.done": "✅ Tayyor",
    "btn.yes_delete": "🗑 Ha, oʻchirish",
    "btn.no": "Yoʻq",
    "btn.prev": "‹",
    "btn.next": "›",
    "cancelled": "Bekor qilindi.",
    "use_menu": "Iltimos, quyidagi tugmalardan foydalaning 👇",
    "error.generic": "⚠️ Xatolik yuz berdi. Qayta urinib koʻring.",
    "access_denied": "⛔️ Sizda bunga ruxsat yoʻq.",
    "help.student": (
        "ℹ️ <b>Yordam</b>\n\n"
        "Bu bot Toshkent shahridagi Turin politexnika universiteti uchun maʼlumotlaringizni yigʻadi.\n\n"
        "• /start: asosiy menyu\n"
        "• /language: tilni oʻzgartirish\n"
        "• /cancel: joriy amalni toʻxtatish\n\n"
        "Xodimlar uchun: /login"
    ),
    "help.staff": (
        "ℹ️ <b>Xodimlar uchun yordam</b>\n\n"
        "• /students: talabalar roʻyxati\n"
        "• /find <i>matn</i>: ism, telefon, hujjat yoki @username boʻyicha qidirish\n"
        "• /export: talabalaringiz Excel fayli\n"
        "• /logout: bu Telegram’ni akkauntingizdan uzish\n"
        "• /language, /cancel\n\n"
        "Veb-saytda ham xuddi shu imkoniyatlar bor."
    ),
    "help.admin": "\n\n<b>Administrator</b>\n• /admin: guruhlar, akkauntlar, sozlamalar",
    # ---------------------------------------------------------------- welcome
    "welcome.new": (
        "🎓 <b>Toshkent shahridagi Turin politexnika universiteti</b>\n"
        "Talabalar maʼlumotlarini yigʻish\n\n"
        "Bu taxminan <b>3 daqiqa</b> vaqt oladi. Tayyorlab qoʻying:\n"
        "🪪 pasport yoki ID karta\n"
        "🖼 3×4 rasm\n"
        "📄 rezyume (PDF yoki Word)\n\n"
        "🔒 Maʼlumotlaringiz <b>universitetning oʻz serverida</b> oʻqiladi, hech qanday tashqi "
        "yoki sunʼiy intellekt xizmatlariga yuborilmaydi. Ularni faqat guruh sardoringiz va "
        "tyutorlar koʻradi (Oʻzbekiston Respublikasining “Shaxsga doir maʼlumotlar toʻgʻrisida”gi Qonuni).\n\n"
        "Rozilik bildirish va boshlash uchun quyidagi tugmani bosing."
    ),
    "btn.consent": "✅ Roziman, boshlash",
    "welcome.back": "👋 Qaytganingiz bilan, <b>{name}</b>!",
    "welcome.staff": "👋 Assalomu alaykum, <b>{name}</b>!\n{roles}",
    "role.admin": "🛡 Administrator",
    "role.tutor": "🎓 Tyutor: barcha guruhlar",
    "role.leader": "👥 Guruh sardori: {groups}",
    # ---------------------------------------------------------------- student menu
    "btn.register": "📝 Maʼlumotlarni toʻldirish",
    "btn.profile": "👤 Profilim",
    "btn.update": "✏️ Maʼlumotlarni yangilash",
    "profile": (
        "👤 <b>{name}</b>\n"
        "{group} · {age} yosh\n\n"
        "🎂 {birth_date}\n"
        "⚧ {gender}\n"
        "📱 {phone}\n"
        "🪪 {document}\n\n"
        "{docs}\n\n"
        "<i>Yangilangan: {updated}</i>"
    ),
    # ---------------------------------------------------------------- steps
    "step.document": "🪪 Hujjat",
    "step.check": "🔎 Maʼlumotlarni tekshiring",
    "step.phone": "📱 Telefon raqami",
    "step.group": "🎓 Guruh",
    "step.photo": "🖼 3×4 rasm",
    "step.cv": "📄 Rezyume",
    "reg.document": (
        "Hujjatingiz rasmini yuboring:\n\n"
        "• <b>pasport</b>: rasmingiz bor asosiy sahifa\n"
        "• <b>ID karta</b>: avval <b>orqa</b> tomoni\n\n"
        "Pastdagi <code>&lt;&lt;&lt;</code> belgili ikki qator aniq va toʻliq koʻrinishi kerak."
    ),
    "reg.document_tip": "💡 Yorugʻ joyda, yaltirashsiz, telefonni hujjat ustida toʻgʻri ushlab suratga oling.",
    "reg.reading": "⏳ Hujjat oʻqilmoqda…",
    "reg.id_front": "Endi ID kartangizning <b>old</b> tomonini yuboring: rasmingiz bor tomon.",
    "reg.patronymic": (
        "<b>Otangizning ismini</b> hujjatdagidek yozing.\n"
        "<i>Masalan: Karimovich, Karimovna, Karim oʻgʻli</i>"
    ),
    "reg.check": (
        "<b>Familiya:</b> {last_name}\n"
        "<b>Ism:</b> {first_name}\n"
        "<b>Otasining ismi:</b> {middle_name}\n"
        "<b>Tugʻilgan sana:</b> {birth_date}\n"
        "<b>Jins:</b> {gender}\n"
        "<b>Hujjat:</b> {doc_type} {doc_number}\n"
        "<b>Amal qilish muddati:</b> {doc_expiry}\n"
        "<b>JShShIR:</b> {pinfl}\n\n"
        "Hammasi toʻgʻrimi?"
    ),
    "reg.check_tip": "Ismlar rasmdan oʻqiladi, yorugʻlik aksi xatoga olib kelishi mumkin. Notoʻgʻri boʻlsa, tuzatish uchun ustiga bosing.",
    "reg.type_field": "✏️ <b>{field}</b>\nHujjatda qanday yozilgan boʻlsa, xuddi shunday yozing.\n\nHozir: <code>{current}</code>",
    "reg.pick_gender": "Jinsingizni tanlang:",
    "btn.correct": "✅ Ha, toʻgʻri",
    "btn.retake": "📷 Yangi rasm",
    "reg.phone": "Pastdagi <b>📱 Raqamimni yuborish</b> tugmasini bosing yoki raqamni yozing.\n<i>Masalan: +998 90 123 45 67</i>",
    "btn.share_phone": "📱 Raqamimni yuborish",
    "reg.group": "Guruhingizni tanlang yoki nomini yozing.",
    "reg.photo": (
        "<b>3×4 rasm</b> yuboring: hujjatlardagi kabi, oddiy och fonda yuzingiz aniq koʻringan portret."
    ),
    "reg.photo_tip": "💡 Bosma 3×4 rasmning skani yoki aniq surati ham boʻladi.",
    "reg.cv": "<b>Rezyume</b>ni PDF yoki Word fayl koʻrinishida yuboring.\n<i>Sahifalar rasmi ham boʻladi ({max} tagacha); oxirgisidan soʻng «Tayyor»ni bosing.</i>",
    "reg.page_added": "📄 {n}-sahifa qabul qilindi. Keyingisini yuboring yoki «Tayyor»ni bosing.",
    "reg.max_pages": "Maksimal {max} sahifa. «Tayyor»ni bosing.",
    "reg.checking": "⏳ Tekshirilmoqda…",
    "reg.review": (
        "📋 <b>Tekshiring</b>\n\n"
        "<b>{name}</b>\n"
        "🎂 {birth_date} · {gender}\n"
        "🪪 {document}\n"
        "📱 {phone}\n"
        "🎓 {group}\n\n"
        "{docs}\n\n"
        "⚠️ <b>Hammasini diqqat bilan tekshiring.</b> Yuborganingizdan keyin maʼlumotlaringizni oʻzingiz oʻzgartira olmaysiz.\n\n"
        "Yuborilsinmi?"
    ),
    "btn.submit": "✅ Yuborish",
    "btn.edit": "✏️ Oʻzgartirish",
    "reg.edit_which": "Nimani oʻzgartirmoqchisiz?",
    "field.document": "🪪 Hujjat",
    "field.phone": "📱 Telefon",
    "field.group": "🎓 Guruh",
    "field.photo": "🖼 Rasm",
    "field.cv": "📄 Rezyume",
    "doc.ok": "✅",
    "doc.missing": "—",
    "docs.line": "🪪 Hujjat {passport}   🖼 Rasm {photo}   📄 Rezyume {cv}",
    "reg.done": (
        "🎉 <b>Tayyor! Maʼlumotlaringiz yuborildi.</b>\n\n"
        "Biror narsa notoʻgʻri boʻlsa, tyutor yoki guruh sardoriga murojaat qiling: ular tuzatib beradi."
    ),
    "reg.locked": "🔒 Maʼlumotlaringiz allaqachon yuborilgan va ularni botda oʻzgartirib boʻlmaydi.\nBiror narsa notoʻgʻri boʻlsa, tyutor yoki guruh sardoriga murojaat qiling: ular tuzatib beradi.",
    "reg.closed": "⏸ Hozircha maʼlumotlar qabul qilinmayapti. Keyinroq urinib koʻring.",
    # ---------------------------------------------------------------- validation
    "doc_err.not_image": "❌ Bu rasm emas. Iltimos, hujjatning <b>rasmini</b> yuboring.",
    "doc_err.too_small": "❌ Rasm juda kichik. Hujjat butun kadrni egallashi uchun yaqinroqdan suratga oling.",
    "doc_err.blurry": "❌ Rasm <b>xira</b>. Telefonni qimirlatmay ushlang, fokuslang va qayta urinib koʻring.",
    "doc_err.not_found": (
        "❌ Hujjatning mashina oʻqiydigan qatorlarini (<code>&lt;&lt;&lt;</code> belgili) topa olmadim.\n"
        "Pasportning asosiy sahifasini yoki ID kartaning <b>orqa</b> tomonini yuboring."
    ),
    "doc_err.partial": "❌ Hujjatning bir qismi kesilib qolgan. <b>Butun sahifa</b>, jumladan pastki qatorlar ham rasmda boʻlsin.",
    "doc_err.unreadable": "❌ Hujjatni ishonchli oʻqib boʻlmadi (yaltirash yoki soya?). Iltimos, yangi rasm yuboring.",
    "doc_err.expired": "❌ Bu hujjatning <b>amal qilish muddati tugagan</b>. Amaldagi pasport yoki ID karta yuboring.",
    "doc_err.age": "❌ Bu hujjatdagi tugʻilgan sana ruxsat etilgan yoshga mos kelmaydi. Oʻz hujjatingizni yuboring.",
    "doc_err.duplicate": "⛔️ Bu hujjat boshqa Telegram akkauntidan allaqachon roʻyxatdan oʻtgan. Tyutoringizga murojaat qiling.",
    "doc_err.front": "❌ Bu ID kartaning old tomoniga oʻxshamaydi (unda rasmingiz koʻrinmayapti). Qayta urinib koʻring.",
    "photo_err.not_image": "❌ Iltimos, <b>rasm</b> yuboring.",
    "photo_err.too_small": "❌ Rasm juda kichik (kamida 300×400 px).",
    "photo_err.not_portrait": "❌ 3×4 rasm <b>vertikal</b> boʻladi (boʻyi enidan katta). Qirqib, qayta yuboring.",
    "photo_err.blurry": "❌ Rasm xira. Aniqroq rasm yuboring.",
    "photo_err.no_face": "❌ Yuz koʻrinmayapti. Yuzingiz aniq koʻringan portret yuboring.",
    "photo_err.many_faces": "❌ Rasmda bir nechta yuz bor. <b>Faqat oʻzingiz</b> tushgan portret yuboring.",
    "photo_err.face_too_small": "❌ Yuzingiz juda kichik. 3×4 rasmda yuz kadrning katta qismini egallashi kerak.",
    "file_err.type": "❌ Bu fayl turi bu yerda qabul qilinmaydi.",
    "file_err.size": "❌ Fayl juda katta (maksimal 20 MB).",
    "file_err.expected": "❌ Iltimos, fayl yoki rasm yuboring.",
    "err.phone": "❌ Bu telefon raqamiga oʻxshamaydi. Masalan: <code>+998901234567</code>",
    "err.foreign_contact": "❌ Iltimos, tugma orqali <b>oʻz</b> raqamingizni yuboring.",
    "err.name_part": "❌ Faqat harflar (2–64), masalan: <i>Karimov</i>, <i>Karim oʻgʻli</i>.",
    "err.group_not_found": "❌ «{query}» guruhi yoʻq. Roʻyxatdan tanlang.",
    "err.no_groups": "⚠️ Hozircha guruhlar yoʻq. Keyinroq urinib koʻring.",
    "err.no_pages": "Avval kamida bitta sahifa yuboring.",
    "err.use_buttons": "Iltimos, yuqoridagi tugmalardan foydalaning ☝️",
    "gender.male": "Erkak",
    "gender.female": "Ayol",
    "doctype.passport": "Pasport",
    "doctype.id_card": "ID karta",
    # ---------------------------------------------------------------- staff login
    "login.username": "🔐 <b>Xodimlar uchun kirish</b>\n\n<b>Login</b>ingizni kiriting:",
    "login.password": "Endi <b>parol</b>ni kiriting.\n<i>Xabar darhol oʻchiriladi.</i>",
    "login.ok": "✅ <b>{name}</b> sifatida kirdingiz. Bu Telegram akkauntingizga ulandi.",
    "login.failed": "❌ Login yoki parol notoʻgʻri.",
    "login.locked": "⛔️ Urinishlar juda koʻp. 15 daqiqadan soʻng qayta urinib koʻring.",
    "login.logged_out": "👋 Chiqdingiz. Bu Telegram endi xodim akkauntiga ulanmagan.",
    "login.not_logged": "Siz tizimga kirmagansiz.",
    # ---------------------------------------------------------------- staff
    "btn.students": "👥 Talabalar",
    "btn.search": "🔍 Qidirish",
    "btn.export": "📊 Excel",
    "btn.admin": "⚙️ Boshqaruv",
    "staff.groups": "👥 <b>Talabalar</b>\n{groups} ta guruhda {students} nafar",
    "staff.no_groups": "Hozircha guruhlar yoʻq.",
    "staff.group": "👥 <b>{group}</b> · {n} nafar talaba",
    "staff.group_empty": "👥 <b>{group}</b>\n\nHozircha talabalar yoʻq.",
    "staff.card": (
        "🎓 <b>{name}</b>\n"
        "{group} · {age} yosh · {gender}\n\n"
        "🎂 {birth_date}\n"
        "📱 {phone}\n"
        "✈️ {telegram}\n"
        "🪪 {document}\n"
        "🔢 JShShIR {pinfl}\n\n"
        "{docs}\n"
        "<i>Roʻyxatdan oʻtgan: {created} · yangilangan: {updated}</i>"
    ),
    "btn.passport": "🪪 Hujjat",
    "btn.photo": "🖼 Rasm",
    "btn.cv": "📄 Rezyume",
    "btn.edit_student": "✏️ Tahrirlash",
    "btn.delete": "🗑 Oʻchirish",
    "staff.edit_which": "✏️ <b>{name}</b>: nimani oʻzgartirasiz?",
    "sfield.last_name": "Familiya",
    "sfield.first_name": "Ism",
    "sfield.middle_name": "Otasining ismi",
    "sfield.birth_date": "Tugʻilgan sana",
    "sfield.gender": "Jins",
    "sfield.phone": "Telefon",
    "sfield.group": "Guruh",
    "staff.edit_prompt": "<b>{field}</b> uchun yangi qiymatni yuboring.\nHozir: <code>{current}</code>",
    "staff.edit_date_prompt": "Yangi tugʻilgan sanani <b>KK.OO.YYYY</b> koʻrinishida yuboring.\nHozir: <code>{current}</code>",
    "staff.edit_gender": "Jinsni tanlang:",
    "staff.edit_group": "Yangi guruhni tanlang:",
    "staff.saved": "✅ Saqlandi.",
    "staff.invalid_value": "❌ Notoʻgʻri qiymat. Qayta urinib koʻring yoki «Bekor qilish»ni bosing.",
    "staff.delete_confirm": "<b>{name}</b> ({group}) va uning barcha hujjatlari oʻchirilsinmi? Buni qaytarib boʻlmaydi.",
    "staff.deleted": "🗑 <b>{name}</b> oʻchirildi.",
    "staff.not_found": "Talaba topilmadi.",
    "staff.search_prompt": "🔍 Ism, telefon, hujjat raqami, JShShIR yoki @username yuboring:",
    "staff.search_results": "🔍 «{query}»: {n} ta topildi",
    "staff.search_empty": "«{query}» boʻyicha hech narsa topilmadi.",
    "staff.search_short": "Kamida 2 ta belgi kiriting.",
    "staff.export_caption": "📊 {n} nafar talaba · {date}",
    "notify.new_student": "🆕 <b>{group}</b> guruhida yangi talaba: {name}",
    # ---------------------------------------------------------------- admin
    "admin.panel": (
        "⚙️ <b>Boshqaruv</b>\n\n"
        "🎓 Talabalar: <b>{students}</b>\n"
        "🏷 Guruhlar: <b>{groups}</b>\n"
        "👤 Xodim akkauntlari: <b>{accounts}</b>\n"
        "📝 Roʻyxatdan oʻtish: <b>{registration}</b>"
    ),
    "admin.open": "ochiq",
    "admin.closed": "yopiq",
    "btn.admin_groups": "🏷 Guruhlar",
    "btn.admin_accounts": "👤 Akkauntlar",
    "btn.admin_settings": "🔧 Sozlamalar",
    "admin.groups": "🏷 <b>Guruhlar</b> ({n})\nBoshqarish uchun guruhni tanlang.",
    "btn.add_groups": "➕ Guruh qoʻshish",
    "btn.edupage_import": "📥 EduPage’dan import",
    "admin.edupage_loading": "⏳ EduPage jadvalidan guruhlar oʻqilmoqda…",
    "admin.edupage_done": "✅ <b>EduPage:</b> {total} ta guruh.\n➕ Qoʻshildi: {added}\n✔️ Oldin bor edi: {existing}",
    "admin.edupage_missing": "⚠️ Bu yerda bor, lekin hozir EduPage’da yoʻq (qoldirildi; bitirgan boʻlsa, yashiring): {names}",
    "admin.edupage_failed": "❌ EduPage’ni oʻqib boʻlmadi. Keyinroq urinib koʻring.",
    "admin.add_groups_prompt": "Guruh nomlarini yuboring: har birini yangi qatorda yoki vergul bilan.\n<i>Masalan:</i> <code>SE-24-01, SE-24-02</code>",
    "admin.groups_added": "✅ Qoʻshildi: {added}\nAvvaldan mavjud: {existing}",
    "admin.groups_invalid": "❌ Notoʻgʻri nomlar: {names}",
    "admin.group_card": "🏷 <b>{group}</b>\n{n} nafar talaba · {status}",
    "admin.group_active": "botda koʻrinadi",
    "admin.group_hidden": "botda yashirilgan",
    "btn.rename": "✏️ Nomini oʻzgartirish",
    "btn.hide": "🙈 Yashirish",
    "btn.show": "👁 Koʻrsatish",
    "admin.rename_prompt": "<b>{group}</b> uchun yangi nom yuboring:",
    "admin.name_taken": "❌ Bu nom band.",
    "admin.group_delete_confirm": "<b>{group}</b> oʻchirilsinmi? Talabalari bor guruh oʻchirilmaydi, yashiriladi.",
    "admin.group_deleted": "🗑 Guruh oʻchirildi.",
    "admin.group_hidden_instead": "🙈 Guruhda talabalar bor, shuning uchun u yashirildi.",
    "admin.accounts": "👤 <b>Xodim akkauntlari</b> ({n})",
    "btn.new_account": "➕ Yangi akkaunt",
    "admin.account_card": (
        "👤 <b>{name}</b>\n"
        "Login: <code>{username}</code>\n"
        "Rollar: {roles}\n"
        "Telegram: {telegram}\n"
        "Holat: {status}"
    ),
    "admin.account_active": "faol",
    "admin.account_disabled": "oʻchirilgan",
    "admin.telegram_none": "ulanmagan",
    "btn.reset_password": "🔑 Yangi parol",
    "btn.disable": "⏸ Oʻchirish",
    "btn.enable": "▶️ Yoqish",
    "admin.new_username": "➕ <b>Yangi akkaunt</b>\n\n<b>Login</b> yuboring (3–32 belgi: a–z, 0–9, nuqta, chiziqcha, pastki chiziq):",
    "admin.bad_username": "❌ Login notoʻgʻri. a–z, 0–9, «.», «-», «_» ishlating (3–32 belgi).",
    "admin.username_taken": "❌ Bu login band.",
    "admin.new_name": "Shaxsning <b>F.I.Sh.</b>ini yuboring (boshqalarga koʻrinadi) yoki «Oʻtkazib yuborish»ni bosing.",
    "admin.new_role": "<b>Rol</b>ni tanlang:",
    "admin.new_group": "Bu shaxs sardor boʻladigan guruhni tanlang:",
    "admin.account_created": (
        "✅ Akkaunt yaratildi.\n\n"
        "Login: <code>{username}</code>\n"
        "Vaqtinchalik parol: <code>{password}</code>\n\n"
        "Ularni shaxsan bering. U veb-saytga kiradi (va yangi parol tanlaydi), "
        "bu botga esa /login yuboradi."
    ),
    "admin.password_reset": "🔑 <code>{username}</code> uchun yangi vaqtinchalik parol:\n<code>{password}</code>\n\nKeyingi safar veb-saytga kirganda uni oʻzgartirishi kerak.",
    "admin.account_delete_confirm": "<b>{name}</b> akkaunti oʻchirilsinmi?",
    "admin.account_deleted": "🗑 Akkaunt oʻchirildi.",
    "admin.cannot_self": "Buni oʻz akkauntingizga qila olmaysiz.",
    "admin.last_admin": "Bu oxirgi administrator akkaunti.",
    "admin.settings": "🔧 <b>Sozlamalar</b>\nAlmashtirish uchun bosing.",
    "btn.toggle_registration": "{mark} Roʻyxatdan oʻtishni qabul qilish",
    "btn.toggle_notify": "{mark} Guruh sardorlarini xabardor qilish",
    # ---------------------------------------------------------------- commands
    "cmd.start": "Asosiy menyu",
    "cmd.language": "Tilni oʻzgartirish",
    "cmd.help": "Yordam",
    "cmd.cancel": "Joriy amalni bekor qilish",
    "cmd.login": "Xodimlar uchun kirish",
    "cmd.students": "Talabalar roʻyxati",
    "cmd.find": "Talabalarni qidirish",
    "cmd.export": "Excelga eksport",
    "cmd.logout": "Chiqish",
    "cmd.admin": "Boshqaruv paneli",
    "cmd.backup": "Hozir zaxira nusxa",
    "backup.started": "⏳ Zaxira nusxa tayyorlanmoqda…",
    "backup.caption": "🗄 <b>Zaxira nusxa</b> · {name}\n👥 Talabalar: {students} · 🎓 Guruhlar: {groups} · {size}",
    "backup.encrypted": "🔐 Shifrlangan. 7-Zip, WinRAR yoki Keka orqali zaxira paroli bilan oching (serverdagi BACKUP_PASSWORD).",
    "backup.not_encrypted": "⚠️ Shifrlanmagan: serverda BACKUP_PASSWORD ni oʻrnating. Faylni hech kimga yubormang: unda shaxsiy maʼlumotlar bor.",
    "backup.too_big": "Fayl Telegram chegarasidan (50 MB) katta, shuning uchun faqat serverda saqlanadi.",
    "backup.failed": "❌ Zaxira nusxa yaratilmadi. Server loglarini tekshiring.",
}
