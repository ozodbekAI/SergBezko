import asyncio
import logging
from typing import Dict, List, Tuple

from database import async_session_maker
from database.repositories import (
    SceneCategoryRepository,
    PoseRepository,
    VideoScenarioRepository,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)


# ---------------------- SCENE DATA ---------------------- #
def get_scene_data() -> Dict[str, Dict[str, str]]:
    """
    {
      "Категория": {
         "План": "prompt",
         ...
      },
      ...
    }
    """
    return {
        # 1. Бутик
        "Бутик": {
            "Дальний план": (
                "full-body fashion photo, model standing confidently inside a luxury boutique, "
                "surrounded by clothing racks and soft spotlights, elegant mirror reflections, "
                "polished marble floor, cinematic composition, editorial style, natural posing, "
                "high-end fashion campaign look"
            ),
            "Средний план": (
                "half-body shot, focus on outfit details and silhouette, boutique background softly "
                "blurred, warm lighting on model’s face, subtle reflections in glass, refined "
                "editorial mood, balanced framing"
            ),
            "Крупный план": (
                "close-up of neckline and fabric texture, gold jewelry sparkle, blurred boutique "
                "shelves behind, shallow depth of field, glossy magazine aesthetic, ultra-detailed "
                "fabric texture"
            ),
            "Боковой вид": (
                "side-angle fashion portrait in boutique interior, soft warm lighting, mirror "
                "reflections emphasizing silhouette and drape of fabric, refined editorial mood, "
                "confident posture, natural realism"
            ),
            "Вид со спины": (
                "back view full-body shot, model walking away through boutique corridor, focus on "
                "back detailing of outfit, soft golden reflections on polished surfaces, cinematic "
                "composition, elegant editorial tone"
            ),
            "Динамический кадр": (
                "dynamic shot of model turning or walking through boutique, fabric moving naturally, "
                "light reflecting on surfaces, cinematic motion blur, elegant confident energy"
            ),
        },

        # 2. Классическая гостиная
        "Классическая гостиная": {
            "Дальний план": (
                "model posing in a spacious neoclassical living room with high ceilings, soft "
                "daylight through tall windows, neutral tones and elegant furniture, editorial look, "
                "clean perspective"
            ),
            "Средний план": (
                "mid-shot near a vintage sofa or column, focus on outfit’s silhouette, natural light "
                "highlighting the waistline, gentle shadows adding depth, refined minimal style"
            ),
            "Крупный план": (
                "close-up on buttons, cuffs or neckline, soft warm reflection from nearby lamp, "
                "creamy background blur, tactile fabric texture captured sharply"
            ),
            "Боковой вид": (
                "profile view of model standing beside classical furniture, soft window light "
                "outlining silhouette, elegant and balanced composition, refined editorial calm"
            ),
            "Вид со спины": (
                "full-body back view near window, daylight illuminating hair and garment folds, "
                "focus on back seam and natural drape, sophisticated calm mood"
            ),
            "Динамический кадр": (
                "model gracefully walking across living room, dress or jacket moving softly, daylight "
                "trailing through windows, calm cinematic movement, timeless editorial atmosphere"
            ),
        },

        # 3. Улица / Переход через улицу
        "Улица / Переход через улицу": {
            "Дальний план": (
                "full-body outdoor fashion photo, model crossing city street in motion, modern "
                "architecture and cars blurred behind, strong natural sunlight, dynamic yet elegant pose"
            ),
            "Средний план": (
                "half-body shot at pedestrian crossing, breeze moving fabric slightly, confident "
                "expression, light bokeh from cars and buildings, stylish urban mood"
            ),
            "Крупный план": (
                "close-up of collar, lapel, or accessories, city reflections in sunglasses or jewelry, "
                "cinematic contrast lighting, crisp texture of suiting fabric"
            ),
            "Боковой вид": (
                "side view of model mid-step on crosswalk, wind lifting fabric slightly, urban "
                "reflections, natural sunlight accentuating profile, cinematic sense of motion"
            ),
            "Вид со спины": (
                "back view walking away along crosswalk, city blur behind, coat tails in motion, "
                "golden hour lighting, confident modern energy"
            ),
            "Динамический кадр": (
                "fashion motion shot — model turning on crosswalk or adjusting jacket mid-step, "
                "strong sunlight and moving reflections, cinematic energy, natural flow of fabric"
            ),
        },

        # 4. Индустриальный лофт
        "Индустриальный лофт": {
            "Дальний план": (
                "model standing in spacious industrial loft, exposed brick walls and large windows, "
                "fashion editorial setup with soft daylight, minimalist props, artistic composition"
            ),
            "Средний план": (
                "waist-up shot near window or column, warm sunlight highlighting face and outfit "
                "contours, contrast of textures (fabric vs. brick), modern creative feel"
            ),
            "Крупный план": (
                "close-up of details — stitching, buttons, fabric folds — warm golden light, soft "
                "focus on background metal structures, tactile depth and realism"
            ),
            "Боковой вид": (
                "side portrait near large industrial window, natural light defining shoulder line and "
                "profile, textured brick background, artistic modern tone"
            ),
            "Вид со спины": (
                "full-body back view facing window light, silhouette framed by brick and metal, focus "
                "on back tailoring and fabric texture, moody creative atmosphere"
            ),
            "Динамический кадр": (
                "model walking slowly across loft space, fabric shifting in soft daylight, floating "
                "dust particles visible, cinematic creative stillness, natural elegance"
            ),
        },

        # 5. Холл отеля
        "Холл отеля": {
            "Дальний план": (
                "full-body editorial fashion photo, model walking through a luxury hotel lobby with "
                "marble floors and chandeliers, warm golden ambient light, elegant interior "
                "perspective, cinematic composition, reflections on polished surfaces"
            ),
            "Средний план": (
                "half-body portrait near elevator or marble column, warm soft lighting emphasizing "
                "the outfit silhouette, bokeh from chandeliers in background, poised confident pose, "
                "fashion campaign feel"
            ),
            "Крупный план": (
                "close-up of neckline, jewelry, or fabric texture, background of blurred chandeliers, "
                "warm reflections on skin and metal details, glossy high-end magazine aesthetic"
            ),
            "Боковой вид": (
                "side-angle portrait with chandeliers softly glowing in background, golden light "
                "outlining profile and outfit contours, polished marble reflections, refined elegance"
            ),
            "Вид со спины": (
                "back view full-body walking through lobby, chandeliers and columns framing "
                "silhouette, soft reflections on marble floor, luxurious cinematic composition"
            ),
            "Динамический кадр": (
                "fashion motion capture — model walking confidently across lobby, fabric swaying, "
                "chandelier lights creating motion blur, graceful luxury editorial tone"
            ),
        },

        # 6. Видовая веранда на город
        "Видовая веранда на город": {
            "Дальний план": (
                "full-body shot on rooftop terrace overlooking the city skyline, golden-hour light, "
                "wind in fabric and hair, cinematic horizon, sense of sophistication and independence"
            ),
            "Средний план": (
                "waist-up shot with cityscape bokeh behind, sunset tones on skin and fabric, "
                "confident expression, subtle breeze moving the jacket, elevated mood"
            ),
            "Крупный план": (
                "close-up of lapel, earring, or hair movement against blurred skyline, warm sunlight "
                "reflections, crisp detail on texture, modern editorial tone"
            ),
            "Боковой вид": (
                "side-angle fashion portrait with skyline behind, hair moving in breeze, soft sunset "
                "lighting defining silhouette, cinematic golden-hour warmth"
            ),
            "Вид со спины": (
                "back view of model facing city skyline, coat or dress moving slightly with wind, "
                "sunset glow outlining figure, sense of freedom and poise"
            ),
            "Динамический кадр": (
                "model walking along rooftop edge, wind blowing through fabric, sunset motion blur, "
                "cinematic movement, expressive energy of freedom"
            ),
        },

        # 7. Галерея
        "Галерея": {
            "Дальний план": (
                "full-body minimalist shot in modern art gallery, neutral white walls, abstract "
                "paintings, soft even lighting, refined and clean aesthetic"
            ),
            "Средний план": (
                "mid-shot near sculpture or painting, focus on silhouette and clean lines, balanced "
                "symmetry, editorial calm tone"
            ),
            "Крупный план": (
                "close-up on fabric folds or accessory detail, soft museum lighting, gentle background "
                "blur, artistic yet luxurious atmosphere"
            ),
            "Боковой вид": (
                "side-angle portrait near gallery wall or sculpture, minimal light gradients, clear "
                "view of garment’s profile, calm aesthetic harmony"
            ),
            "Вид со спины": (
                "back view of model walking between artworks, balanced symmetry, neutral lighting, "
                "refined minimalist editorial atmosphere"
            ),
            "Динамический кадр": (
                "model turning slowly or walking through gallery hall, soft flowing fabric, subtle "
                "motion blur, timeless editorial calm, artistic rhythm of movement"
            ),
        },

        # 8. Минималистичная студия
        "Минималистичная студия": {
            "Дальний план": (
                "full-body fashion photo of woman standing in a minimal studio boutique interior with "
                "soft daylight and beige walls, neutral background, refined composition, clean modern "
                "elegance, natural posing, commercial editorial tone"
            ),
            "Средний план": (
                "half-body portrait of woman in stylish outfit, soft natural lighting, neutral beige "
                "or light gray background, calm expression, focus on silhouette and proportions, "
                "minimal contemporary aesthetic"
            ),
            "Крупный план": (
                "close-up of fabric texture or neckline area, soft diffused daylight, balanced tones, "
                "clean detail focus, refined editorial minimalism, tactile material rendering"
            ),
            "Боковой вид": (
                "side-angle portrait near studio wall, daylight outlining silhouette, shoulder and "
                "waistline softly contoured, simple background, calm elegance, modern refined look"
            ),
            "Вид со спины": (
                "back view of woman walking or standing in minimal boutique setting, soft light "
                "reflecting on background wall, focus on back detailing and garment drape, serene "
                "editorial composition"
            ),
            "Динамический кадр": (
                "dynamic shot — woman moving naturally through studio space, fabric responding softly "
                "to motion, daylight streaks across wall, cinematic natural flow, modern fashion "
                "campaign energy"
            ),
        },

        # 9. Лофт минимализм
        "Лофт минимализм": {
            "Дальний план": (
                "full-body fashion photo of woman in minimalist loft with large windows, natural "
                "daylight filling the space, muted color palette, balanced composition, effortless "
                "elegance, clean modern editorial style"
            ),
            "Средний план": (
                "waist-up portrait of woman standing near window, daylight falling softly on face and "
                "outfit, focus on silhouette and proportions, calm sophisticated minimalism, timeless "
                "appeal"
            ),
            "Крупный план": (
                "close-up on neckline or sleeve area, focus on fabric folds and texture, soft natural "
                "light, subtle tonal contrast, refined material detail, editorial precision"
            ),
            "Боковой вид": (
                "profile shot near large loft window, sunlight contouring the silhouette, highlighting "
                "shoulder line and garment drape, textured background, artistic and serene fashion tone"
            ),
            "Вид со спины": (
                "back view facing the window, soft daylight outlining figure, focus on garment’s back "
                "detailing and natural movement of fabric, calm elegant atmosphere"
            ),
            "Динамический кадр": (
                "dynamic shot of woman walking across the loft, fabric moving naturally with light "
                "breeze, warm sunlight trails, cinematic sense of space and effortless movement"
            ),
        },

        # 10. Арт Галерея минимализм
        "Арт Галерея минимализм": {
            "Дальний план": (
                "full-body editorial photo of woman posing in modern art gallery with white neutral "
                "walls and natural daylight, minimal elegant composition, refined contemporary atmosphere"
            ),
            "Средний план": (
                "mid-shot portrait near artwork or sculpture, soft side lighting, clean lines "
                "emphasizing silhouette, balanced symmetry, timeless minimalist fashion tone"
            ),
            "Крупный план": (
                "close-up on fabric or accessory detail, soft diffused gallery light, neutral "
                "background, tactile realistic texture, understated luxury aesthetic"
            ),
            "Боковой вид": (
                "side-angle shot near gallery wall, sunlight defining clean profile and garment "
                "structure, minimalist editorial calm, subtle art-space glow"
            ),
            "Вид со спины": (
                "back view of woman walking along white wall, daylight reflections on polished floor, "
                "soft focus on back tailoring and posture, serene balanced composition"
            ),
            "Динамический кадр": (
                "motion shot — woman turning slightly or walking past artwork, soft daylight motion "
                "blur, flowing fabric or accessory movement, refined sense of rhythm and modern grace"
            ),
        },
    }


