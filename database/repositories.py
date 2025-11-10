from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from database.models import (User, Task, Payment, UserState, TaskStatus, TaskType,
                             BotMessage, PoseElement, SceneElement, AdminLog)
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import json


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
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.username == username)
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
    
    async def get_balance(self, telegram_id: int) -> int:
        user = await self.get_user_by_telegram_id(telegram_id)
        return user.balance if user else 0
    
    async def get_total_users(self) -> int:
        result = await self.session.execute(select(func.count(User.id)))
        return result.scalar()
    
    async def get_total_active_users(self, days: int = 30) -> int:
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await self.session.execute(
            select(func.count(User.id)).where(User.last_activity >= cutoff)
        )
        return result.scalar()
    
    async def get_total_balance(self) -> int:
        result = await self.session.execute(select(func.sum(User.balance)))
        return result.scalar() or 0

    async def check_balance(self, telegram_id: int, required: int) -> bool:
        user = await self.get_user_by_telegram_id(telegram_id)
        return user and user.balance >= required


class TaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_task(self, user_id: int, task_type: TaskType, cost: int, input_data: dict) -> Task:
        task = Task(
            user_id=user_id,
            task_type=task_type,
            cost=cost,
            input_data=json.dumps(input_data),
            status=TaskStatus.PENDING
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task
    
    async def update_task_status(self, task_id: int, status: TaskStatus, 
                                  result_data: Optional[dict] = None,
                                  error_message: Optional[str] = None) -> Optional[Task]:
        result = await self.session.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if task:
            task.status = status
            if result_data:
                task.result_data = json.dumps(result_data)
            if error_message:
                task.error_message = error_message
            if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                task.completed_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(task)
        
        return task
    
    async def get_user_tasks(self, user_id: int, limit: int = 10) -> List[Task]:
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
    
    async def cleanup_old_tasks(self, hours: int = 24):
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        await self.session.execute(
            delete(Task).where(Task.created_at < cutoff_time)
        )
        await self.session.commit()


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_payment(self, user_id: int, payment_id: str, 
                            amount: float, credits: int) -> Payment:
        payment = Payment(
            user_id=user_id,
            payment_id=payment_id,
            amount=amount,
            credits=credits,
            status="pending"
        )
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment
    
    async def get_payment(self, payment_id: str) -> Optional[Payment]:
        result = await self.session.execute(
            select(Payment).where(Payment.payment_id == payment_id)
        )
        return result.scalar_one_or_none()
    
    async def update_payment_status(self, payment_id: str, status: str) -> Optional[Payment]:
        payment = await self.get_payment(payment_id)
        if payment:
            payment.status = status
            if status == "succeeded":
                payment.completed_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(payment)
        return payment
    
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


class StateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def set_state(self, user_id: int, state: str, state_data: Optional[dict] = None):
        result = await self.session.execute(
            select(UserState).where(UserState.user_id == user_id)
        )
        user_state = result.scalar_one_or_none()
        
        if user_state:
            user_state.state = state
            user_state.state_data = json.dumps(state_data) if state_data else None
            user_state.updated_at = datetime.utcnow()
        else:
            user_state = UserState(
                user_id=user_id,
                state=state,
                state_data=json.dumps(state_data) if state_data else None
            )
            self.session.add(user_state)
        
        await self.session.commit()
    
    async def get_state(self, user_id: int) -> Optional[tuple[str, Optional[dict]]]:
        result = await self.session.execute(
            select(UserState).where(UserState.user_id == user_id)
        )
        user_state = result.scalar_one_or_none()
        
        if user_state and user_state.state:
            state_data = json.loads(user_state.state_data) if user_state.state_data else None
            return user_state.state, state_data
        return None
    
    async def clear_state(self, user_id: int):
        await self.session.execute(
            delete(UserState).where(UserState.user_id == user_id)
        )
        await self.session.commit()

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
    
    async def get_all_messages(self) -> List[BotMessage]:
        result = await self.session.execute(select(BotMessage))
        return list(result.scalars().all())


class PoseElementRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_elements_by_pose(self, pose_id: str) -> List[PoseElement]:
        result = await self.session.execute(
            select(PoseElement)
            .where(PoseElement.pose_id == pose_id, PoseElement.is_active == True)
            .order_by(PoseElement.order_index)
        )
        return list(result.scalars().all())
    
    async def get_all_poses(self) -> Dict[str, List[PoseElement]]:
        result = await self.session.execute(
            select(PoseElement)
            .where(PoseElement.is_active == True)
            .order_by(PoseElement.pose_id, PoseElement.order_index)
        )
        elements = result.scalars().all()
        
        poses = {}
        for elem in elements:
            if elem.pose_id not in poses:
                poses[elem.pose_id] = []
            poses[elem.pose_id].append(elem)
        return poses
    
    async def add_element(self, pose_id: str, element_type: str, name: str, 
                         prompt: str, group: str, order_index: int = 0) -> PoseElement:
        elem = PoseElement(
            pose_id=pose_id,
            element_type=element_type,
            name=name,
            prompt=prompt,
            group=group,
            order_index=order_index
        )
        self.session.add(elem)
        await self.session.commit()
        await self.session.refresh(elem)
        return elem
    
    async def delete_element(self, element_id: int):
        await self.session.execute(
            delete(PoseElement).where(PoseElement.id == element_id)
        )
        await self.session.commit()


class SceneElementRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_elements_by_scene(self, scene_id: str) -> List[SceneElement]:
        result = await self.session.execute(
            select(SceneElement)
            .where(SceneElement.scene_id == scene_id, SceneElement.is_active == True)
            .order_by(SceneElement.order_index)
        )
        return list(result.scalars().all())
    
    async def get_all_scenes(self) -> Dict[str, List[SceneElement]]:
        result = await self.session.execute(
            select(SceneElement)
            .where(SceneElement.is_active == True)
            .order_by(SceneElement.scene_id, SceneElement.order_index)
        )
        elements = result.scalars().all()
        
        scenes = {}
        for elem in elements:
            if elem.scene_id not in scenes:
                scenes[elem.scene_id] = []
            scenes[elem.scene_id].append(elem)
        return scenes
        
    async def add_element(self, scene_id: str, element_type: str, name: str,
                          prompt_far: str, prompt_medium: str, prompt_close: str,
                          group: str, prompt_side: str = "", prompt_back: str = "", prompt_motion: str = "",
                          order_index: int = 0) -> SceneElement:  # YANGI: parametrlar qo'shildi
        elem = SceneElement(
            scene_id=scene_id,
            element_type=element_type,
            name=name,
            prompt_far=prompt_far,
            prompt_medium=prompt_medium,
            prompt_close=prompt_close,
            prompt_side=prompt_side,
            prompt_back=prompt_back,
            prompt_motion=prompt_motion,
            group=group,
            order_index=order_index
        )
        self.session.add(elem)
        await self.session.commit()
        await self.session.refresh(elem)
        return elem
    
    async def delete_element(self, element_id: int):
        await self.session.execute(
            delete(SceneElement).where(SceneElement.id == element_id)
        )
        await self.session.commit()


# YANGI: Admin loglar uchun repository
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