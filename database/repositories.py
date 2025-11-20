from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload
from database.models import (ModelCategory, ModelItem, ModelSubcategory, PaymentPackage, User, Task, Payment, UserState, TaskStatus, TaskType,
                             BotMessage, PoseGroup, PoseSubgroup, PosePrompt,
                             SceneCategory, SceneSubcategory, SceneItem,
                             AdminLog)
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
    
    async def admin_me(self, telegram_id: int) -> Optional[User]:
        result = await self.session.execute(
        select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.is_admin = True
            await self.session.commit()
            return user
        return None
    
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


from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_payment(
        self,
        user_id: int,
        payment_id: str,
        amount: float,
        credits: int,
        status: str = "pending",
    ) -> Payment:
        payment = Payment(
            user_id=user_id,
            payment_id=payment_id,
            amount=amount,
            credits=credits,
            status=status,
            created_at=datetime.utcnow(),
            completed_at=None,
        )
        self.session.add(payment)
        try:
            await self.session.commit()
            await self.session.refresh(payment)
            return payment
        except IntegrityError:
            await self.session.rollback()
            # payment_id unikal bo'lgani uchun mavjud yozuvni qaytaramiz
            existing = await self.get_payment_by_payment_id(payment_id)
            if existing:
                return existing
            # kutilmagan holat
            raise

    async def get_payment_by_payment_id(self, payment_id: str) -> Payment | None:
        result = await self.session.execute(
            select(Payment).where(Payment.payment_id == payment_id)
        )
        return result.scalar_one_or_none()

    async def update_payment_status(self, payment_id: str, status: str) -> Payment | None:
        payment = await self.get_payment_by_payment_id(payment_id)
        if not payment:
            return None

        payment.status = status
        terminal_statuses = {"succeeded", "cancelled", "canceled", "failed", "refunded"}
        if status in terminal_statuses and payment.completed_at is None:
            payment.completed_at = datetime.utcnow()

        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def list_user_payments(self, user_id: int, limit: int = 20, offset: int = 0) -> list[Payment]:
        result = await self.session.execute(
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

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


class ModelCategoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_categories(self) -> List[ModelCategory]:
        result = await self.session.execute(
            select(ModelCategory)
            .where(ModelCategory.is_active == True)
            .order_by(ModelCategory.order_index)
        )
        return list(result.scalars().all())

    async def get_category(self, category_id: int) -> Optional[ModelCategory]:
        result = await self.session.execute(
            select(ModelCategory).where(ModelCategory.id == category_id)
        )
        return result.scalar_one_or_none()

    async def add_category(self, name: str, order_index: int = 0) -> ModelCategory:
        category = ModelCategory(name=name, order_index=order_index)
        self.session.add(category)
        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def delete_category(self, category_id: int):
        await self.session.execute(
            delete(ModelCategory).where(ModelCategory.id == category_id)
        )
        await self.session.commit()

    async def get_subcategories_by_category(self, category_id: int) -> List[ModelSubcategory]:
        result = await self.session.execute(
            select(ModelSubcategory)
            .where(ModelSubcategory.category_id == category_id)
            .where(ModelSubcategory.is_active == True)
            .order_by(ModelSubcategory.order_index)
        )
        return list(result.scalars().all())

    async def get_subcategory(self, subcategory_id: int) -> Optional[ModelSubcategory]:
        result = await self.session.execute(
            select(ModelSubcategory).where(ModelSubcategory.id == subcategory_id)
        )
        return result.scalar_one_or_none()

    async def add_subcategory(self, category_id: int, name: str, order_index: int = 0) -> ModelSubcategory:
        subcategory = ModelSubcategory(
            category_id=category_id,
            name=name,
            order_index=order_index
        )
        self.session.add(subcategory)
        await self.session.commit()
        await self.session.refresh(subcategory)
        return subcategory

    async def delete_subcategory(self, subcategory_id: int):
        await self.session.execute(
            delete(ModelSubcategory).where(ModelSubcategory.id == subcategory_id)
        )
        await self.session.commit()

    async def get_items_by_subcategory(self, subcategory_id: int) -> List[ModelItem]:
        result = await self.session.execute(
            select(ModelItem)
            .where(ModelItem.subcategory_id == subcategory_id)
            .where(ModelItem.is_active == True)
            .order_by(ModelItem.order_index)
        )
        return list(result.scalars().all())

    async def get_item(self, item_id: int) -> Optional[ModelItem]:
        result = await self.session.execute(
            select(ModelItem).where(ModelItem.id == item_id)
        )
        return result.scalar_one_or_none()

    async def add_item(self, subcategory_id: int, name: str, prompt: str, order_index: int = 0) -> ModelItem:
        item = ModelItem(
            subcategory_id=subcategory_id,
            name=name,
            prompt=prompt,
            order_index=order_index
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def update_item(self, item_id: int, name: str, prompt: str) -> Optional[ModelItem]:
        result = await self.session.execute(
            select(ModelItem).where(ModelItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item:
            item.name = name
            item.prompt = prompt
            await self.session.commit()
            await self.session.refresh(item)
        return item

    async def delete_item(self, item_id: int):
        await self.session.execute(
            delete(ModelItem).where(ModelItem.id == item_id)
        )
        await self.session.commit()

    async def get_full_hierarchy(self) -> Dict:
        result = await self.session.execute(
            select(ModelCategory)
            .options(
                selectinload(ModelCategory.subcategories).selectinload(ModelSubcategory.items)
            )
            .where(ModelCategory.is_active == True)
            .order_by(ModelCategory.order_index)
        )
        categories = result.scalars().all()
        
        hierarchy = {}
        for category in categories:
            hierarchy[category.id] = {
                "name": category.name,
                "subcategories": {}
            }
            
            for subcategory in category.subcategories:
                if subcategory.is_active:
                    hierarchy[category.id]["subcategories"][subcategory.id] = {
                        "name": subcategory.name,
                        "items": [
                            {"id": item.id, "name": item.name, "prompt": item.prompt}
                            for item in subcategory.items if item.is_active
                        ]
                    }
        
        return hierarchy


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



class SceneCategoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_categories(self) -> List[SceneCategory]:
        result = await self.session.execute(
            select(SceneCategory)
            .where(SceneCategory.is_active == True)
            .order_by(SceneCategory.order_index)
        )
        return list(result.scalars().all())

    async def get_category(self, category_id: int) -> Optional[SceneCategory]:
        result = await self.session.execute(
            select(SceneCategory).where(SceneCategory.id == category_id)
        )
        return result.scalar_one_or_none()

    async def add_category(self, name: str, order_index: int = 0) -> SceneCategory:
        category = SceneCategory(name=name, order_index=order_index)
        self.session.add(category)
        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def delete_category(self, category_id: int):
        await self.session.execute(
            delete(SceneCategory).where(SceneCategory.id == category_id)
        )
        await self.session.commit()

    async def get_subcategories_by_category(self, category_id: int) -> List[SceneSubcategory]:
        result = await self.session.execute(
            select(SceneSubcategory)
            .where(SceneSubcategory.category_id == category_id)
            .where(SceneSubcategory.is_active == True)
            .order_by(SceneSubcategory.order_index)
        )
        return list(result.scalars().all())

    async def get_subcategory(self, subcategory_id: int) -> Optional[SceneSubcategory]:
        result = await self.session.execute(
            select(SceneSubcategory).where(SceneSubcategory.id == subcategory_id)
        )
        return result.scalar_one_or_none()

    async def add_subcategory(self, category_id: int, name: str, order_index: int = 0) -> SceneSubcategory:
        subcategory = SceneSubcategory(
            category_id=category_id,
            name=name,
            order_index=order_index
        )
        self.session.add(subcategory)
        await self.session.commit()
        await self.session.refresh(subcategory)
        return subcategory

    async def delete_subcategory(self, subcategory_id: int):
        await self.session.execute(
            delete(SceneSubcategory).where(SceneSubcategory.id == subcategory_id)
        )
        await self.session.commit()

    async def get_items_by_subcategory(self, subcategory_id: int) -> List[SceneItem]:
        result = await self.session.execute(
            select(SceneItem)
            .where(SceneItem.subcategory_id == subcategory_id)
            .where(SceneItem.is_active == True)
            .order_by(SceneItem.order_index)
        )
        return list(result.scalars().all())

    async def get_item(self, item_id: int) -> Optional[SceneItem]:
        result = await self.session.execute(
            select(SceneItem).where(SceneItem.id == item_id)
        )
        return result.scalar_one_or_none()

    async def add_item(self, subcategory_id: int, name: str, prompt: str, order_index: int = 0) -> SceneItem:
        item = SceneItem(
            subcategory_id=subcategory_id,
            name=name,
            prompt=prompt,
            order_index=order_index
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def update_item(self, item_id: int, name: str, prompt: str) -> Optional[SceneItem]:
        result = await self.session.execute(
            select(SceneItem).where(SceneItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item:
            item.name = name
            item.prompt = prompt
            await self.session.commit()
            await self.session.refresh(item)
        return item

    async def delete_item(self, item_id: int):
        await self.session.execute(
            delete(SceneItem).where(SceneItem.id == item_id)
        )
        await self.session.commit()

    async def get_full_hierarchy(self) -> Dict:
        result = await self.session.execute(
            select(SceneCategory)
            .options(
                selectinload(SceneCategory.subcategories).selectinload(SceneSubcategory.items)
            )
            .where(SceneCategory.is_active == True)
            .order_by(SceneCategory.order_index)
        )
        categories = result.scalars().all()
        
        hierarchy = {}
        for category in categories:
            hierarchy[category.id] = {
                "name": category.name,
                "subcategories": {}
            }
            
            for subcategory in category.subcategories:
                if subcategory.is_active:
                    hierarchy[category.id]["subcategories"][subcategory.id] = {
                        "name": subcategory.name,
                        "items": [
                            {"id": item.id, "name": item.name, "prompt": item.prompt}
                            for item in subcategory.items if item.is_active
                        ]
                    }
        
        return hierarchy


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
    


    from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from database.models import VideoScenario

class VideoScenarioRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> List[VideoScenario]:
        result = await self.session.execute(
            select(VideoScenario)
            .where(VideoScenario.is_active == True)
            .order_by(VideoScenario.order_index, VideoScenario.id)
        )
        return list(result.scalars().all())

    async def get_by_id(self, scenario_id: int) -> Optional[VideoScenario]:
        result = await self.session.execute(
            select(VideoScenario).where(VideoScenario.id == scenario_id)
        )
        return result.scalar_one_or_none()

    async def add(self, name: str, prompt: str, order_index: int = 0, is_active: bool = True) -> VideoScenario:
        scenario = VideoScenario(
            name=name,
            prompt=prompt,
            order_index=order_index,
            is_active=is_active
        )
        self.session.add(scenario)
        await self.session.commit()
        await self.session.refresh(scenario)
        return scenario

    async def update(self, scenario_id: int, name: Optional[str] = None, prompt: Optional[str] = None,
                     order_index: Optional[int] = None, is_active: Optional[bool] = None) -> Optional[VideoScenario]:
        scenario = await self.get_by_id(scenario_id)
        if not scenario:
            return None
        if name is not None:
            scenario.name = name
        if prompt is not None:
            scenario.prompt = prompt
        if order_index is not None:
            scenario.order_index = order_index
        if is_active is not None:
            scenario.is_active = is_active
        await self.session.commit()
        await self.session.refresh(scenario)
        return scenario

    async def delete(self, scenario_id: int) -> None:
        await self.session.execute(delete(VideoScenario).where(VideoScenario.id == scenario_id))
        await self.session.commit()


class PaymentPackageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_all_packages(self, only_active: bool = True) -> List[PaymentPackage]:
        """Barcha paketlarni olish"""
        query = select(PaymentPackage).order_by(PaymentPackage.order_index)
        if only_active:
            query = query.where(PaymentPackage.is_active == True)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_package_by_id(self, package_id: int) -> Optional[PaymentPackage]:
        """ID bo'yicha paket olish"""
        result = await self.session.execute(
            select(PaymentPackage).where(PaymentPackage.id == package_id)
        )
        return result.scalar_one_or_none()
    
    async def add_package(self, label: str, credits: int, price: float, 
                         bonus: Optional[str] = None, order_index: int = 0) -> PaymentPackage:
        package = PaymentPackage(
            label=label,
            credits=credits,
            price=price,
            bonus=bonus,
            order_index=order_index
        )
        self.session.add(package)
        await self.session.commit()
        await self.session.refresh(package)
        return package
    
    async def update_package(self, package_id: int, label: Optional[str] = None,
                           credits: Optional[int] = None, price: Optional[float] = None,
                           bonus: Optional[str] = None, order_index: Optional[int] = None,
                           is_active: Optional[bool] = None) -> Optional[PaymentPackage]:
        package = await self.get_package_by_id(package_id)
        if not package:
            return None
        
        if label is not None:
            package.label = label
        if credits is not None:
            package.credits = credits
        if price is not None:
            package.price = price
        if bonus is not None:
            package.bonus = bonus
        if order_index is not None:
            package.order_index = order_index
        if is_active is not None:
            package.is_active = is_active
        
        await self.session.commit()
        await self.session.refresh(package)
        return package
    
    async def delete_package(self, package_id: int) -> bool:
        await self.session.execute(
            delete(PaymentPackage).where(PaymentPackage.id == package_id)
        )
        await self.session.commit()
        return True
    
    async def toggle_active(self, package_id: int) -> Optional[PaymentPackage]:
        package = await self.get_package_by_id(package_id)
        if package:
            package.is_active = not package.is_active
            await self.session.commit()
            await self.session.refresh(package)
        return package


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
    
    async def admin_me(self, telegram_id: int) -> Optional[User]:
        result = await self.session.execute(
        select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.is_admin = True
            await self.session.commit()
            return user
        return None
    
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