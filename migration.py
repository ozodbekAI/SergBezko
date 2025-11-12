"""
Скрипт для заполнения базы данных: ModelType, SceneGroup/ScenePlanPrompt, PoseGroup/PoseSubgroup/PosePrompt
Запустите после миграций:
    python populate_all_data.py
"""
import asyncio
import logging
from datetime import datetime

from database import async_session_maker
from database.repositories import (
    ModelTypeRepository,
    SceneRepository,
    PoseRepository,
)

# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ==============================  Model Types  ============================== #
async def populate_model_types() -> None:
    async with async_session_maker() as session:
        repo = ModelTypeRepository(session)

        logger.info("Добавление типов моделей...")

        data = [
            ("Брюнетка", "A brunette woman model with dark hair, natural beauty, professional fashion photography", 1),
            ("Блондинка", "A blonde woman model with light hair, elegant appearance, high-fashion editorial style", 2),
            ("Шатенка", "A redhead woman model with auburn hair, striking features, artistic fashion photography", 3),
            ("Рыжая", "A ginger woman model with bright red hair, unique appearance, creative fashion shoot", 4),
            ("Седая", "A silver-haired woman model with gray hair, sophisticated mature beauty, luxury fashion", 5),
        ]

        for name, prompt, order in data:
            try:
                obj = await repo.add(name=name, prompt=prompt, order_index=order)
                logger.info(f"Тип модели: {name} (ID: {obj.id})")
            except Exception as exc:
                logger.warning(f"Тип модели «{name}» уже есть / ошибка: {exc}")

        logger.info("Все типы моделей добавлены!")