# ---------------------- POSE DATA ---------------------- #
def get_pose_data() -> Dict[str, List[Tuple[str, str]]]:
    """
    {
      "Группа": [
          ("Название позы", "prompt"),
          ...
      ]
    }
    """
    return {
        "Стоячие позы": [
            ("Стоит прямо", "woman standing straight, facing forward, relaxed natural posture"),
            ("Полуоборот, рука на бедре", "woman standing slightly sideways, one leg bent, hand on hip"),
            ("Лёгкий шаг", "woman standing with crossed legs, gentle confident look"),
            ("Руки в карманах", "woman standing with hands in pockets, shoulders relaxed"),
            ("Касание волос", "woman standing with one hand touching hair, elegant casual pose"),
            ("У стены", "fashion model standing near wall, one hand on waist, other hanging freely"),
            ("Смещение веса", "model standing in contrapposto pose, hip slightly shifted, elegant balance"),
            ("Руки на талии", "both hands on waist, confident posture, straight shoulders"),
            ("Одна рука в кармане", "woman standing with one hand in pocket, natural confident stance"),
            ("Обе руки в карманах", "both hands in pockets, relaxed editorial look"),
            ("Рука на шее", "one hand resting near neck or collar, thoughtful relaxed mood"),
            ("Профиль", "side-angle standing pose, natural posture, soft light on face"),
            ("Полуоборот корпуса", "woman turning slightly toward camera, gentle motion implied"),
            ("С одной сумкой", "model standing with handbag in one hand, elegant relaxed posture"),
            ("Сложенные руки", "woman standing with arms loosely crossed, confident calm expression"),
        ],
        "Движение / динамика": [
            ("Идёт вперёд", "woman walking slowly toward camera, one leg in motion, fluid movement"),
            ("В движении", "model mid-walk, coat or hair flowing, cinematic motion blur"),
            ("Поворот на ходу", "elegant woman turning slightly while walking, natural stride"),
            ("Шаг в сторону", "model taking a step sideways, confident dynamic posture"),
            ("Подиумный шаг", "slow motion runway walk, head slightly turned, graceful flow"),
            ("Поворот корпуса", "model turning body softly while continuing step, natural rhythm"),
            ("Ветер в движении", "hair or fabric caught in motion, confident walk through breeze"),
            ("Поворот головы", "walking with subtle head turn toward camera, confident elegant look"),
            ("Откидывает волосы", "model tossing hair while walking, dynamic yet natural motion"),
            ("Плавный разворот", "slow turning pose mid-motion, dress or jacket moving softly"),
            ("Шаг на камеру", "model walking into frame, soft forward motion, confident composure"),
            ("Спинка", "walking away, back view, coat tails moving, cinematic lighting"),
        ],
        "Сидячие позы": [
            ("Сидит на стуле", "woman sitting on chair gracefully, legs crossed at ankle, straight posture"),
            ("В кресле", "model sitting on armchair, one arm on rest, confident relaxed look"),
            ("На краю дивана", "woman sitting on edge of sofa, leaning slightly forward, natural smile"),
            ("На табурете", "fashion model seated on stool, side-view pose, elongated legs"),
            ("Локти на коленях", "model sitting casually with elbows on knees, deep thoughtful gaze"),
        ],
        "Переходные / полусидячие позы": [
            ("Опора на стену", "woman leaning against wall, one leg bent, one hand in pocket"),
            ("Опора на стол", "model leaning slightly on table edge, relaxed and stylish"),
            ("Полусидя", "woman half-kneeling or crouching, confident modern editorial pose"),
            ("Опора на руки", "model resting back on hands, legs forward, relaxed pose"),
        ],
        "Пластичные позы": [
            ("Выбиг в спине", "high-fashion pose, arched back, head slightly tilted, expressive hands"),
            ("Элегантная согнутая рука", "editorial pose with one shoulder raised, elegant tension in body line"),
            ("Поворот корпуса", "fashion model twisting torso slightly, soft graceful tension"),
            ("Плавное движение", "cinematic movement with fluid arm line, minimalistic elegance"),
        ],
        "Портреты": [
            ("Полупрофиль", "half-body portrait, head turned slightly, shoulders relaxed"),
            ("¾ портрет", "three-quarter portrait, one hand near face, elegant composure"),
            ("Боковой ракурс", "side-angle portrait, light outlining jawline and neck"),
            ("Профиль", "profile portrait, serene expression, smooth posture"),
            ("Прямой взгляд", "half-body portrait, model looking directly at camera, confident calm expression"),
            ("Плечо вперёд", "model turning shoulder toward camera, confident yet relaxed look"),
            ("Рука у лица", "hand near chin or cheek, elegant thoughtful gesture"),
            ("Две руки у лица", "both hands framing face softly, fashion editorial composition"),
            ("Касание шеи", "one hand gently touching neck, refined elegance, cinematic light"),
            ("Улыбка", "natural smile, warm soft light, confident friendly expression"),
            ("Портрет сидя", "half-body seated portrait, hands relaxed on lap, calm balance"),
        ],
    }


