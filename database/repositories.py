from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload
from database.models import (ScenePlanPrompt, User, Task, Payment, UserState, TaskStatus, TaskType,
                             BotMessage, PoseGroup, PoseSubgroup, PosePrompt,
                             SceneGroup, AdminLog, ModelType)
from typing import Optional, List, Dict
from datetime import datetime, timedelta


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_or_create_user(self, telegram_id: int, username: Optional[str] = None,
                                  first_name: Optional[str] = None, last_name: Optional[str] = None) -> User:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                balance=0
            )
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
        else:
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            user.last_activity = datetime.utcnow()
            await self.session.commit()
        
        return user
    
    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    async def is_admin(self, telegram_id: int) -> bool:
        user = await self.get_user_by_telegram_id(telegram_id)
        return user and user.is_admin
    
    async def is_banned(self, telegram_id: int) -> bool:
        user = await self.get_user_by_telegram_id(telegram_id)
        return user and user.is_banned
    
    async def ban_user(self, telegram_id: int) -> Optional[User]:
        user = await self.get_user_by_telegram_id(telegram_id)
        if user:
            user.is_banned = True
            await self.session.commit()
            await self.session.refresh(user)
        return user
    
    async def unban_user(self, telegram_id: int) -> Optional[User]:
        user = await self.get_user_by_telegram_id(telegram_id)
        if user:
            user.is_banned = False
            await self.session.commit()
            await self.session.refresh(user)
        return user
    
    async def update_balance(self, telegram_id: int, amount: int) -> Optional[User]:
        user = await self.get_user_by_telegram_id(telegram_id)
        if user:
            user.balance += amount
            await self.session.commit()
            await self.session.refresh(user)
        return user
    
    async def check_balance(self, telegram_id: int, required: int) -> bool:
        user = await self.get_user_by_telegram_id(telegram_id)
        return user and user.balance >= required
    
    async def get_total_users(self) -> int:
        result = await self.session.execute(select(func.count(User.id)))
        return result.scalar()
    
    async def get_total_active_users(self, days: int = 30) -> int:
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await self.session.execute(
            select(func.count(User.id)).where(User.last_activity >= cutoff)
        )
        return result.scalar()
    
    async def get_banned_count(self) -> int:
        result = await self.session.execute(
            select(func.count(User.id)).where(User.is_banned == True)
        )
        return result.scalar()
    
    async def get_banned_users(self, limit: int = 20, offset: int = 0) -> List[User]:
        result = await self.session.execute(
            select(User)
            .where(User.is_banned == True)
            .order_by(User.last_activity.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
    
    async def get_all_users(self, limit: int = 20, offset: int = 0) -> List[User]:
        result = await self.session.execute(
            select(User)
            .order_by(User.last_activity.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
    
    async def search_users(self, query: str) -> List[User]:
        query = query.strip()
        
        if query.isdigit():
            telegram_id = int(query)
            result = await self.session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            return [user] if user else []
        
        result = await self.session.execute(
            select(User).where(
                (User.username.ilike(f"%{query}%")) |
                (User.first_name.ilike(f"%{query}%")) |
                (User.last_name.ilike(f"%{query}%"))
            ).limit(20)
        )
        return list(result.scalars().all())


class TaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_user_tasks(self, user_id: int, limit: int = 20) -> List[Task]:
        result = await self.session.execute(
            select(Task).where(Task.user_id == user_id)
            .order_by(Task.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_total_tasks(self) -> int:
        result = await self.session.execute(select(func.count(Task.id)))
        return result.scalar()
    
    async def get_completed_tasks(self) -> int:
        result = await self.session.execute(
            select(func.count(Task.id)).where(Task.status == TaskStatus.COMPLETED)
        )
        return result.scalar()


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_total_payments(self) -> int:
        result = await self.session.execute(
            select(func.count(Payment.id)).where(Payment.status == "succeeded")
        )
        return result.scalar()
    
    async def get_total_credits_sold(self) -> int:
        result = await self.session.execute(
            select(func.sum(Payment.credits)).where(Payment.status == "succeeded")
        )
        return result.scalar() or 0


class BotMessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_message(self, message_key: str) -> Optional[BotMessage]:
        result = await self.session.execute(
            select(BotMessage).where(BotMessage.message_key == message_key)
        )
        return result.scalar_one_or_none()
    
    async def set_message(self, message_key: str, text: str, 
                         media_type: Optional[str] = None,
                         media_file_id: Optional[str] = None) -> BotMessage:
        msg = await self.get_message(message_key)
        if msg:
            msg.text = text
            msg.media_type = media_type
            msg.media_file_id = media_file_id
            msg.updated_at = datetime.utcnow()
        else:
            msg = BotMessage(
                message_key=message_key,
                text=text,
                media_type=media_type,
                media_file_id=media_file_id
            )
            self.session.add(msg)
        
        await self.session.commit()
        await self.session.refresh(msg)
        return msg


# ===== MODEL TYPE REPOSITORY =====

class ModelTypeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_all(self) -> List[ModelType]:
        result = await self.session.execute(
            select(ModelType)
            .where(ModelType.is_active == True)
            .order_by(ModelType.order_index)
        )
        return list(result.scalars().all())
    
    async def get_by_id(self, model_type_id: int) -> Optional[ModelType]:
        result = await self.session.execute(
            select(ModelType).where(ModelType.id == model_type_id)
        )
        return result.scalar_one_or_none()
    
    async def add(self, name: str, prompt: str, order_index: int = 0) -> ModelType:
        model_type = ModelType(
            name=name,
            prompt=prompt,
            order_index=order_index
        )
        self.session.add(model_type)
        await self.session.commit()
        await self.session.refresh(model_type)
        return model_type
    
    async def update(self, model_type_id: int, name: str, prompt: str) -> Optional[ModelType]:
        result = await self.session.execute(
            select(ModelType).where(ModelType.id == model_type_id)
        )
        model_type = result.scalar_one_or_none()
        if model_type:
            model_type.name = name
            model_type.prompt = prompt
            await self.session.commit()
            await self.session.refresh(model_type)
        return model_type
    
    async def delete(self, model_type_id: int):
        await self.session.execute(
            delete(ModelType).where(ModelType.id == model_type_id)
        )
        await self.session.commit()



class PoseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_all_groups(self) -> List[PoseGroup]:
        result = await self.session.execute(
            select(PoseGroup)
            .where(PoseGroup.is_active == True)
            .order_by(PoseGroup.order_index)
        )
        return list(result.scalars().all())
    
    async def get_group(self, group_id: int) -> Optional[PoseGroup]:
        result = await self.session.execute(
            select(PoseGroup).where(PoseGroup.id == group_id)
        )
        return result.scalar_one_or_none()
    
    async def add_group(self, name: str, order_index: int = 0) -> PoseGroup:
        group = PoseGroup(name=name, order_index=order_index)
        self.session.add(group)
        await self.session.commit()
        await self.session.refresh(group)
        return group
    
    async def delete_group(self, group_id: int):
        await self.session.execute(
            delete(PoseGroup).where(PoseGroup.id == group_id)
        )
        await self.session.commit()
    
    async def get_subgroups_by_group(self, group_id: int) -> List[PoseSubgroup]:
        result = await self.session.execute(
            select(PoseSubgroup)
            .where(PoseSubgroup.group_id == group_id, PoseSubgroup.is_active == True)
            .order_by(PoseSubgroup.order_index)
        )
        return list(result.scalars().all())
    
    async def get_subgroup(self, subgroup_id: int) -> Optional[PoseSubgroup]:
        result = await self.session.execute(
            select(PoseSubgroup).where(PoseSubgroup.id == subgroup_id)
        )
        return result.scalar_one_or_none()
    
    async def add_subgroup(self, group_id: int, name: str, order_index: int = 0) -> PoseSubgroup:
        subgroup = PoseSubgroup(
            group_id=group_id,
            name=name,
            order_index=order_index
        )
        self.session.add(subgroup)
        await self.session.commit()
        await self.session.refresh(subgroup)
        return subgroup
    
    async def delete_subgroup(self, subgroup_id: int):
        await self.session.execute(
            delete(PoseSubgroup).where(PoseSubgroup.id == subgroup_id)
        )
        await self.session.commit()
    
    async def get_prompts_by_subgroup(self, subgroup_id: int) -> List[PosePrompt]:
        result = await self.session.execute(
            select(PosePrompt)
            .where(PosePrompt.subgroup_id == subgroup_id, PosePrompt.is_active == True)
            .order_by(PosePrompt.order_index)
        )
        return list(result.scalars().all())
    
    async def get_prompt(self, prompt_id: int) -> Optional[PosePrompt]:
        result = await self.session.execute(
            select(PosePrompt).where(PosePrompt.id == prompt_id)
        )
        return result.scalar_one_or_none()
    
    async def add_prompt(self, subgroup_id: int, name: str, prompt: str, order_index: int = 0) -> PosePrompt:
        pose_prompt = PosePrompt(
            subgroup_id=subgroup_id,
            name=name,
            prompt=prompt,
            order_index=order_index
        )
        self.session.add(pose_prompt)
        await self.session.commit()
        await self.session.refresh(pose_prompt)
        return pose_prompt
    
    async def update_prompt(self, prompt_id: int, name: str, prompt: str) -> Optional[PosePrompt]:
        result = await self.session.execute(
            select(PosePrompt).where(PosePrompt.id == prompt_id)
        )
        pose_prompt = result.scalar_one_or_none()
        if pose_prompt:
            pose_prompt.name = name
            pose_prompt.prompt = prompt
            await self.session.commit()
            await self.session.refresh(pose_prompt)
        return pose_prompt
    
    async def delete_prompt(self, prompt_id: int):
        await self.session.execute(
            delete(PosePrompt).where(PosePrompt.id == prompt_id)
        )
        await self.session.commit()
    
    async def get_full_hierarchy(self) -> Dict:
        result = await self.session.execute(
            select(PoseGroup)
            .options(
                selectinload(PoseGroup.subgroups).selectinload(PoseSubgroup.prompts)
            )
            .where(PoseGroup.is_active == True)
            .order_by(PoseGroup.order_index)
        )
        groups = result.scalars().all()
        
        hierarchy = {}
        for group in groups:
            hierarchy[group.id] = {
                "name": group.name,
                "subgroups": {}
            }
            
            for subgroup in group.subgroups:
                if subgroup.is_active:
                    hierarchy[group.id]["subgroups"][subgroup.id] = {
                        "name": subgroup.name,
                        "prompts": [
                            {"id": p.id, "name": p.name, "prompt": p.prompt} 
                            for p in subgroup.prompts if p.is_active
                        ]
                    }
        
        return hierarchy




class SceneRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # === GROUPS ===
    async def get_all_groups(self) -> List[SceneGroup]:
        result = await self.session.execute(
            select(SceneGroup)
            .where(SceneGroup.is_active == True)
            .order_by(SceneGroup.order_index)
        )
        return list(result.scalars().all())

    async def get_group(self, group_id: int) -> Optional[SceneGroup]:
        result = await self.session.execute(
            select(SceneGroup).where(SceneGroup.id == group_id)
        )
        return result.scalar_one_or_none()

    async def add_group(self, name: str) -> SceneGroup:
        group = SceneGroup(name=name)
        self.session.add(group)
        await self.session.commit()
        await self.session.refresh(group)
        return group

    async def delete_group(self, group_id: int):
        await self.session.execute(delete(SceneGroup).where(SceneGroup.id == group_id))
        await self.session.commit()


    async def add_plan_prompt(self, group_id: int, name: str, prompt: str) -> ScenePlanPrompt:
        plan = ScenePlanPrompt(group_id=group_id, name=name, prompt=prompt)
        self.session.add(plan)
        await self.session.commit()
        await self.session.refresh(plan)
        return plan

    async def update_plan_prompt(self, plan_id: int, prompt: str) -> Optional[ScenePlanPrompt]:
        result = await self.session.execute(
            select(ScenePlanPrompt).where(ScenePlanPrompt.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        if plan:
            plan.prompt = prompt
            await self.session.commit()
            await self.session.refresh(plan)
        return plan

    async def delete_plan_prompt(self, plan_id: int):
        await self.session.execute(delete(ScenePlanPrompt).where(ScenePlanPrompt.id == plan_id))
        await self.session.commit()

    async def get_full_hierarchy(self) -> Dict[int, Dict]:
        groups = await self.get_all_groups()
        hierarchy = {}
        for group in groups:
            plans = await self.get_plans_by_group(group.id)
            hierarchy[group.id] = {
                "name": group.name,
                "plans": [{"id": p.id, "name": p.name, "prompt": p.prompt} for p in plans]
            }
        return hierarchy
    
    async def get_plans_by_group(self, group_id: int) -> List[ScenePlanPrompt]:
        """Bir gruppaga tegishli barcha planlarni olish"""
        result = await self.session.execute(
            select(ScenePlanPrompt)
            .where(ScenePlanPrompt.group_id == group_id)
            .where(ScenePlanPrompt.is_active == True)
            .order_by(ScenePlanPrompt.order_index)
        )
        return list(result.scalars().all())


    async def get_all_plans(self) -> List[ScenePlanPrompt]:
        result = await self.session.execute(
            select(ScenePlanPrompt)
            .where(ScenePlanPrompt.is_active == True)
            .order_by(ScenePlanPrompt.order_index)
        )
        all_plans = list(result.scalars().all())
        
        seen_names = {}
        for plan in all_plans:
            if plan.name not in seen_names:
                seen_names[plan.name] = plan
        
        unique_plans = list(seen_names.values())
        unique_plans.sort(key=lambda x: x.order_index)
        
        return unique_plans


    async def get_plan(self, plan_id: int) -> Optional[ScenePlanPrompt]:
        result = await self.session.execute(
            select(ScenePlanPrompt).where(ScenePlanPrompt.id == plan_id)
        )
        return result.scalar_one_or_none()
    
    async def get_plan_prompt(self, plan_id: int) -> Optional[str]:
        plan = await self.get_plan(plan_id)
        if plan:
            return plan.prompt
        return None


    async def get_prompts_by_group_and_plan(self, group_id: int, plan_id: int) -> List[ScenePlanPrompt]:
        plan = await self.get_plan(plan_id)
        if not plan:
            return []
        
        result = await self.session.execute(
            select(ScenePlanPrompt)
            .where(ScenePlanPrompt.group_id == group_id)
            .where(ScenePlanPrompt.name == plan.name)
            .where(ScenePlanPrompt.is_active == True)
            .order_by(ScenePlanPrompt.order_index)
        )
        return list(result.scalars().all())


class AdminLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def log_action(self, admin_id: int, action: str, details: Optional[str] = None):
        log = AdminLog(
            admin_id=admin_id,
            action=action,
            details=details
        )
        self.session.add(log)
        await self.session.commit()
    
    async def get_recent_logs(self, limit: int = 50) -> List[AdminLog]:
        result = await self.session.execute(
            select(AdminLog)
            .order_by(AdminLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())