# ==============================  Scenes  ============================== #
async def populate_scenes() -> None:
    async with async_session_maker() as session:
        repo = SceneRepository(session)

        # ----------  Группы сцен  ----------
        logger.info("Создание групп сцен...")
        groups = [
            ("Бутик / Showroom", 1),
            ("Классическая гостиная / Интерьер", 2),
            ("Улица / Переход через улицу", 3),
            ("Индустриальный лофт", 4),
            ("Hotel Lobby / Luxury Hall", 5),
            ("Rooftop / City View Terrace", 6),
            ("Art Gallery / Minimal Space", 7),
            ("Boutique / Studio", 8),
            ("Loft / Natural Light Space", 9),
            ("Art Gallery / Neutral Wall", 10),
        ]

        group_id_map: dict[str, int] = {}
        for name, order in groups:
            try:
                grp = await repo.add_group(name=name, order_index=order)
                group_id_map[name] = grp.id
                logger.info(f"Группа: {name} (ID: {grp.id})")
            except Exception as exc:
                logger.warning(f"Группа «{name}» уже существует: {exc}")
                # получаем существующую
                all_g = await repo.get_all_groups()
                for g in all_g:
                    if g.name == name:
                        group_id_map[name] = g.id
                        break

        # ----------  Планы (универсальные)  ----------
        logger.info("Создание планов...")
        plans = [
            ("Дальний план", 1),
            ("Средний план", 2),
            ("Крупный план", 3),
            ("Боковой вид", 4),
            ("Вид со спины", 5),
            ("Динамический кадр", 6),
        ]

        plan_id_map: dict[str, int] = {}
        for name, order in plans:
            try:
                pl = await repo.add_plan(name=name, order_index=order)
                plan_id_map[name] = pl.id
                logger.info(f"План: {name} (ID: {pl.id})")
            except Exception as exc:
                logger.warning(f"План «{name}» уже существует: {exc}")
                all_p = await repo.get_all_plans()
                for p in all_p:
                    if p.name == name:
                        plan_id_map[name] = p.id
                        break

        # ----------  Промпты для каждой группы  ----------
        logger.info("Заполнение промптов сцен...")

        # 1. Бутик / Showroom
        boutique = {
            "Дальний план": [
                ("Мягкое освещение", "full-body fashion photo, model standing confidently inside a luxury boutique, surrounded by clothing racks and soft spotlights, elegant mirror reflections, polished marble floor, cinematic composition, editorial style, natural posing, high-end fashion campaign look"),
            ],
            "Средний план": [
                ("Витрина на фоне", "half-body shot, focus on outfit details and silhouette, boutique background softly blurred, warm lighting on model's face, subtle reflections in glass, refined editorial mood, balanced framing"),
            ],
            "Крупный план": [
                ("Детали ткани", "close-up of neckline and fabric texture, gold jewelry sparkle, blurred boutique shelves behind, shallow depth of field, glossy magazine aesthetic, ultra-detailed fabric texture"),
            ],
            "Боковой вид": [
                ("Боковой портрет", "side-angle fashion portrait in boutique interior, soft warm lighting, mirror reflections emphasizing silhouette and drape of fabric, refined editorial mood, confident posture, natural realism"),
            ],
            "Вид со спины": [
                ("Вид сзади в коридоре", "back view full-body shot, model walking away through boutique corridor, focus on back detailing of outfit, soft golden reflections on polished surfaces, cinematic composition, elegant editorial tone"),
            ],
            "Динамический кадр": [
                ("Поворот в движении", "dynamic shot of model turning or walking through boutique, fabric moving naturally, light reflecting on surfaces, cinematic motion blur, elegant confident energy"),
            ],
        }

        await _add_prompts_for_group(
            repo,
            group_name="Бутик / Showroom",
            group_id_map=group_id_map,
            plan_id_map=plan_id_map,
            prompts_dict=boutique,
        )

        # 2. Классическая гостиная / Интерьер
        interior = {
            "Дальний план": [
                ("Неоклассический интерьер", "model posing in a spacious neoclassical living room with high ceilings, soft daylight through tall windows, neutral tones and elegant furniture, editorial look, clean perspective"),
            ],
            "Средний план": [
                ("У дивана", "mid-shot near a vintage sofa or column, focus on outfit's silhouette, natural light highlighting the waistline, gentle shadows adding depth, refined minimal style"),
            ],
            "Крупный план": [
                ("Детали одежды", "close-up on buttons, cuffs or neckline, soft warm reflection from nearby lamp, creamy background blur, tactile fabric texture captured sharply"),
            ],
            "Боковой вид": [
                ("Профиль у мебели", "profile view of model standing beside classical furniture, soft window light outlining silhouette, elegant and balanced composition, refined editorial calm"),
            ],
            "Вид со спины": [
                ("У окна сзади", "full-body back view near window, daylight illuminating hair and garment folds, focus on back seam and natural drape, sophisticated calm mood"),
            ],
            "Динамический кадр": [
                ("Прогулка по комнате", "model gracefully walking across living room, dress or jacket moving softly, daylight trailing through windows, calm cinematic movement, timeless editorial atmosphere"),
            ],
        }

        await _add_prompts_for_group(
            repo,
            group_name="Классическая гостиная / Интерьер",
            group_id_map=group_id_map,
            plan_id_map=plan_id_map,
            prompts_dict=interior,
        )

        # 3. Улица / Переход через улицу
        street = {
            "Дальний план": [
                ("Переход через улицу", "full-body outdoor fashion photo, model crossing city street in motion, modern architecture and cars blurred behind, strong natural sunlight, dynamic yet elegant pose"),
            ],
            "Средний план": [
                ("На пешеходном переходе", "half-body shot at pedestrian crossing, breeze moving fabric slightly, confident expression, light bokeh from cars and buildings, stylish urban mood"),
            ],
            "Крупный план": [
                ("Городские отражения", "close-up of collar, lapel, or accessories, city reflections in sunglasses or jewelry, cinematic contrast lighting, crisp texture of suiting fabric"),
            ],
            "Боковой вид": [
                ("Профиль на переходе", "side view of model mid-step on crosswalk, wind lifting fabric slightly, urban reflections, natural sunlight accentuating profile, cinematic sense of motion"),
            ],
            "Вид со спины": [
                ("Уходит по переходу", "back view walking away along crosswalk, city blur behind, coat tails in motion, golden hour lighting, confident modern energy"),
            ],
            "Динамический кадр": [
                ("Поворот на переходе", "fashion motion shot — model turning on crosswalk or adjusting jacket mid-step, strong sunlight and moving reflections, cinematic energy, natural flow of fabric"),
            ],
        }

        await _add_prompts_for_group(
            repo,
            group_name="Улица / Переход через улицу",
            group_id_map=group_id_map,
            plan_id_map=plan_id_map,
            prompts_dict=street,
        )

        logger.info("Все промпты сцен добавлены!")


