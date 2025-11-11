from aiogram.fsm.state import State, StatesGroup


class ProductCardStates(StatesGroup):
    waiting_for_photo = State()
    selecting_scene = State()
    selecting_plan = State()  
    confirming = State()


class NormalizeStates(StatesGroup):
    waiting_for_photos = State()
    selecting_model_type = State()
    confirming = State()


class VideoStates(StatesGroup):
    waiting_for_photo = State()
    selecting_scenario = State()
    entering_custom_prompt = State()
    confirming = State()


class PhotoStates(StatesGroup):
    waiting_for_photo = State()
    selecting_group = State()
    selecting_scene = State()  
    selecting_pose = State()  
    selecting_plan = State()  
    selecting_element = State()  
    selecting_pose_element = State()  
    entering_custom_prompt = State()
    confirming = State()

from aiogram.fsm.state import State, StatesGroup


class AdminMessageStates(StatesGroup):
    entering_text = State()
    uploading_media = State()


class AdminPoseStates(StatesGroup):
    selecting_group = State()
    entering_pose_id = State()
    selecting_element_type = State()
    entering_element_name = State()
    entering_element_prompt = State()


class AdminSceneStates(StatesGroup):
    selecting_group = State()
    entering_scene_id = State()
    selecting_element_type = State()
    entering_element_name = State()
    entering_prompt_far = State()
    entering_prompt_medium = State()
    entering_prompt_close = State()
    entering_prompt_side = State()
    entering_prompt_back = State()
    entering_prompt_motion = State()


# YANGI: User management states
class AdminUserStates(StatesGroup):
    searching_user = State()
    viewing_user = State()
    adding_credits = State()