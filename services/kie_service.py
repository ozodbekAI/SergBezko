import aiohttp
import asyncio
import requests
import json
import base64
import time
from typing import Optional, List, Dict
from config import settings
import logging

from database import async_session_maker
from database.repositories import BotMessageRepository, SceneCategoryRepository

logger = logging.getLogger(__name__)

class KIEService:
    def __init__(self):
        self.api_key = settings.KIE_API_KEY
        self.create_url = "https://api.kie.ai/api/v1/jobs/createTask"
        self.query_url = "https://api.kie.ai/api/v1/jobs/recordInfo"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    DEFAULT_GHOST_PROMPT = (
        "Create a ghost mannequin from the reference image: transparent body, "
        "light background, no face, professional product photography, high detail, photorealistic."
    )

    DEFAULT_OWN_COMBINE_PROMPT = (
        "Professional product normalization: Take the ghost mannequin from the first reference image "
        "and place it on the model from the second reference image. "
        "Match pose, lighting, and style perfectly. Maintain product details, natural lighting, high quality, photorealistic."
    )

    async def _get_normalize_prompts(self) -> tuple[str, str]:
        """
        1) ghost_prompt  - birinchi rasm (maneken / ghost) uchun
        2) own_combine   - 'Есть своя фотомодель' rejimida ghost + modelni birlashtirish uchun
        """
        async with async_session_maker() as session:
            msg_repo = BotMessageRepository(session)
            ghost_msg = await msg_repo.get_message("normalize_prompt_step1")
            own_msg = await msg_repo.get_message("normalize_prompt_step2_own")

        ghost_prompt = (ghost_msg.text if ghost_msg and ghost_msg.text else self.DEFAULT_GHOST_PROMPT)
        own_combine_prompt = (own_msg.text if own_msg and own_msg.text else self.DEFAULT_OWN_COMBINE_PROMPT)
        return ghost_prompt, own_combine_prompt

    def get_model_base(self, model: str) -> str:
        return model.split('/')[0]
    
    def create_task(self, model: str, input_data: dict) -> str:
        payload = {"model": model, "input": input_data}
        logger.info(f"Creating task with model: {model}")
        logger.info(f"Input data: {json.dumps(input_data, ensure_ascii=False)[:200]}...")
        response = requests.post(self.create_url, headers=self.headers, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()
        logger.info(f"Create task response: {result}")
        if result.get("code") != 200:
            logger.error(f"API create task error: {result}")
            raise ValueError(f"Failed to create task: {result.get('msg', 'Unknown error')}")
        task_id = result.get("data", {}).get("taskId")
        if not task_id:
            logger.error(f"API response without taskId: {result}")
            raise ValueError(f"Failed to extract taskId: {result}")
        return task_id
    
    def get_task_status(self, task_id: str) -> dict:
        if not task_id:
            raise ValueError("Task ID cannot be None")
        params = {"taskId": task_id}
        response = requests.get(self.query_url, params=params, headers=self.headers)
        logger.info(f"Status request URL: {response.url}, status: {response.status_code}")
        logger.info(f"Raw response: {response.text}")
        response.raise_for_status()
        result = response.json()
        logger.info(f"Status response parsed: {result}")
        if result.get("code") != 200:
            error_msg = result.get("message") or result.get("msg", "Unknown error")
            logger.error(f"API status error: {result}")
            raise ValueError(f"Failed to get status: {error_msg}")
        data = result.get("data", {})
        state = data.get("state", "unknown")
        result_json_str = data.get("resultJson", "{}")
        try:
            result_dict = json.loads(result_json_str) if result_json_str else {}
            logger.info(f"Parsed resultJson: {result_dict}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse resultJson: {result_json_str}, error: {e}")
            result_dict = {}
        if state in ["fail", "failed", "error"]:
            fail_msg = data.get("failMsg", "Unknown error")
            fail_code = data.get("failCode", "Unknown")
            logger.error(f"Task failed - Code: {fail_code}, Message: {fail_msg}")
            raise Exception(f"Task failed: {fail_msg} (code: {fail_code})")
        return {"status": state, "result": result_dict}

    async def poll_task(self, task_id: str, max_attempts: int = 120) -> dict:
        for attempt in range(max_attempts):
            try:
                status_info = await asyncio.to_thread(self.get_task_status, task_id)
                logger.info(f"Poll attempt {attempt + 1}/{max_attempts} for {task_id}: status={status_info['status']}")
                if status_info["status"] == "success":
                    logger.info(f"Task {task_id} completed successfully!")
                    return status_info["result"]
                elif status_info["status"] in ["fail", "failed", "error"]:
                    logger.error(f"Task {task_id} failed with status: {status_info['status']}")
                    raise Exception(f"Task failed: {status_info}")
                logger.info("Task still processing, waiting 10 seconds...")
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"Error polling task {task_id} on attempt {attempt + 1}: {e}")
                if attempt == max_attempts - 1:
                    raise
                logger.info("Retrying in 10 seconds...")
                await asyncio.sleep(10)
        raise Exception(f"Task timeout after {max_attempts} attempts ({max_attempts * 10} seconds)")

    async def download_image(self, url: str) -> bytes:
        logger.info(f"Downloading content from: {url}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                    response.raise_for_status()
                    content = await response.read()
                    logger.info(f"Successfully downloaded {len(content)} bytes")
                    return content
        except Exception as e:
            logger.error(f"Failed to download from {url}: {e}")
            raise


    async def generate_product_cards(self, data: dict) -> list:
        photo_url = data["photo_url"]
        results = []
        model = "google/nano-banana-edit"

        async with async_session_maker() as session:
            scene_repo = SceneCategoryRepository(session)

            if data["generation_type"] == "all_scenes":
                hierarchy = await scene_repo.get_full_hierarchy()
                for cat_id, cat in hierarchy.items():
                    cat_name = cat["name"]
                    for sub_id, sub in cat["subcategories"].items():
                        sub_name = sub["name"]
                        for item in sub["items"]:
                            item_name = item["name"]
                            item_prompt = item["prompt"]
                            full_prompt = (
                                "Create a professional product card: Place the product from the "
                                f"reference image into the scene: {cat_name} → {sub_name} → {item_name}. "
                                f"Details: {item_prompt}. High quality, photorealistic, studio lighting, clean background."
                            )
                            input_data = {
                                "prompt": full_prompt,
                                "image_urls": [photo_url],
                                "output_format": "png",
                                "image_size": "1:1"
                            }
                            task_id = await asyncio.to_thread(self.create_task, model, input_data)
                            result = await self.poll_task(task_id)
                            if "resultUrls" in result and result["resultUrls"]:
                                image_bytes = await self.download_image(result["resultUrls"][0])
                                results.append({
                                    "image": image_bytes,
                                    "category": cat_name,
                                    "subcategory": sub_name,
                                    "item": item_name
                                })

            elif data["generation_type"] == "group_scenes":
                category_id = int(data["selected_group"])
                category = await scene_repo.get_category(category_id)
                if not category:
                    raise ValueError(f"Scene category {category_id} not found")

                subcats = await scene_repo.get_subcategories_by_category(category_id)
                for sub in subcats:
                    items = await scene_repo.get_items_by_subcategory(sub.id)
                    for it in items:
                        full_prompt = (
                            "Create a professional product card: Place the product from the "
                            f"reference image into the scene: {category.name} → {sub.name} → {it.name}. "
                            f"Details: {it.prompt}. High quality, photorealistic, studio lighting, clean background."
                        )
                        input_data = {
                            "prompt": full_prompt,
                            "image_urls": [photo_url],
                            "output_format": "png",
                            "image_size": "1:1"
                        }
                        task_id = await asyncio.to_thread(self.create_task, model, input_data)
                        result = await self.poll_task(task_id)
                        if "resultUrls" in result and result["resultUrls"]:
                            image_bytes = await self.download_image(result["resultUrls"][0])
                            results.append({
                                "image": image_bytes,
                                "category": category.name,
                                "subcategory": sub.name,
                                "item": it.name
                            })

            elif data["generation_type"] == "single_scene":
                item_id = int(data["selected_item"])
                item = await scene_repo.get_item(item_id)
                if not item:
                    raise ValueError(f"Scene item {item_id} not found")

                sub = await scene_repo.get_subcategory(item.subcategory_id)
                if not sub:
                    raise ValueError(f"Subcategory {item.subcategory_id} for item {item_id} not found")

                cat = await scene_repo.get_category(sub.category_id)
                if not cat:
                    raise ValueError(f"Category {sub.category_id} for subcategory {sub.id} not found")

                full_prompt = (
                    "Create a professional product card: Place the product from the "
                    f"reference image into the scene: {cat.name} → {sub.name} → {item.name}. "
                    f"Details: {item.prompt}. High quality, photorealistic, studio lighting, clean background."
                )
                input_data = {
                    "prompt": full_prompt,
                    "image_urls": [photo_url],
                    "output_format": "png",
                    "image_size": "1:1"
                }
                task_id = await asyncio.to_thread(self.create_task, model, input_data)
                result = await self.poll_task(task_id)
                if "resultUrls" in result and result["resultUrls"]:
                    image_bytes = await self.download_image(result["resultUrls"][0])
                    results.append({
                        "image": image_bytes,
                        "category": cat.name,
                        "subcategory": sub.name,
                        "item": item.name
                    })
            else:
                raise ValueError("Unknown generation_type")

        return results

    async def normalize_own_model(self, item_image_url: str, model_image_url: str) -> dict:
        model = "google/nano-banana-edit"

        # 1) PROMPT – ghost / maneken (ikkala tugma uchun umumiy)
        ghost_prompt, own_combine_prompt = await self._get_normalize_prompts()

        # 1-qadam: itemdan ghost / maneken
        input_data_ghost = {
            "prompt": ghost_prompt,
            "image_urls": [item_image_url],
            "output_format": "png",
            "image_size": "1:1"
        }
        task_id_ghost = await asyncio.to_thread(self.create_task, model, input_data_ghost)
        ghost_result = await self.poll_task(task_id_ghost)
        if "resultUrls" not in ghost_result or not ghost_result["resultUrls"]:
            raise ValueError("No ghost image in result")
        ghost_url = ghost_result["resultUrls"][0]

        # 2) PROMPT – admin kiritgan 'own' kombinat promnti
        input_data_combine = {
            "prompt": own_combine_prompt,
            "image_urls": [ghost_url, model_image_url],
            "output_format": "png",
            "image_size": "1:1"
        }
        task_id_combine = await asyncio.to_thread(self.create_task, model, input_data_combine)
        combine_result = await self.poll_task(task_id_combine)
        if "resultUrls" in combine_result and combine_result["resultUrls"]:
            return {"image": await self.download_image(combine_result["resultUrls"][0])}
        raise ValueError("No final image in result")

    async def normalize_new_model(self, item_image_url: str, model_prompt: str) -> dict:
        model = "google/nano-banana-edit"

        # Faqat 1-PROMPT (ghost) – admin paneldan
        ghost_prompt, _ = await self._get_normalize_prompts()

        # 1-qadam: itemdan ghost / maneken
        input_data_ghost = {
            "prompt": ghost_prompt,
            "image_urls": [item_image_url],
            "output_format": "png",
            "image_size": "1:1"
        }
        task_id_ghost = await asyncio.to_thread(self.create_task, model, input_data_ghost)
        ghost_result = await self.poll_task(task_id_ghost)
        if "resultUrls" not in ghost_result or not ghost_result["resultUrls"]:
            raise ValueError("No ghost image in result")
        ghost_url = ghost_result["resultUrls"][0]

        # 2-qadam: yangi fotomodelni AI bilan generatsiya qilish (oldingidek)
        combine_prompt = (
            "Professional product normalization: Take the ghost mannequin from the reference image "
            "and place it on a new model described as: "
            f"{model_prompt}. High quality, photorealistic, studio lighting, natural pose."
        )
        input_data_combine = {
            "prompt": combine_prompt,
            "image_urls": [ghost_url],
            "output_format": "png",
            "image_size": "1:1"
        }
        task_id_combine = await asyncio.to_thread(self.create_task, model, input_data_combine)
        combine_result = await self.poll_task(task_id_combine)
        if "resultUrls" in combine_result and combine_result["resultUrls"]:
            return {"image": await self.download_image(combine_result["resultUrls"][0])}
        raise ValueError("No final image in result")

    async def generate_video(self, image_url: str, prompt: str, model: str, duration: int, resolution: str) -> dict:
        logger.info(f"Starting video generation with model: {model}")
        logger.info(f"Image URL: {image_url}")
        logger.info(f"Prompt: {prompt}")
        logger.info(f"Duration: {duration}, Resolution: {resolution}")
        if "grok" in model.lower():
            input_data = {"image_urls": [image_url], "index": 0, "prompt": prompt, "mode": "normal"}
            logger.info("Using Grok model format")
        else:
            input_data = {"prompt": prompt, "image_url": image_url, "duration": str(duration), "resolution": resolution}
            logger.info("Using Hailuo model format")
        logger.info(f"Creating task with input: {input_data}")
        task_id = await asyncio.to_thread(self.create_task, model, input_data)
        logger.info(f"Task created with ID: {task_id}")
        logger.info("Starting to poll task status...")
        result = await self.poll_task(task_id)
        logger.info(f"Video generation complete! Result: {result}")
        if "resultUrls" in result and result["resultUrls"]:
            video_url = result["resultUrls"][0]
            logger.info(f"Downloading video from: {video_url}")
            video_bytes = await self.download_image(video_url)
            logger.info(f"Video downloaded successfully, size: {len(video_bytes)} bytes")
            return {"video": video_bytes}
        logger.error(f"No video URLs in result: {result}")
        raise ValueError(f"No video URLs in result: {result}")

    async def change_scene(self, image_url: str, prompt: str) -> dict:
        model = "google/nano-banana-edit"
        full_prompt = f"Scene transformation using the reference image: Change the background and scene to {prompt}. Keep the main subject (person or product) unchanged, professional photography, high detail, photorealistic."
        input_data = {"prompt": full_prompt, "image_urls": [image_url], "output_format": "png", "image_size": "1:1"}
        task_id = await asyncio.to_thread(self.create_task, model, input_data)
        result = await self.poll_task(task_id)
        if "resultUrls" in result and result["resultUrls"]:
            return {"image": await self.download_image(result["resultUrls"][0])}
        raise ValueError("No image in result")

    async def change_pose(self, image_url: str, prompt: str) -> dict:
        model = "google/nano-banana-edit"
        full_prompt = f"Pose transformation using the reference image: Change the pose to {prompt}. Keep the face, clothing, and other details unchanged, natural body position, professional photography, high quality."
        input_data = {"prompt": full_prompt, "image_urls": [image_url], "output_format": "png", "image_size": "1:1"}
        task_id = await asyncio.to_thread(self.create_task, model, input_data)
        result = await self.poll_task(task_id)
        if "resultUrls" in result and result["resultUrls"]:
            return {"image": await self.download_image(result["resultUrls"][0])}
        raise ValueError("No image in result")

    async def custom_generation(self, image_url: str, prompt: str) -> dict:
        model = "google/nano-banana-edit"
        full_prompt = f"Custom image edit based on the reference image: {prompt}. High quality, photorealistic, maintain original subject details."
        input_data = {"prompt": full_prompt, "image_urls": [image_url], "output_format": "png", "image_size": "1:1"}
        task_id = await asyncio.to_thread(self.create_task, model, input_data)
        result = await self.poll_task(task_id)
        if "resultUrls" in result and result["resultUrls"]:
            return {"image": await self.download_image(result["resultUrls"][0])}
        raise ValueError("No image in result")


kie_service = KIEService()