async def _add_prompts_for_group(
    repo: SceneRepository,
    group_name: str,
    group_id_map: dict[str, int],
    plan_id_map: dict[str, int],
    prompts_dict: dict[str, list[tuple[str, str]]],
) -> None:
    """Вспомогательная функция – добавление всех промптов одной группы."""
    if group_name not in group_id_map:
        logger.warning(f"Группа «{group_name}» не найдена – пропускаем.")
        return

    group_id = group_id_map[group_name]

    for plan_name, items in prompts_dict.items():
        if plan_name not in plan_id_map:
            continue
        plan_id = plan_id_map[plan_name]

        for idx, (name, prompt) in enumerate(items, start=1):
            try:
                await repo.add_prompt(
                    group_id=group_id,
                    plan_id=plan_id,
                    name=name,
                    prompt=prompt,
                    order_index=idx,
                )
                logger.info(f"  Промпт «{name}» → {group_name}/{plan_name}")
            except Exception as exc:
                logger.warning(f"  Промпт «{name}» уже есть / ошибка: {exc}")


# ==============================  Poses  ============================== #
async def populate_poses() -> None:
    async with async_session_maker() as session:
        repo = PoseRepository(session)

        # ----------  Группы поз  ----------
        logger.info("Создание групп поз...")
        pose_groups = [
            ("Стоя", 1),
            ("Сидя", 2),
            ("В движении", 3),
            ("Переходные", 4),
            ("Пластичные", 5),
            ("Портретные", 6),
        ]

        group_id_map: dict[str, int] = {}
        for name, order in pose_groups:
            try:
                grp = await repo.add_group(name=name, order_index=order)
                group_id_map[name] = grp.id
                logger.info(f"Группа поз: {name} (ID: {grp.id})")
            except Exception as exc:
                logger.warning(f"Группа поз «{name}» уже существует: {exc}")
                all_g = await repo.get_all_groups()
                for g in all_g:
                    if g.name == name:
                        group_id_map[name] = g.id
                        break

        # ----------  Подгруппы + промпты  ----------
        await _populate_standing(repo, group_id_map)
        await _populate_sitting(repo, group_id_map)
        await _populate_dynamic(repo, group_id_map)

        logger.info("Все позы добавлены!")


