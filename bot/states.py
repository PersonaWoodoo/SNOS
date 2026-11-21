from aiogram.fsm.state import State, StatesGroup

class AdminFlow(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_permissions = State()
    waiting_for_remove_id = State()
