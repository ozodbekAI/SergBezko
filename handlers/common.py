from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from keyboards import get_generation_menu, get_main_menu

router = Router(name="common")


@router.callback_query(F.data == "back_to_generations")
async def back_to_generation_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "Выберите тип генерации:", 
        reply_markup=get_generation_menu()
    )


# @router.callback_query(F.data == "back_to_main")
# async def back_to_main_handler(callback: CallbackQuery, state: FSMContext):
#     await callback.answer()
#     await state.clear()
#     await callback.message.edit_text(
#         "Главное меню:\n\nВыберите раздел:",
#         reply_markup=get_main_menu()
#     )


# @router.callback_query(F.data == "cancel")
# async def cancel_operation(callback: CallbackQuery, state: FSMContext):
#     await callback.answer("Операция отменена")
#     await state.clear()
#     await callback.message.edit_text(
#         "❌ Операция отменена.\n\nВыберите тип генерации:", 
#         reply_markup=get_generation_menu()
#     )