# ---------------------- VIDEO SCENARIO DATA ---------------------- #
def get_video_scenario_data() -> Dict[str, List[Tuple[str, str]]]:
    """
    {
      "Группа": [
         ("Название сценария", "prompt"),
         ...
      ]
    }
    """
    return {
        "Стоячие сцены": [
            (
                "Естественное оживление",
                "subtle motion video — model breathing softly, blinking naturally, slight shoulder and "
                "chest movement, fabric shifts gently with light, same background and lighting, no new objects",
            ),
            (
                "Лёгкий поворот корпуса",
                "short fashion clip — model slowly turning torso to the side and back, keeping calm "
                "expression, soft reflection on outfit, maintain same environment and framing",
            ),
            (
                "Полуразворот к камере",
                "elegant motion video — model turning half toward camera, slight smile, subtle change "
                "of posture, smooth cinematic motion, no new props or background changes",
            ),
            (
                "Исправление стойки",
                "fashion video — model adjusting posture slightly, shifting weight from one leg to "
                "another, relaxed natural pose, same lighting and scene, realistic subtle motion",
            ),
        ],
        "Движение / динамика (видео)": [
            (
                "Медленный шаг вперёд",
                "editorial video — woman taking one graceful step forward, fabric moving softly, camera "
                "fixed, focus on silhouette and light play, no environment change",
            ),
            (
                "Поворот с шагом",
                "short cinematic motion — model turning sideways while walking half step, elegant "
                "movement of trousers or dress, stable lighting, same setting, no new elements",
            ),
            (
                "Замедленное движение",
                "fashion slow-motion — model gently walking, coat or hair moving with air, lighting "
                "reflections consistent, clean minimal scene, no new objects",
            ),
        ],
        "Сидячие сцены": [
            (
                "Смена позы",
                "motion portrait — seated model shifts slightly, crosses legs or adjusts posture, "
                "natural breathing, hands resting softly, lighting unchanged, background intact",
            ),
            (
                "Мягкое движение рук",
                "close-up motion — model sitting gracefully, gently moves hand along fabric or hair, "
                "subtle animation, maintain environment and composition",
            ),
            (
                "Взгляд в сторону",
                "gentle cinematic loop — seated woman slowly turns head to the side, eyes following "
                "softly, elegant micro-expression, no scene or object changes",
            ),
        ],
        "Акценты и ткани": [
            (
                "Движение ткани",
                "subtle fashion detail video — light wind effect on fabric, sleeve or skirt moving "
                "gently, no model motion, same camera angle and environment",
            ),
            (
                "Акцент на фактуру",
                "macro motion — close-up on clothing details, soft movement of fabric folds under light, "
                "natural micro-shifts, no background or composition change",
            ),
            (
                "Исправление манжета или воротника",
                "short close-up motion — model softly adjusts sleeve or collar, realistic hand motion, "
                "same lighting, no new props",
            ),
        ],
        "Выражение и эмоция": [
            (
                "Мягкая улыбка",
                "cinematic portrait — model slightly smiles or breathes out softly, eyes relaxed, "
                "natural warmth, lighting and framing consistent, no other changes",
            ),
            (
                "Переход взгляда",
                "short editorial video — model looks away then back to camera, graceful and subtle "
                "expression shift, same environment, no new objects",
            ),
            (
                "Вдох / пауза",
                "intimate fashion motion — model takes gentle breath, chest rises softly, moment of "
                "stillness, same lighting and framing, realistic micro-movement",
            ),
        ],
        "Движение камеры": [
            (
                "Плавный зум-ин",
                "cinematic motion — camera slowly dolly-in toward model, increasing depth and focus, "
                "no subject motion, no new elements",
            ),
            (
                "Плавный зум-аут",
                "editorial parallax — camera gently moves backward creating space around model, "
                "lighting constant, no background change",
            ),
            (
                "Небольшой параллакс",
                "soft parallax motion — slight horizontal camera movement creating depth, subject "
                "remains still, maintain original scene, no object addition",
            ),
        ],
        "Съёмка с несколькими моделями": [
            (
                "Лёгкое взаимодействие",
                "duo fashion motion — two models exchange a short glance or slight synchronized "
                "movement, same background, elegant and natural, no added objects",
            ),
            (
                "Одновременный шаг",
                "group motion — models take one coordinated step forward, fabric moves subtly, clean "
                "lighting, same composition, no environment change",
            ),
        ],
    }