# -------------------  Стоячие подгруппы  ------------------- #
async def _populate_standing(repo: PoseRepository, group_id_map: dict[str, int]) -> None:
    group_name = "Стоя"
    if group_name not in group_id_map:
        return
    group_id = group_id_map[group_name]

    subgroups = [
        ("Возле стены", 1),
        ("Улица", 2),
        ("Лицом", 3),
        ("Боком", 4),
        ("Casual", 5),
    ]

    sub_id_map: dict[str, int] = {}
    for sub_name, order in subgroups:
        try:
            sub = await repo.add_subgroup(group_id=group_id, name=sub_name, order_index=order)
            sub_id_map[sub_name] = sub.id
            logger.info(f"  Подгруппа «{sub_name}» (ID: {sub.id})")
        except Exception as exc:
            logger.warning(f"  Подгруппа «{sub_name}» уже есть: {exc}")
            all_sub = await repo.get_subgroups_by_group(group_id)
            for s in all_sub:
                if s.name == sub_name:
                    sub_id_map[sub_name] = s.id
                    break

    # ----- Возле стены -----
    wall_prompts = [
        ("Руки в карманах", "standing near wall, hands in pockets, casual pose, confident posture, fashion photography, natural lighting"),
        ("Опирается на стену", "leaning against wall, relaxed pose, one leg bent, shoulder touching wall, casual confidence, editorial style"),
        ("Скрещенные руки", "standing near wall, arms crossed, assertive pose, confident expression, fashion editorial, clean background"),
        ("Одна нога согнута", "standing near wall, one leg bent at knee, relaxed casual stance, fashion photography"),
        ("Рука на стене", "standing with one hand touching wall, casual elegant pose, natural light, editorial style"),
    ]
    await _add_pose_prompts(repo, sub_id_map.get("Возле стены"), wall_prompts)

    # ----- Улица -----
    street_prompts = [
        ("Идет по улице", "walking confidently on street, natural stride, arms swinging naturally, urban fashion photography"),
        ("Остановилась на тротуаре", "standing on sidewalk, one hip slightly out, hand on hip, street fashion pose, urban background"),
        ("Переходит дорогу", "crossing street confidently, mid-stride, natural movement, city background blur, fashion editorial"),
        ("У светофора", "standing at traffic light, casual waiting pose, hand in pocket, urban fashion style"),
    ]
    await _add_pose_prompts(repo, sub_id_map.get("Улица"), street_prompts)

    # ----- Лицом -----
    face_prompts = [
        ("Прямо в камеру", "standing straight facing camera, confident eye contact, balanced posture, professional fashion photography"),
        ("Руки на бедрах", "standing facing camera, hands on hips, power pose, confident stance, editorial style"),
        ("Одна нога впереди", "standing facing camera, one foot forward, elegant pose, natural posture, fashion editorial"),
    ]
    await _add_pose_prompts(repo, sub_id_map.get("Лицом"), face_prompts)


# -------------------  Сидячие подгруппы  ------------------- #
async def _populate_sitting(repo: PoseRepository, group_id_map: dict[str, int]) -> None:
    group_name = "Сидя"
    if group_name not in group_id_map:
        return
    group_id = group_id_map[group_name]

    subgroups = [
        ("На стуле", 1),
        ("На полу", 2),
        ("На скамье", 3),
    ]

    sub_id_map: dict[str, int] = {}
    for sub_name, order in subgroups:
        try:
            sub = await repo.add_subgroup(group_id=group_id, name=sub_name, order_index=order)
            sub_id_map[sub_name] = sub.id
            logger.info(f"  Подгруппа «{sub_name}» (ID: {sub.id})")
        except Exception as exc:
            logger.warning(f"  Подгруппа «{sub_name}» уже есть: {exc}")
            all_sub = await repo.get_subgroups_by_group(group_id)
            for s in all_sub:
                if s.name == sub_name:
                    sub_id_map[sub_name] = s.id
                    break

    # ----- На стуле -----
    chair_prompts = [
        ("Сидит прямо", "sitting on chair, back straight, hands on knees, confident posture, professional fashion photography"),
        ("Ноги скрещены", "sitting on chair, legs crossed elegantly, relaxed posture, editorial fashion style"),
        ("Боком на стуле", "sitting sideways on chair, looking over shoulder, graceful pose, artistic photography"),
        ("Облокотилась", "sitting on chair, leaning on armrest, relaxed elegant pose, natural lighting"),
        ("Ноги вытянуты", "sitting on chair, legs extended forward, casual comfortable pose, fashion editorial"),
    ]
    await _add_pose_prompts(repo, sub_id_map.get("На стуле"), chair_prompts)

    # ----- На полу -----
    floor_prompts = [
        ("Сидит по-турецки", "sitting cross-legged on floor, relaxed casual pose, natural light, bohemian style"),
        ("Ноги согнуты", "sitting on floor with knees bent, arms wrapped around legs, casual intimate pose"),
        ("Опирается на руку", "sitting on floor, leaning on one hand, relaxed elegant pose, editorial style"),
    ]
    await _add_pose_prompts(repo, sub_id_map.get("На полу"), floor_prompts)


