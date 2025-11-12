from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from keyboards import get_generation_menu, get_main_menu

router = Router(name="common")


@router.callback_query(F.data.in_(["back_to_generations", "back_to_generation"]))
async def back_to_generation_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    
    # Media bilan xabar bo'lsa delete qilib answer
    if callback.message.text is None:
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer(
            "Выберите тип генерации:", 
            reply_markup=get_generation_menu()
        )
    else:
        await callback.message.edit_text(
            "Выберите тип генерации:", 
            reply_markup=get_generation_menu()
        )


# @router.callback_query(F.data == "repeat_generation")
# async def repeat_generation_handler(callback: CallbackQuery, state: FSMContext):
#     """Takroriy generatsiya - generation menyuga qaytarish"""
#     await callback.answer()
#     await state.clear()
    
#     if callback.message.text is None:
#         try:
#             await callback.message.delete()
#         except:
#             pass
#         await callback.message.answer(
#             "Выберите тип генерации:", 
#             reply_markup=get_generation_menu()
#         )
#     else:
#         await callback.message.edit_text(
#             "Выберите тип генерации:", 
#             reply_markup=get_generation_menu()
#         )


# @router.callback_query(F.data == "cancel")
# async def cancel_operation(callback: CallbackQuery, state: FSMContext):
#     """Operatsiyani bekor qilish"""
#     await callback.answer("Операция отменена")
#     await state.clear()
    
#     if callback.message.text is None:
#         try:
#             await callback.message.delete()
#         except:
#             pass
#         await callback.message.answer(
#             "❌ Операция отменена.\n\nВыберите тип генерации:", 
#             reply_markup=get_generation_menu()
#         )
#     else:
#         await callback.message.edit_text(
#             "❌ Операция отменена.\n\nВыберите тип генерации:", 
#             reply_markup=get_generation_menu()
#         )