# ---------------------- SEED FUNCTIONS ---------------------- #
async def seed_scenes() -> None:
    data = get_scene_data()
    async with async_session_maker() as session:
        repo = SceneCategoryRepository(session)

        existing_categories = {c.name: c for c in await repo.get_all_categories()}

        for order_c, (cat_name, plans) in enumerate(data.items(), start=1):
            if cat_name in existing_categories:
                cat = existing_categories[cat_name]
            else:
                cat = await repo.add_category(name=cat_name, order_index=order_c)
                existing_categories[cat_name] = cat
            log.info(f"[SCENE CATEGORY] {cat_name} (id={cat.id})")

            existing_subcats = {
                s.name: s for s in await repo.get_subcategories_by_category(cat.id)
            }

            for order_s, (plan_name, prompt_text) in enumerate(plans.items(), start=1):
                if plan_name in existing_subcats:
                    sub = existing_subcats[plan_name]
                else:
                    sub = await repo.add_subcategory(
                        category_id=cat.id,
                        name=plan_name,
                        order_index=order_s,
                    )
                    existing_subcats[plan_name] = sub
                log.info(f"  [SCENE SUBCATEGORY] {plan_name} (id={sub.id}) in {cat_name}")

                existing_items = {
                    i.name: i for i in await repo.get_items_by_subcategory(sub.id)
                }
                item_name = plan_name  # 1 item per план

                if item_name in existing_items:
                    item = existing_items[item_name]
                    await repo.update_item(item.id, name=item_name, prompt=prompt_text)
                    log.info(f"    [SCENE ITEM:update] {item_name} (id={item.id})")
                else:
                    item = await repo.add_item(
                        subcategory_id=sub.id,
                        name=item_name,
                        prompt=prompt_text,
                        order_index=1,
                    )
                    log.info(f"    [SCENE ITEM] {item_name} (id={item.id})")