# -------------------  Динамические подгруппы  ------------------- #
async def _populate_dynamic(repo: PoseRepository, group_id_map: dict[str, int]) -> None:
    group_name = "В движении"
    if group_name not in group_id_map:
        return
    group_id = group_id_map[group_name]

    subgroups = [
        ("Идёт", 1),
        ("Прыгает", 2),
        ("Поворачивается", 3),
        ("Бежит", 4),
    ]

    sub_id_map: dict[str, int] = {}
    for sub_name, order in subgroups:
        try:
            sub = await repo.add_subgroup(group_id=group_id, name=sub_name, order_index=order)
            sub_id_map[sub_name] = sub.id
            logger.info(f"  Подгруппа «{sub_name}» (ID: {sub.id})")
        except Exception as exc:
            logger.warning(f"  Подгруппа «{sub_name}» уже есть: {exc}")
            all_sub = await repo.get_subgroups_by_group(group_id)
            for s in all_sub:
                if s.name == sub_name:
                    sub_id_map[sub_name] = s.id
                    break

    # ----- Идёт -----
    walk_prompts = [
        ("Уверенная походка", "walking confidently, strong stride, arms moving naturally, dynamic fashion photography, motion captured"),
        ("Легкая прогулка", "casual walk, relaxed movement, natural flow, fashion editorial in motion, soft movement"),
        ("Широкий шаг", "walking with wide confident stride, powerful movement, fashion editorial, dynamic energy"),
        ("Медленная походка", "slow graceful walk, elegant movement, flowing fabric, artistic fashion photography"),
    ]
    await _add_pose_prompts(repo, sub_id_map.get("Идёт"), walk_prompts)

    # ----- Поворачивается -----
    turn_prompts = [
        ("Поворот головы", "turning head while walking, hair in motion, graceful movement, fashion photography, dynamic moment"),
        ("Оглядывается", "looking back over shoulder while moving, elegant turn, flowing fabric, editorial style"),
        ("Поворот всего тела", "full body turn while in motion, dramatic movement, fabric swirling, cinematic fashion"),
        ("Быстрый поворот", "quick turn with hair flying, dynamic energy, motion blur, fashion editorial"),
    ]
    await _add_pose_prompts(repo, sub_id_map.get("Поворачивается"), turn_prompts)


async def _add_pose_prompts(
    repo: PoseRepository,
    subgroup_id: int | None,
    prompts: list[tuple[str, str]],
) -> None:
    if subgroup_id is None:
        return
    for idx, (name, prompt) in enumerate(prompts, start=1):
        try:
            await repo.add_prompt(
                subgroup_id=subgroup_id,
                name=name,
                prompt=prompt,
                order_index=idx,
            )
            logger.info(f"    Промпт позы «{name}»")
        except Exception as exc:
            logger.warning(f"    Промпт позы «{name}» уже есть / ошибка: {exc}")


# ==============================  MAIN  ============================== #
async def main() -> None:
    logger.info("НАЧАЛО ЗАПОЛНЕНИЯ БД".center(80, "="))

    await populate_model_types()
    await populate_scenes()
    await populate_poses()

    logger.info("БАЗА ДАННЫХ УСПЕШНО ЗАПОЛНЕНА!".center(80, "="))
    logger.info(
        "\n".join(
            [
                "• 5 типов моделей",
                "• 10 групп сцен + 6 планов в каждой",
                "• 6 групп поз → подгруппы → промпты",
                "Готово к запуску бота!",
            ]
        )
    )


if __name__ == "__main__":
    asyncio.run(main())