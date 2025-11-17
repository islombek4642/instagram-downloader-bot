from typing import Optional

from telegram import KeyboardButton, ReplyKeyboardMarkup


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Asosiy menyu klaviaturasi - tez-tez ishlatiladigan buyruqlar uchun."""
    
    keyboard = [
        [KeyboardButton("/help"), KeyboardButton("/contact")],
        [KeyboardButton("/stats")]
    ]
    
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Ijtimoiy tarmoq linkini yuboring..."
    )