async def seed_poses() -> None:
    data = get_pose_data()
    async with async_session_maker() as session:
        repo = PoseRepository(session)

        existing_groups = {g.name: g for g in await repo.get_all_groups()}

        for order_g, (group_name, poses) in enumerate(data.items(), start=1):
            if group_name in existing_groups:
                group = existing_groups[group_name]
            else:
                group = await repo.add_group(name=group_name, order_index=order_g)
                existing_groups[group_name] = group
            log.info(f"[POSE GROUP] {group_name} (id={group.id})")

            subgroup_name = "Основные"
            existing_subgroups = {
                s.name: s for s in await repo.get_subgroups_by_group(group.id)
            }

            if subgroup_name in existing_subgroups:
                subgroup = existing_subgroups[subgroup_name]
            else:
                subgroup = await repo.add_subgroup(
                    group_id=group.id,
                    name=subgroup_name,
                    order_index=1,
                )
            log.info(
                f"  [POSE SUBGROUP] {subgroup.name} (id={subgroup.id}) in {group_name}"
            )

            existing_prompts = {
                p.name: p for p in await repo.get_prompts_by_subgroup(subgroup.id)
            }

            for order_p, (pose_name, prompt) in enumerate(poses, start=1):
                if pose_name in existing_prompts:
                    pp = existing_prompts[pose_name]
                    await repo.update_prompt(pp.id, name=pose_name, prompt=prompt)
                    log.info(f"    [POSE:update] {pose_name} (id={pp.id})")
                else:
                    pp = await repo.add_prompt(
                        subgroup_id=subgroup.id,
                        name=pose_name,
                        prompt=prompt,
                        order_index=order_p,
                    )
                    log.info(f"    [POSE] {pose_name} (id={pp.id})")


