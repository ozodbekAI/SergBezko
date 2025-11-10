from datetime import datetime
from sqlalchemy import BigInteger, String, Integer, DateTime, Text, Boolean, Float, Enum as SQLEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from typing import Optional
import enum


class Base(DeclarativeBase):
    pass


class TaskStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(enum.Enum):
    PRODUCT_CARD = "product_card"
    NORMALIZE_OWN_MODEL = "normalize_own_model"
    NORMALIZE_NEW_MODEL = "normalize_new_model"
    VIDEO_BALANCE = "video_balance"
    VIDEO_PRO_6 = "video_pro_6"
    VIDEO_PRO_10 = "video_pro_10"
    VIDEO_SUPER_6 = "video_super_6"
    PHOTO_SCENE = "photo_scene"
    PHOTO_POSE = "photo_pose"
    PHOTO_CUSTOM = "photo_custom"


class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)  # YANGI: Ban field
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Task(Base):
    __tablename__ = "tasks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    task_type: Mapped[TaskType] = mapped_column(SQLEnum(TaskType))
    status: Mapped[TaskStatus] = mapped_column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    cost: Mapped[int] = mapped_column(Integer)
    input_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Payment(Base):
    __tablename__ = "payments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    payment_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    amount: Mapped[float] = mapped_column(Float)
    credits: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class UserState(Base):
    __tablename__ = "user_states"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# YANGI: Bot xabarlari uchun model
class BotMessage(Base):
    __tablename__ = "bot_messages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)  # start, product_card, normalize, video, photo
    text: Mapped[str] = mapped_column(Text)
    media_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # photo, video, none
    media_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# YANGI: Poses elementlari
class PoseElement(Base):
    __tablename__ = "pose_elements"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pose_id: Mapped[str] = mapped_column(String(100), index=True)  # jumping, standing_straight
    element_type: Mapped[str] = mapped_column(String(50))  # action, mood, style
    name: Mapped[str] = mapped_column(String(255))  # "Прыжок в воздухе"
    prompt: Mapped[str] = mapped_column(String(500))  # "jumping in air"
    group: Mapped[str] = mapped_column(String(100))  # dynamic, standing
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# YANGI: Scene elementlari
class SceneElement(Base):
    __tablename__ = "scene_elements"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scene_id: Mapped[str] = mapped_column(String(100), index=True)
    element_type: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    prompt_far: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_medium: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_close: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_side: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_back: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_motion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    group: Mapped[str] = mapped_column(String(100))  
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# YANGI: Admin logs
class AdminLog(Base):
    __tablename__ = "admin_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(100)) 
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)