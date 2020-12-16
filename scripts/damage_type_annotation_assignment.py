import os
import sys
import glob
import json
import shutil
import copy
import random
    
DATA_POOL = "/data-non-pii-share/rd_ai/mohan/rd_data_tool_data_preparation/outputs/damage_type_annotation"

user_list = [
    "mohan",
    "steven",
    "ann",
    "bahar",
    "prajakta",
    "hao",
    "amir",
    "sheida",
    "zia",
    "neda",
    "shanduojiao",
    "brian",
    "jiachen",
    "ashish"
]

class TODAnnotationPreparation():
    def __init__(self, **kwargs):
        self.app_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        self.tool_input_path = os.path.join(self.app_path, "input", "damage_type_annotation")
        self.data_pool = kwargs.get("data_pool", DATA_POOL)
        
        # prepare user folder
        self.users = kwargs.get("users", self.get_user_list())
        self.initial_folders(force_=kwargs.get("force_", False))
        
        # load data
        self.load_data()
        self.assign_data()
        
    def get_user_list(self):
        with open(os.path.join(self.app_path, "user_info.json"), "r") as f:
            users = list(json.load(f).keys())
        return users
    
    def initial_folders(self, force_):
        user_paths = {}
        
        for u in self.users:
            user_path = os.path.join(self.tool_input_path, u)
              
            if force_:
                shutil.rmtree(user_path)
                
            if not os.path.exists(user_path):
                os.makedirs(user_path)

            user_paths[u] = user_path

        self.user_paths = user_paths
        
    def load_data(self):
        self.data_list = [
            v for v in glob.glob(os.path.join(self.data_pool, "*"))
        ]
        
    def _remove_records(self):
        for u in self.users:
            record_ = os.path.join(self.tool_input_path, "record_{}".format(u))
            if os.path.exists(record_):
                os.remove(record_)
                
    def assign_data(self):
        data_list = copy.deepcopy(self.data_list)
        random.shuffle(data_list)
        
        user_list = copy.deepcopy(self.users)
        
        while len(data_list) > 0:
            if len(user_list) == 0:
                user_list = copy.deepcopy(self.users)
            
            data_ = data_list.pop(0)
            user_ = user_list.pop(0)
            
            print("{}\n...to...\n{}\n{}".format(data_, self.user_paths[user_], "="*50))
            shutil.copy(data_, self.user_paths[user_])
            
        
    
if __name__ == "__main__":
    t = TODAnnotationPreparation(users=user_list)
