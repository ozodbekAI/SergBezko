"""
Seed: 3-level Scenes (Category -> Subcategory (Plan) -> Items)
Run:
    python populate_scenes_3level.py
"""
import asyncio
import logging
from typing import Dict, List, Tuple

from database import async_session_maker
from database.repositories import SceneCategoryRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)


# ---------------------- DATA ---------------------- #
def get_scene_data() -> Dict[str, Dict[str, List[Tuple[str, str]]]]:
    """
    Strukturasi:
    {
      "Категория": {
          "Подкатегория (план)": [
              ("Item nomi (kreativ)", "prompt"),
              ...
          ],
          ...
      },
      ...
    }
    Har bir plan uchun 2 ta item (nom + prompt) berilgan.
    """
    return {
        # 1) Бутик
        "Бутик": {
            "Дальний план": [
                ("Линии пространства бутика",
                 "full-body editorial photo in luxury boutique, polished marble, mirrored walls, clothing racks geometry, soft spotlights, cinematic depth, confident stance"),
                ("Панорама витрин и силуэт",
                 "full-body shot with boutique aisles, elegant reflections, balanced perspective lines, high-end campaign look, natural pose, airy composition"),
            ],
            "Средний план": [
                ("Силуэт у витрины",
                 "half-body portrait near glass showcase, soft bokeh from warm lights, focus on waistline and drape, refined editorial calm"),
                ("Акцент на крое",
                 "half-body shot, jacket open, subtle turn of shoulders, boutique background softly blurred, delicate light on fabric contours"),
            ],
            "Крупный план": [
                ("Текстуры и блеск",
                 "close-up on neckline and fabric grain, subtle jewelry glint, shallow DOF, glossy magazine aesthetic, tactile material rendering"),
                ("Деталь лацкана",
                 "macro lapel/stitched seam close-up, creamy background blur, precise texture, premium fashion feel"),
            ],
            "Боковой вид": [
                ("Профиль у зеркальной панели",
                 "side-angle portrait, warm light contours silhouette, mirror reflection extends geometry, elegant posture, natural realism"),
                ("Плечевая линия",
                 "side view emphasizing shoulder line and garment drape, soft highlight, minimalist background reflections"),
            ],
            "Вид со спины": [
                ("Уход через коридор",
                 "back view full-body, walking down boutique corridor, golden reflections, focus on back tailoring and motion"),
                ("Контуры на полировке",
                 "back view near polished floor, long reflection, calm stride, cinematic space"),
            ],
            "Динамический кадр": [
                ("Поворот с блеском",
                 "fashion motion turn, fabric trailing, mirror streaks, elegant energy, slight motion blur"),
                ("Шаг между стеллажами",
                 "dynamic step between racks, airy light, floating hem, editorial movement"),
            ],
        },

        # 2) Классическая гостиная
        "Классическая гостиная": {
            "Дальний план": [
                ("Высокие окна и перспектива",
                 "full-body in neoclassical living room, tall windows, neutral palette, elegant furniture, clean perspective, soft daylight"),
                ("Композиция с колонной",
                 "full-body framed by column and sofa, calm editorial spacing, refined symmetry, natural pose"),
            ],
            "Средний план": [
                ("У старинного дивана",
                 "mid-shot near vintage sofa, light shaping waist and silhouette, gentle shadows, minimal refined mood"),
                ("Контраст фактур",
                 "mid-shot, fabric vs. carved wood contrast, warm side light, balanced framing"),
            ],
            "Крупный план": [
                ("Пуговицы и манжеты",
                 "close-up on buttons/cuffs, creamy background blur, tactile fabric detail, warm reflection"),
                ("Текстура воротника",
                 "macro neckline and seam, delicate highlight, magazine clarity"),
            ],
            "Боковой вид": [
                ("Профиль у колонны",
                 "profile near classical column, soft window light, elegant balance, serene editorial tone"),
                ("Линия плеча в полутени",
                 "side profile emphasizing shoulder curve, subtle half-light, sculptural feel"),
            ],
            "Вид со спины": [
                ("Контражур у окна",
                 "back view near window, daylight outlining hair and folds, calm sophisticated atmosphere"),
                ("Шов и драпировка",
                 "back view with focus on back seam and garment drape, neutral tones, gentle light"),
            ],
            "Динамический кадр": [
                ("Шаг по комнате",
                 "graceful walk across room, soft daylight trails, floating fabric, cinematic calm"),
                ("Плавный разворот",
                 "slow turn, hemline motion, timeless editorial stillness"),
            ],
        },

        # 3) Улица / Переход через улицу
        "Улица / Переход через улицу": {
            "Дальний план": [
                ("Шаг через город",
                 "full-body outdoor crossing street, modern architecture blur, strong sunlight, confident stride"),
                ("Городская перспектива",
                 "full-body with crosswalk lines leading depth, cars bokeh, dynamic yet elegant pose"),
            ],
            "Средний план": [
                ("На пешеходном переходе",
                 "half-body at crosswalk, breeze moving fabric, confident gaze, urban bokeh"),
                ("У края тротуара",
                 "mid-shot at curb, poised stance, highlights on contours, city glow"),
            ],
            "Крупный план": [
                ("Отблеск города в аксессуарах",
                 "close-up collar/lapel, sunglasses reflection of skyline, cinematic contrast lighting"),
                ("Текстура костюма",
                 "macro suiting fabric texture, crisp detail, shallow DOF, urban tone"),
            ],
            "Боковой вид": [
                ("Профиль на переходе",
                 "side view mid-step, wind lift, sun accent on profile, sense of motion"),
                ("Городские контуры",
                 "side-angle with building lines, moving traffic bokeh, clean silhouette"),
            ],
            "Вид со спины": [
                ("В закат по зебре",
                 "back view walking golden-hour, coat tails in motion, confident energy"),
                ("Шлейф движения",
                 "back view with subtle motion trail, warm reflections"),
            ],
            "Динамический кадр": [
                ("Разворот на ходу",
                 "turning mid-step, fabric swirl, strong sunlight flicker, cinematic energy"),
                ("Жест и шаг",
                 "adjusting jacket while walking, natural flow, motion emphasis"),
            ],
        },

        # 4) Индустриальный лофт
        "Индустриальный лофт": {
            "Дальний план": [
                ("Пространство кирпича и света",
                 "full-body in industrial loft, exposed brick, large windows, soft daylight, minimalist props"),
                ("Графика металла",
                 "full-body with steel structures, airy composition, editorial framing"),
            ],
            "Средний план": [
                ("У окна и колонны",
                 "waist-up near window or column, warm sunlight on contours, modern creative feel"),
                ("Контуры на кирпиче",
                 "mid-shot, fabric vs. brick texture contrast, subtle highlight"),
            ],
            "Крупный план": [
                ("Золотой свет на швах",
                 "close-up stitching/buttons, golden side light, realistic tactile depth"),
                ("Фактура денима/твила",
                 "macro fold texture, soft background metal blur, precise detail"),
            ],
            "Боковой вид": [
                ("Профиль у панорамного окна",
                 "side portrait, natural light defining shoulder line, textured brick background"),
                ("Линия силуэта",
                 "side-angle emphasizing garment drape, clean modern tone"),
            ],
            "Вид со спины": [
                ("Силуэт на фоне окон",
                 "back view facing window, framed by brick & metal, focus on back tailoring"),
                ("Тихий шаг в цеху",
                 "back view slow walk, moody creative atmosphere"),
            ],
            "Динамический кадр": [
                ("Пыль и лучи",
                 "slow walk across loft, dust in light beams, soft fabric motion, cinematic stillness"),
                ("Сдвиг ракурса",
                 "gentle turn with trailing hem, ambient daylight flow"),
            ],
        },

        # 5) Холл отеля
        "Холл отеля": {
            "Дальний план": [
                ("Марш по мрамору",
                 "full-body walk in luxury hotel lobby, marble floors, chandeliers, golden ambient light, reflections"),
                ("Ось колонн",
                 "full-body framed by columns, elegant perspective, polished surfaces glow"),
            ],
            "Средний план": [
                ("У лифта",
                 "half-body near elevator/chandelier bokeh, soft warm light, poised confident look"),
                ("Силуэт у колонны",
                 "mid-shot by marble column, warm rim light on contours, campaign feel"),
            ],
            "Крупный план": [
                ("Блики люстр",
                 "neckline/jewelry close-up, chandelier bokeh, glossy high-end aesthetic"),
                ("Текстура шелка",
                 "macro fabric sheen, soft reflections on skin and metal accents"),
            ],
            "Боковой вид": [
                ("Профиль в золоте",
                 "side portrait with golden glow, outline of profile and garment curves"),
                ("Свет на контуре",
                 "side-angle, polished floor reflection line, refined elegance"),
            ],
            "Вид со спины": [
                ("Силуэт в галерее холла",
                 "back view full-body, chandeliers framing, marble reflection, cinematic composition"),
                ("Шаг к выходу",
                 "back view walk across lobby, soft trail of light"),
            ],
            "Динамический кадр": [
                ("Движение люкса",
                 "confident cross-lobby walk, fabric sway, chandelier motion blur"),
                ("Поворот у ресепшн",
                 "turn with flowing hem near reception, graceful editorial tone"),
            ],
        },

        # 6) Видовая веранда на город
        "Видовая веранда на город": {
            "Дальний план": [
                ("Горизонт и свобода",
                 "full-body on rooftop terrace, city skyline, golden hour, wind in fabric and hair, sophisticated vibe"),
                ("Линия парапета",
                 "full-body along terrace edge, cinematic horizon, sense of independence"),
            ],
            "Средний план": [
                ("Закат и силуэт",
                 "waist-up with skyline bokeh, sunset tones on skin, calm confident expression"),
                ("Ветер в лацканах",
                 "mid-shot, subtle breeze moving jacket, elevated mood"),
            ],
            "Крупный план": [
                ("Лацкан и серьга",
                 "close-up on lapel/earring against blurred skyline, warm sun reflections"),
                ("Прядь и ткань",
                 "macro hair movement and fabric texture, crisp detail, modern editorial"),
            ],
            "Боковой вид": [
                ("Профиль на фоне города",
                 "side-angle portrait, hair in breeze, sunset defining silhouette"),
                ("Контур заката",
                 "side view with golden rim light, soft skyline gradient"),
            ],
            "Вид со спины": [
                ("К городу лицом",
                 "back view facing skyline, coat moving slightly with wind, sunset glow"),
                ("Тихая опора на поручень",
                 "back view leaning on railing, serene composition"),
            ],
            "Динамический кадр": [
                ("По кромке террасы",
                 "walking along rooftop edge, wind through fabric, cinematic movement"),
                ("Поворот к горизонту",
                 "slow turn towards horizon, motion blur strokes"),
            ],
        },

        # 7) Галерея
        "Галерея": {
            "Дальний план": [
                ("Минимализм залов",
                 "full-body in modern art gallery, neutral white walls, abstract paintings, soft even light"),
                ("Симметрия экспозиции",
                 "full-body centered between artworks, refined clean aesthetic"),
            ],
            "Средний план": [
                ("У скульптуры",
                 "mid-shot near sculpture, balanced symmetry, calm editorial tone"),
                ("Линии на фоне полотна",
                 "mid-shot with painting backdrop, focus on silhouette and clean lines"),
            ],
            "Крупный план": [
                ("Тактильная материя",
                 "close-up on fabric folds/accessory, soft museum lighting, neutral blur"),
                ("Деталь фурнитуры",
                 "macro clasp/button, understated luxury, precise rendering"),
            ],
            "Боковой вид": [
                ("Профиль у стены",
                 "side-angle portrait near gallery wall, minimal light gradients, garment profile clear"),
                ("Контур в полутоне",
                 "side view with gentle tonal shift, harmonic minimalism"),
            ],
            "Вид со спины": [
                ("Между полотнами",
                 "back view walking between artworks, balanced symmetry, neutral lighting"),
                ("Тихий проход",
                 "back view with soft steps, serene editorial atmosphere"),
            ],
            "Динамический кадр": [
                ("Поворот у инсталляции",
                 "slow turn/walk past artwork, subtle motion blur, flowing fabric"),
                ("Ритм зала",
                 "movement echoing gallery rhythm, timeless minimalist grace"),
            ],
        },

        # 8) Минималистичная студия
        "Минималистичная студия": {
            "Дальний план": [
                ("Чистая геометрия",
                 "full-body in minimal studio, soft daylight, beige walls, neutral background, clean modern elegance"),
                ("Коммерческий кадр",
                 "full-body commercial editorial tone, balanced negative space"),
            ],
            "Средний план": [
                ("Силуэт и пропорции",
                 "half-body, soft natural light, calm expression, focus on proportions, minimal aesthetic"),
                ("У стены в полоборота",
                 "mid-shot near wall, subtle shoulder turn, refined simplicity"),
            ],
            "Крупный план": [
                ("Материал под светом",
                 "close-up fabric texture/neckline, diffused daylight, clean detail focus"),
                ("Строчка и край",
                 "macro seam and edge, precise minimal editorial"),
            ],
            "Боковой вид": [
                ("Контур у стены",
                 "side-angle, daylight outlining silhouette, shoulder/waist softly contoured"),
                ("Пластика линии",
                 "side view emphasizing drape, serene modern look"),
            ],
            "Вид со спины": [
                ("Спокойный разворот",
                 "back view standing/walking, soft wall reflection, focus on back detailing"),
                ("Плавная драпировка",
                 "back view, garment drape and flow, quiet composition"),
            ],
            "Динамический кадр": [
                ("Ход через свет",
                 "dynamic step through studio light streaks, natural motion"),
                ("Линии движения",
                 "gentle move, fabric responds softly, cinematic flow"),
            ],
        },

        # 9) Лофт минимализм
        "Лофт минимализм": {
            "Дальний план": [
                ("Окна и воздух",
                 "full-body in minimalist loft, large windows, daylight filling space, muted palette"),
                ("Чистые плоскости",
                 "full-body with planar walls, effortless elegance, editorial clarity"),
            ],
            "Средний план": [
                ("У окна",
                 "waist-up by window, soft light on face and outfit, calm sophistication"),
                ("Гладкая композиция",
                 "mid-shot with balanced lines, timeless minimalism"),
            ],
            "Крупный план": [
                ("Манжета и линия",
                 "close-up sleeve/neckline, soft natural light, subtle contrast"),
                ("Тон ткани",
                 "macro folds and texture, editorial precision"),
            ],
            "Боковой вид": [
                ("Профиль в луче",
                 "profile near window ray, shoulder line highlighted, textured backdrop"),
                ("Силуэт стены",
                 "side view against plain wall, drape emphasized"),
            ],
            "Вид со спины": [
                ("К свету спиной",
                 "back view facing window, outline by daylight, gentle motion"),
                ("Шаг в тишине",
                 "back view step, quiet spacious mood"),
            ],
            "Динамический кадр": [
                ("Дыхание пространства",
                 "walking across loft, fabric moves naturally, warm sunlight trails"),
                ("Лёгкий поворот",
                 "soft turn, effortless movement, sense of space"),
            ],
        },

        # 10) Арт Галерея минимализм
        "Арт Галерея минимализм": {
            "Дальний план": [
                ("Белые стены и баланс",
                 "full-body in contemporary gallery, neutral walls, natural daylight, refined minimal composition"),
                ("Ось экспозиции",
                 "full-body aligned with exhibits, contemporary atmosphere"),
            ],
            "Средний план": [
                ("У инсталляции",
                 "mid-shot near artwork/sculpture, soft side light, clean lines emphasizing silhouette"),
                ("Сдержанная симметрия",
                 "mid-shot with balanced symmetry, timeless minimal tone"),
            ],
            "Крупный план": [
                ("Текстура и акцент",
                 "close-up on fabric/accessory, diffused gallery light, neutral background, tactile realism"),
                ("Минимал-деталь",
                 "macro understated detail, elegant restraint"),
            ],
            "Боковой вид": [
                ("Профиль у полотна",
                 "side-angle by wall, sunlight defining profile and structure, calm editorial"),
                ("Контур галереи",
                 "side view with subtle glow of art space, minimalist calm"),
            ],
            "Вид со спины": [
                ("Проход вдоль стены",
                 "back view walking along white wall, daylight reflections on floor, poised posture"),
                ("Тихий силуэт",
                 "back view soft focus on back tailoring, serene composition"),
            ],
            "Динамический кадр": [
                ("Шаг мимо искусства",
                 "motion shot turning/walking past artwork, soft daylight motion blur"),
                ("Ритм экспозиции",
                 "flowing fabric echoes gallery rhythm, modern grace"),
            ],
        },
    }


