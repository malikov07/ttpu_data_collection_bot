"""Turn DB objects into JSON-friendly dicts for the website."""

from __future__ import annotations

from datetime import date

from app.db.models import Account, Certificate, Document, DocumentKind, Group, Student
from app.services.validators import age_on


def document_json(doc: Document | None) -> dict:
    return {
        "present": doc is not None,
        "pages": [
            {"index": i, "mime": f.get("mime"), "name": f.get("name"), "source": f.get("type"), "side": f.get("side")}
            for i, f in enumerate(doc.files)
        ]
        if doc
        else [],
        "updated_at": doc.updated_at.isoformat() if doc else None,
    }


def certificate_json(c: Certificate, *, student: bool = False, can_review: bool | None = None) -> dict:
    data = {
        "id": c.id,
        "type": c.type.value,
        "result": c.result,
        "status": c.status.value,
        "note": c.note,
        "files": [{"index": i, "mime": f.get("mime"), "name": f.get("name"), "source": f.get("type")} for i, f in enumerate(c.files)],
        "reviewed_by": c.reviewed_by,
        "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else None,
        "created_at": c.created_at.isoformat(),
    }
    if student:
        s = c.student
        data["student"] = {"id": s.id, "full_name": s.full_name, "group": {"id": s.group.id, "name": s.group.name}}
    if can_review is not None:
        data["can_review"] = can_review
    return data


def student_json(s: Student, *, today: date | None = None) -> dict:
    user = s.user
    return {
        "id": s.id,
        "full_name": s.full_name,
        "last_name": s.last_name,
        "first_name": s.first_name,
        "middle_name": s.middle_name,
        "birth_date": s.birth_date.isoformat(),
        "age": age_on(s.birth_date, today or date.today()),
        "gender": s.gender.value,
        "phone": s.phone,
        "group": {"id": s.group.id, "name": s.group.name},
        "document": {
            "type": s.doc_type.value if s.doc_type else None,
            "number": s.doc_number,
            "expiry": s.doc_expiry.isoformat() if s.doc_expiry else None,
            "pinfl": s.pinfl,
            "nationality": s.nationality,
        },
        "telegram": {
            "id": s.telegram_id,
            "username": user.username if user else None,
            "first_name": user.first_name if user else None,
        },
        "documents": {kind.value: document_json(s.document(kind)) for kind in DocumentKind},
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


def group_json(g: Group, *, students: int, leaders: list[Account]) -> dict:
    return {
        "id": g.id,
        "name": g.name,
        "is_active": g.is_active,
        "students": students,
        "leaders": [
            {"id": a.id, "label": a.label, "username": a.username, "telegram_connected": a.telegram_id is not None}
            for a in leaders
        ],
        "created_at": g.created_at.isoformat(),
    }


def account_json(a: Account) -> dict:
    user = a.user
    return {
        "id": a.id,
        "username": a.username,
        "display_name": a.display_name,
        "label": a.label,
        "roles": [
            {"role": r.role.value, "group": {"id": r.group.id, "name": r.group.name} if r.group else None}
            for r in a.roles
        ],
        "is_active": a.is_active,
        "must_change_password": a.must_change_password,
        "telegram": {"id": a.telegram_id, "username": user.username if user else None} if a.telegram_id else None,
        "last_login_at": a.last_login_at.isoformat() if a.last_login_at else None,
        "created_at": a.created_at.isoformat(),
    }
