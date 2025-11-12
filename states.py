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
    selecting_subgroup = State()         
    selecting_plan = State()             
    selecting_prompt = State()           
    entering_custom_prompt = State()     
    confirming = State()                


class AdminModelTypeStates(StatesGroup):
    entering_name = State()
    entering_prompt = State()


class AdminPoseStates(StatesGroup):
    # Poza qo'shish
    selecting_group = State()        
    entering_group_id = State()        
    entering_group_name = State()      
    
    selecting_subgroup = State()       
    entering_subgroup_id = State()     
    entering_subgroup_name = State()   
    
    entering_prompt_name = State()     
    entering_prompt_text = State()    
    
    # O'chirish
    deleting_group = State()
    deleting_subgroup = State()
    deleting_prompt = State()
    
    # Tahrirlash
    editing_prompt = State()
    editing_prompt_text = State()


class AdminSceneStates(StatesGroup):
    entering_group_name = State()         
    entering_plan_prompt = State()          
    adding_default_plans = State()          


class AdminMessageStates(StatesGroup):
    entering_text = State()
    uploading_media = State()


class AdminUserStates(StatesGroup):
    searching_user = State()
    adding_credits = State()