from aiogram.fsm.state import State, StatesGroup


class ProductCardStates(StatesGroup):
    waiting_for_photo = State()
    selecting_scene_category = State()
    selecting_multiple_scenes = State()  
    selecting_multiple_categories = State()
    confirming = State()


class NormalizeStates(StatesGroup):
    waiting_for_photos = State()
    selecting_model_category = State()
    selecting_model_subcategory = State()
    selecting_model_item = State()
    confirming = State()


class VideoStates(StatesGroup):
    waiting_for_photo = State()
    selecting_scenario = State()
    entering_custom_prompt = State()
    confirming = State()


class PhotoStates(StatesGroup):
    waiting_for_photo = State()
    
    selecting_scene_category = State()
    selecting_scene_subcategory = State()
    selecting_scene_item = State()
    
    selecting_pose_group = State()
    selecting_pose_subgroup = State()
    selecting_pose_prompt = State()
    
    entering_custom_prompt = State()
    confirming = State()




class AdminModelCategoryStates(StatesGroup):
    entering_category_name = State()
    selecting_category = State()
    entering_subcategory_name = State()
    selecting_subcategory = State()
    entering_item_name = State()
    entering_item_prompt = State()
    editing_item_name = State()         #
    editing_item_prompt = State()


class AdminPoseStates(StatesGroup):
    entering_group_name = State()
    
    selecting_group = State()
    entering_subgroup_name = State()

    selecting_subgroup = State()
    entering_prompt_name = State()
    entering_prompt_text = State()
    
    editing_prompt_text = State()

class AdminVideoScenarioStates(StatesGroup):
    main = State()

    entering_name = State()
    entering_prompt = State()
    entering_order = State()

    selecting_scenario = State()
    editing_menu = State()
    editing_name = State()
    editing_prompt = State()
    editing_order = State()

    confirming_delete = State()


class AdminSceneCategoryStates(StatesGroup):
    entering_category_name = State()
    selecting_category = State()
    entering_subcategory_name = State()
    selecting_subcategory = State()
    entering_item_name = State()
    entering_item_prompt = State()
    editing_item_name = State()        
    editing_item_prompt = State()

class AdminMessageStates(StatesGroup):
    entering_text = State()
    uploading_media = State()

class AdminNormalizePromptStates(StatesGroup):
    choosing = State()
    entering_prompt1 = State()
    entering_prompt2 = State()


class AdminUserStates(StatesGroup):
    searching_user = State()
    adding_credits = State()