async def seed_video_scenarios() -> None:
    data = get_video_scenario_data()
    async with async_session_maker() as session:
        repo = VideoScenarioRepository(session)

        existing = await repo.get_all()
        existing_by_name = {v.name: v for v in existing}

        order_idx = 1
        for group_name, scenarios in data.items():
            for name, prompt in scenarios:
                full_name = f"{group_name} — {name}"
                if full_name in existing_by_name:
                    vs = existing_by_name[full_name]
                    await repo.update(
                        scenario_id=vs.id,
                        name=full_name,
                        prompt=prompt,
                        order_index=order_idx,
                        is_active=True,
                    )
                    log.info(f"[VIDEO:update] {full_name} (id={vs.id})")
                else:
                    vs = await repo.add(
                        name=full_name,
                        prompt=prompt,
                        order_index=order_idx,
                        is_active=True,
                    )
                    log.info(f"[VIDEO] {full_name} (id={vs.id})")
                order_idx += 1


# ---------------------- MAIN ---------------------- #
async def main():
    log.info("=== START MIGRATION: Scenes, Poses, Video Scenarios ===")
    await seed_scenes()
    await seed_poses()
    await seed_video_scenarios()
    log.info("=== DONE MIGRATION ===")


if __name__ == "__main__":
    asyncio.run(main())
