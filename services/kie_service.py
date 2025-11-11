import aiohttp
import asyncio
import requests
import json
import base64
import time
from typing import Optional, List, Dict
from config import settings
import logging

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
    
    def get_model_base(self, model: str) -> str:
        return model.split('/')[0]
    
    def create_task(self, model: str, input_data: dict) -> str:
        payload = {
            "model": model,
            "input": input_data
        }
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
        
        status_info = {
            "status": state,
            "result": result_dict
        }
        
        return status_info

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
                
                logger.info(f"Task {task_id} still processing, waiting 10 seconds...")
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
        from services.config_loader import config_loader
        
        photo_url = data["photo_url"]
        results = []
        generation_type = data["generation_type"]
        model = "google/nano-banana-edit"
        
        if generation_type == "all_scenes":
            scenes = config_loader.scenes.get("scenes", [])
            plans = ["far", "medium", "close"]
            for scene in scenes:
                for plan in plans:
                    scene_prompt = scene["prompts"][plan]
                    full_prompt = f"Create a professional product card: Place the product from the reference image into {scene_prompt}. High quality, photorealistic, studio lighting, clean background."
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
                        results.append({"image": image_bytes, "scene_name": scene["name"], "plan": plan})
        
        elif generation_type == "group_scenes":
            group_id = data["selected_group"]
            scenes = config_loader.get_scenes_by_group(group_id)
            plans = ["far", "medium", "close"]
            for scene in scenes:
                for plan in plans:
                    scene_prompt = scene["prompts"][plan]
                    full_prompt = f"Create a professional product card: Place the product from the reference image into {scene_prompt}. High quality, photorealistic, studio lighting, clean background."
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
                        results.append({"image": image_bytes, "scene_name": scene["name"], "plan": plan})
        
        elif generation_type == "single_scene":
            scene = config_loader.get_scene_by_id(data["selected_scene"])
            plan = data["selected_plan"]
            scene_prompt = scene["prompts"][plan]
            full_prompt = f"Create a professional product card: Place the product from the reference image into {scene_prompt}. High quality, photorealistic, studio lighting, clean background."
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
                results.append({"image": image_bytes, "scene_name": scene["name"], "plan": plan})
        
        return results
    
    async def normalize_own_model(self, item_image_url: str, model_image_url: str) -> dict:
        model = "google/nano-banana-edit"
        
        ghost_prompt = "Create a ghost mannequin from the reference image: transparent body, light background, no face, professional product photography, high detail, photorealistic."
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
        
        combine_prompt = (
            "Professional product normalization: Take the ghost mannequin from the first reference image "
            "and place it on the model from the second reference image. "
            "Match pose, lighting, and style perfectly. Maintain product details, natural lighting, high quality, photorealistic."
        )
        input_data_combine = {
            "prompt": combine_prompt,
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
        
        ghost_prompt = "Create a ghost mannequin from the reference image: transparent body, light background, no face, professional product photography, high detail, photorealistic."
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
        
        combine_prompt = f"Professional product normalization: Take the ghost mannequin from the reference image and place it on a new model described as: {model_prompt}. High quality, photorealistic, studio lighting, natural pose."
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
            input_data = {
                "image_urls": [image_url],
                "index": 0,
                "prompt": prompt,
                "mode": "normal"
            }
            logger.info("Using Grok model format")
        else:  
            input_data = {
                "prompt": prompt,
                "image_url": image_url,
                "duration": str(duration),
                "resolution": resolution
            }
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
        
        # Create scene change prompt
        full_prompt = f"Scene transformation using the reference image: Change the background and scene to {prompt}. Keep the main subject (person or product) unchanged, professional photography, high detail, photorealistic."
        
        input_data = {
            "prompt": full_prompt,
            "image_urls": [image_url],
            "output_format": "png",
            "image_size": "1:1"
        }
        
        task_id = await asyncio.to_thread(self.create_task, model, input_data)
        result = await self.poll_task(task_id)
        if "resultUrls" in result and result["resultUrls"]:
            return {"image": await self.download_image(result["resultUrls"][0])}
        raise ValueError("No image in result")
    
    async def change_pose(self, image_url: str, prompt: str) -> dict:
        model = "google/nano-banana-edit"
        
        # Create pose change prompt
        full_prompt = f"Pose transformation using the reference image: Change the pose to {prompt}. Keep the face, clothing, and other details unchanged, natural body position, professional photography, high quality."
        
        input_data = {
            "prompt": full_prompt,
            "image_urls": [image_url],
            "output_format": "png",
            "image_size": "1:1"
        }
        
        task_id = await asyncio.to_thread(self.create_task, model, input_data)
        result = await self.poll_task(task_id)
        if "resultUrls" in result and result["resultUrls"]:
            return {"image": await self.download_image(result["resultUrls"][0])}
        raise ValueError("No image in result")
    
    async def custom_generation(self, image_url: str, prompt: str) -> dict:
        model = "google/nano-banana-edit"
        
        full_prompt = f"Custom image edit based on the reference image: {prompt}. High quality, photorealistic, maintain original subject details."
        
        input_data = {
            "prompt": full_prompt,
            "image_urls": [image_url],
            "output_format": "png",
            "image_size": "1:1"
        }
        
        task_id = await asyncio.to_thread(self.create_task, model, input_data)
        result = await self.poll_task(task_id)
        if "resultUrls" in result and result["resultUrls"]:
            return {"image": await self.download_image(result["resultUrls"][0])}
        raise ValueError("No image in result")


kie_service = KIEService()