# ---------------------- SEED LOGIC ---------------------- #
async def populate_scenes_3level() -> None:
    data = get_scene_data()

    async with async_session_maker() as session:
        repo = SceneCategoryRepository(session)

        # Cache existing categories once
        existing_categories = {c.name: c for c in await repo.get_all_categories()}

        for order_c, (cat_name, subcats) in enumerate(data.items(), start=1):
            # Category
            if cat_name in existing_categories:
                cat = existing_categories[cat_name]
            else:
                cat = await repo.add_category(name=cat_name, order_index=order_c)
                existing_categories[cat_name] = cat
            log.info(f"[CATEGORY] {cat_name} (id={cat.id})")

            # Subcategories for this category
            existing_subcats = {s.name: s for s in await repo.get_subcategories_by_category(cat.id)}

            for order_s, (sub_name, items) in enumerate(subcats.items(), start=1):
                if sub_name in existing_subcats:
                    sub = existing_subcats[sub_name]
                else:
                    sub = await repo.add_subcategory(category_id=cat.id, name=sub_name, order_index=order_s)
                    existing_subcats[sub_name] = sub
                log.info(f"  [SUBCATEGORY] {sub_name} (id={sub.id}) in {cat_name}")

                # Items for subcategory
                existing_items = {i.name: i for i in await repo.get_items_by_subcategory(sub.id)}

                for order_i, (item_name, prompt) in enumerate(items, start=1):
                    if item_name in existing_items:
                        log.info(f"    [ITEM:skip] {item_name} (exists)")
                        continue
                    item = await repo.add_item(
                        subcategory_id=sub.id,
                        name=item_name,
                        prompt=prompt,
                        order_index=order_i
                    )
                    log.info(f"    [ITEM] {item_name} (id={item.id})")


# ---------------------- MAIN ---------------------- #
async def main():
    log.info("=== START: 3-level scene seeding ===")
    await populate_scenes_3level()
    log.info("=== DONE: 3-level scene seeding ===")


if __name__ == "__main__":
    asyncio.run(main())
