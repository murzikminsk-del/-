from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def topics_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slug, label in [
        ("legal", "⚖️ Юридическая консультация"),
        ("concession", "🤝 Концессии и договоры"),
        ("corporate", "🏢 Корпоративный блок"),
        ("compliance", "📋 Регламенты и политики"),
    ]:
        builder.button(text=label, callback_data=f"topic:{slug}")
    builder.button(text="❌ Отмена", callback_data="topic:cancel")
    builder.adjust(1)
    return builder.as_markup()