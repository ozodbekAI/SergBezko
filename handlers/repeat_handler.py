from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from database import async_session_maker
from database.repositories import UserRepository, PoseElementRepository, SceneElementRepository
from services.config_loader import config_loader
from services.kie_service import kie_service
from services.translator import translator_service
from keyboards import get_repeat_button, get_back_to_generation
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
            "❌",
            reply_markup=get_back_to_generation()
        )
        return
    
    generation_type = last_generation.get("type")
    
    cost = last_generation.get("cost", 0)
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        has_balance = await user_repo.check_balance(callback.from_user.id, cost)
        if not has_balance:
            await callback.message.answer(
                "❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'",
                reply_markup=get_back_to_generation()
            )
            return
        
        await user_repo.update_balance(callback.from_user.id, -cost)
        user = await user_repo.get_user_by_telegram_id(callback.from_user.id)
    
    await callback.message.edit_text("⏳ Генерация началась...")
    
    try:
        if generation_type == "photo":
            await repeat_photo_generation(callback, last_generation, user)
        elif generation_type == "video":
            await repeat_video_generation(callback, last_generation, user)
        elif generation_type == "normalize":
            await repeat_normalize_generation(callback, last_generation, user)
        elif generation_type == "product_card":
            await repeat_product_card_generation(callback, last_generation, user)
        else:
            raise ValueError(f"Unknown generation type: {generation_type}")
            
    except Exception as e:
        logger.error(f"Repeat generation error: {e}", exc_info=True)
        # Xatolik bo'lsa kreditslarni qaytarish
        async with async_session_maker() as session:
            user_repo = UserRepository(session)
            await user_repo.update_balance(callback.from_user.id, cost)
        
        await callback.message.answer(
            f"❌ Ошибка при генерации: {str(e)}\n\nКредиты возвращены на баланс.",
            reply_markup=get_back_to_generation()
        )


async def repeat_photo_generation(callback: CallbackQuery, data: dict, user):
    photo_url = data["photo_url"]
    mode = data["mode"]
    cost = data["cost"]
    
    results = []
    
    if mode == "scene_change":
        selected_ids = data["selected_element_ids"]
        scene_id = data["selected_scene"]
        plan_id = data.get("selected_plan", "medium")
        
        async with async_session_maker() as session:
            scene_repo = SceneElementRepository(session)
            all_elements = await scene_repo.get_elements_by_scene(scene_id)
        
        for elem in all_elements:
            if elem.id in selected_ids:
                prompt_field = f"prompt_{plan_id}"
                prompt = getattr(elem, prompt_field, elem.prompt_medium)
                result = await kie_service.change_scene(photo_url, prompt)
                result["element_name"] = f"{elem.name} ({plan_id.title()})"
                results.append(result)
    
    elif mode == "pose_change":
        selected_ids = data["selected_element_ids"]
        pose_id = data["selected_pose"]
        
        async with async_session_maker() as session:
            pose_repo = PoseElementRepository(session)
            all_elements = await pose_repo.get_elements_by_pose(pose_id)
        
        for elem in all_elements:
            if elem.id in selected_ids:
                result = await kie_service.change_pose(photo_url, elem.prompt)
                result["element_name"] = elem.name
                results.append(result)
    
    elif mode == "custom":
        prompt = data["prompt"]
        result = await kie_service.custom_generation(photo_url, prompt)
        results.append(result)
    
    for i, result in enumerate(results, 1):
        if "image" in result:
            caption = result.get("element_name") or f"Результат {i}"
            await callback.message.answer_photo(
                BufferedInputFile(result["image"], filename=f"result_{i}.jpg"),
                caption=caption
            )
    
    await callback.message.answer(
        f"✅ Генерация завершена!\n\n"
        f"Потрачено: {cost} кредитов\n"
        f"Баланс: {user.balance} кредитов",
        reply_markup=get_repeat_button()
    )


async def repeat_video_generation(callback: CallbackQuery, data: dict, user):
    photo_url = data["photo_url"]
    prompt = data["prompt"]
    cost = data["cost"]
    model = data["model"]
    duration = int(data["duration"].split()[0].replace("~", ""))
    resolution = data["resolution"]
    
    result = await kie_service.generate_video(photo_url, prompt, model, duration, resolution)
    
    if "video" in result:
        await callback.message.answer_video(
            BufferedInputFile(result["video"], filename="video.mp4"),
            caption="✅ Видео готово!"
        )
        await callback.message.answer(
            f"Потрачено: {cost} кредитов\nБаланс: {user.balance} кредитов",
            reply_markup=get_repeat_button()
        )
    else:
        raise ValueError("No video in result")


async def repeat_normalize_generation(callback: CallbackQuery, data: dict, user):
    mode = data["mode"]
    photo_urls = data["photo_urls"]
    cost = data["cost"]
    
    if mode == "own_model":
        result = await kie_service.normalize_own_model(photo_urls[0], photo_urls[1])
    else:
        model_type = data["model_type"]
        model = config_loader.get_model_type_by_id(model_type)
        result = await kie_service.normalize_new_model(photo_urls[0], model["prompt"])
    
    if "image" in result:
        await callback.message.answer_photo(
            BufferedInputFile(result["image"], filename="normalized.jpg"),
            caption="✅ Нормализация завершена!"
        )
        await callback.message.answer(
            f"Потрачено: {cost} кредита\nБаланс: {user.balance} кредитов",
            reply_markup=get_repeat_button()
        )
    else:
        raise ValueError("No image in result")


async def repeat_product_card_generation(callback: CallbackQuery, data: dict, user):
    cost = data["cost"]
    results = await kie_service.generate_product_cards(data)
    
    for i, result in enumerate(results, 1):
        if "image" in result:
            caption = f"Сцена: {result.get('scene_name', 'N/A')} · План: {result.get('plan', 'N/A')}"
            await callback.message.answer_photo(
                BufferedInputFile(result["image"], filename=f"result_{i}.jpg"),
                caption=caption
            )
    
    await callback.message.answer(
        f"✅ Генерация завершена!\n\n"
        f"Потрачено: {cost} кредитов\n"
        f"Баланс: {user.balance} кредитов",
        reply_markup=get_repeat_button()
    )