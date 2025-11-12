from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from database import async_session_maker
from database.repositories import (
    UserRepository,
    PoseRepository,
    SceneCategoryRepository,
    ModelCategoryRepository,
)
from services.kie_service import kie_service
from keyboards import get_back_to_generation, get_repeat_button
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "repeat_generation")
async def repeat_last_generation(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()
    last_generation = data.get("last_generation")

    if not last_generation:
        await callback.message.answer(
            "❌ Нет последней генерации для повтора.",
            reply_markup=get_back_to_generation()
        )
        return

    gen_type = last_generation.get("type")
    cost = int(last_generation.get("cost", 0))

    # 1) Tekshir va minus qilish
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        if not await user_repo.check_balance(callback.from_user.id, cost):
            await callback.message.answer(
                "❌ Недостаточно кредитов.\n\nПополните баланс в разделе 'Мой кабинет.'",
                reply_markup=get_back_to_generation()
            )
            return
        await user_repo.update_balance(callback.from_user.id, -cost)
        user = await user_repo.get_user_by_telegram_id(callback.from_user.id)

    await callback.message.edit_text("⏳ Повторная генерация началась...")

    try:
        # ===== NORMALIZE =====
        if gen_type == "normalize":
            mode = last_generation["mode"]
            photo_urls = last_generation["photo_urls"]

            if mode == "own_model":
                result = await kie_service.normalize_own_model(photo_urls[0], photo_urls[1])
            else:
                model_prompt = last_generation["model_prompt"]
                result = await kie_service.normalize_new_model(photo_urls[0], model_prompt)

            if "image" not in result:
                raise ValueError("No image in normalize result")

            await callback.message.answer_photo(
                BufferedInputFile(result["image"], filename="normalized.jpg"),
                caption="✅ Нормализация завершена!"
            )
            await callback.message.answer(
                f"Потрачено: {cost} кредита\nБаланс: {user.balance} кредитов",
                reply_markup=get_repeat_button()
            )
            return

        # ===== PRODUCT CARD (3-darajali Category → Subcategory → Item) =====
        if gen_type == "product_card":
            photo_url = last_generation["photo_url"]
            generation_type = last_generation["generation_type"]
            results = []

            async with async_session_maker() as session:
                scene_repo = SceneCategoryRepository(session)

                if generation_type == "all_scenes":
                    hierarchy = await scene_repo.get_full_hierarchy()
                    for _, cat in hierarchy.items():
                        for _, sub in cat["subcategories"].items():
                            for item in sub["items"]:
                                res = await kie_service.change_scene(photo_url, item["prompt"])
                                res["category_name"] = cat["name"]
                                res["subcategory_name"] = sub["name"]
                                res["item_name"] = item["name"]
                                results.append(res)

                elif generation_type == "category_all_subcats":
                    category_id = int(last_generation["selected_category"])
                    category = await scene_repo.get_category(category_id)
                    subcats = await scene_repo.get_subcategories_by_category(category_id)
                    for sub in subcats:
                        items = await scene_repo.get_items_by_subcategory(sub.id)
                        for item in items:
                            res = await kie_service.change_scene(photo_url, item.prompt)
                            res["category_name"] = category.name
                            res["subcategory_name"] = sub.name
                            res["item_name"] = item.name
                            results.append(res)

                elif generation_type == "subcategory_all_items":
                    subcategory_id = int(last_generation["selected_subcategory"])
                    subcategory = await scene_repo.get_subcategory(subcategory_id)
                    category = await scene_repo.get_category(subcategory.category_id)
                    items = await scene_repo.get_items_by_subcategory(subcategory_id)
                    for item in items:
                        res = await kie_service.change_scene(photo_url, item.prompt)
                        res["category_name"] = category.name
                        res["subcategory_name"] = subcategory.name
                        res["item_name"] = item.name
                        results.append(res)

                elif generation_type == "single_item":
                    item_id = int(last_generation["selected_item"])
                    item = await scene_repo.get_item(item_id)
                    subcategory = await scene_repo.get_subcategory(item.subcategory_id)
                    category = await scene_repo.get_category(subcategory.category_id)
                    res = await kie_service.change_scene(photo_url, item.prompt)
                    res["category_name"] = category.name
                    res["subcategory_name"] = subcategory.name
                    res["item_name"] = item.name
                    results.append(res)

            # Yuborish
            for i, res in enumerate(results, 1):
                if "image" in res:
                    caption = f"{res.get('category_name','N/A')} · {res.get('subcategory_name','N/A')} · {res.get('item_name','N/A')}"
                    await callback.message.answer_photo(
                        BufferedInputFile(res["image"], filename=f"result_{i}.jpg"),
                        caption=caption
                    )

            await callback.message.answer(
                f"✅ Генерация завершена!\n\nПотрачено: {cost} кредитов\nБаланс: {user.balance} кредитов",
                reply_markup=get_repeat_button()
            )
            return

        # ===== PHOTO (3 rejim) =====
        if gen_type == "photo":
            mode = last_generation["mode"]
            photo_url = last_generation["photo_url"]

            if mode == "scene_change":
                # item_id saqlab qo‘yilgan bo‘lishi kerak
                item_id = int(last_generation["item_id"])
                async with async_session_maker() as session:
                    scene_repo = SceneCategoryRepository(session)
                    item = await scene_repo.get_item(item_id)
                res = await kie_service.change_scene(photo_url, item.prompt)
                if "image" not in res:
                    raise ValueError("No image in scene result")
                await callback.message.answer_photo(
                    BufferedInputFile(res["image"], "result.jpg"),
                    caption=f"✅ {item.name}"
                )

            elif mode == "pose_change":
                # prompt_id saqlangan bo‘lishi kerak
                prompt_id = int(last_generation["prompt_id"])
                async with async_session_maker() as session:
                    pose_repo = PoseRepository(session)
                    prompt = await pose_repo.get_prompt(prompt_id)
                res = await kie_service.change_pose(photo_url, prompt.prompt)
                if "image" not in res:
                    raise ValueError("No image in pose result")
                await callback.message.answer_photo(
                    BufferedInputFile(res["image"], "result.jpg"),
                    caption=f"✅ {prompt.name}"
                )

            elif mode == "custom":
                prompt = last_generation["prompt"]
                res = await kie_service.custom_generation(photo_url, prompt)
                if "image" not in res:
                    raise ValueError("No image in custom result")
                await callback.message.answer_photo(
                    BufferedInputFile(res["image"], "custom.jpg")
                )

            await callback.message.answer(
                f"✅ Готово!\n\nПотрачено: {cost} кр.\nБаланс: {user.balance} кр.",
                reply_markup=get_repeat_button()
            )
            return

        # Agar noma’lum type bo‘lsa:
        raise ValueError(f"Unknown generation type: {gen_type}")

    except Exception as e:
        logger.error(f"Repeat generation error: {e}", exc_info=True)
        # Refund
        async with async_session_maker() as session:
            user_repo = UserRepository(session)
            await user_repo.update_balance(callback.from_user.id, cost)
        await callback.message.answer(
            f"❌ Ошибка при генерации: {str(e)}\n\nКредиты возвращены на баланс.",
            reply_markup=get_back_to_generation()
        )
