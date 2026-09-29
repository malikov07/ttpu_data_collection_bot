from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    document = State()  # passport page / ID card back
    id_front = State()  # ID card front
    name_part = State()  # typing a surname / name / patronymic by hand
    check = State()  # confirm the data read from the document
    phone = State()
    group = State()
    photo = State()  # 3x4
    cv = State()
    review = State()


class LoginStates(StatesGroup):
    username = State()
    password = State()


class StaffStates(StatesGroup):
    search = State()
    edit_value = State()


class AdminStates(StatesGroup):
    add_groups = State()
    rename_group = State()
    new_username = State()
    new_name = State()
