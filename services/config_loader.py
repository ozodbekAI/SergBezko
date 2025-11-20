import yaml
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from database import async_session_maker
from database.repositories import PaymentPackageRepository


class ConfigLoader:
    def __init__(self):
        self.base_dir = Path(__file__).parent / ".." / "configs" 
        self._scenes: Optional[Dict[str, Any]] = None
        self._poses: Optional[Dict[str, Any]] = None
        self._pricing: Optional[Dict[str, Any]] = None
        self._model_types: Optional[Dict[str, Any]] = None
        self._video_scenarios: Optional[Dict[str, Any]] = None

    def _load_yaml(self, file_path: str) -> Dict[str, Any]:
        file = self.base_dir / "presets" / file_path
        if not file.exists():
            raise FileNotFoundError(f"Config file not found: {file}")
        with open(file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _load_json(self, file_path: str) -> Dict[str, Any]:
        file = self.base_dir / file_path
        if not file.exists():
            raise FileNotFoundError(f"Config file not found: {file}")
        with open(file, 'r', encoding='utf-8') as f:
            return json.load(f)

    @property
    def scenes(self) -> Dict[str, Any]:
        if self._scenes is None:
            self._scenes = self._load_yaml("scenes.yaml")
        return self._scenes

    @property
    def poses(self) -> Dict[str, Any]:
        if self._poses is None:
            self._poses = self._load_yaml("poses.yaml")
        return self._poses

    @property
    def pricing(self) -> Dict[str, Any]:
        if self._pricing is None:
            self._pricing = self._load_json("pricing.json")
        return self._pricing

    @property
    def model_types(self) -> Dict[str, Any]:
        if self._model_types is None:
            self._model_types = self._load_yaml("model_types.yaml")
        return self._model_types

    @property
    def video_scenarios(self) -> Dict[str, Any]:
        if self._video_scenarios is None:
            self._video_scenarios = self._load_yaml("video_scenarios.yaml")
        return self._video_scenarios

    def get_scene_groups(self) -> List[Dict[str, str]]:
        groups = self.scenes.get("groups", {})
        return [{"id": group_id, "name": group["name"]} for group_id, group in groups.items()]

    def get_scenes_by_group(self, group_id: str) -> List[Dict[str, Any]]:
        groups = self.scenes.get("groups", {})
        scene_ids = groups.get(group_id, {}).get("scenes", [])  
        scenes_list = self.scenes.get("scenes", []) 
        return [s for s in scenes_list if s["id"] in scene_ids]  

    def get_scene_by_id(self, scene_id: str) -> Dict[str, Any]:
        scenes_list = self.scenes.get("scenes", [])
        for s in scenes_list:
            if s["id"] == scene_id:
                return s
        raise ValueError(f"Scene not found: {scene_id}")

    def get_pose_groups(self) -> List[Dict[str, str]]:
        groups = self.poses.get("groups", {})
        return [{"id": group_id, "name": group["name"]} for group_id, group in groups.items()]

    def get_poses_by_group(self, group_id: str) -> List[Dict[str, Any]]:
        groups = self.poses.get("groups", {})
        pose_ids = groups.get(group_id, {}).get("poses", [])
        poses_list = self.poses.get("poses", [])
        return [p for p in poses_list if p["id"] in pose_ids]

    def get_pose_by_id(self, pose_id: str) -> Dict[str, Any]:
        poses_list = self.poses.get("poses", [])
        for p in poses_list:
            if p["id"] == pose_id:
                return p
        raise ValueError(f"Pose not found: {pose_id}")

    def get_model_type_by_id(self, model_id: str) -> Dict[str, Any]:
        """Get model type by ID from model_types list"""
        model_types_list = self.model_types.get("model_types", [])
        for m in model_types_list:
            if m["id"] == model_id:
                return m
        raise ValueError(f"Model type not found: {model_id}")

    async def get_payment_packages(self) -> List[Dict[str, Any]]:
        """
        Database'dan payment paketlarini olish.
        Agar database'da bo'lmasa, JSON'dan fallback qilish.
        """
        try:
            async with async_session_maker() as session:
                pkg_repo = PaymentPackageRepository(session)
                packages = await pkg_repo.get_all_packages(only_active=True)
                
                if packages:
                    # Database'dan olingan paketlarni formatlash
                    return [
                        {
                            "label": pkg.label,
                            "credits": pkg.credits,
                            "price": pkg.price,
                            "bonus": pkg.bonus
                        }
                        for pkg in packages
                    ]
        except Exception as e:
            # Agar database'da xatolik bo'lsa, JSON'dan o'qish
            import logging
            logging.warning(f"Failed to load packages from DB, using JSON fallback: {e}")
        
        # Fallback: JSON'dan o'qish
        return self.pricing.get("packages", [])
    
    def get_video_scenario_by_id(self, scenario_id: str) -> Dict[str, Any]:
        """Get video scenario by ID from video_scenarios list"""
        scenarios_list = self.video_scenarios.get("video_scenarios", [])
        for s in scenarios_list:
            if s["id"] == scenario_id:
                return s
        raise ValueError(f"Video scenario not found: {scenario_id}")


# Global instance
config_loader = ConfigLoader()