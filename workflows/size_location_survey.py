import csv
import json
import os
import shutil
import glob
import numpy as np

from flask import render_template, url_for, request, redirect, Blueprint, session
from flask_login import login_required, current_user

from PIL import Image, ImageFont, ImageDraw, ImageEnhance
import cv2
import base64

from libs.utils import next_dirs, pop_workflow_session_keys, app_dir, to_base64, touch, remove_if_exists
from libs.size_n_location_butterfly import get_butterfly_plot

tool_name = "size_location_survey"
local_bp = Blueprint(tool_name, __name__)

output_dir = os.path.join(app_dir, "output", tool_name)
input_dir = os.path.join(app_dir, "input", tool_name)

panel_list = [
    'front_bumper',         
    'hood',                 
    'left_fender',          
    'right_fender',         
    'rear_bumper',          
    'trunk_lid',            
    'left_quarter',         
    'right_quarter',        
    'left_front_door',      
    'left_rear_door',       
    'right_front_door',     
    'right_rear_door',      
    'left_headlight',       
    'left_taillight',       
    'right_headlight',      
    'right_taillight',      
    'front_windshield',     
    'rear_windshield',      
    'roof',                 
    'pillar',               
    'other',                
    'left_front_wheel',     
    'left_rear_wheel',      
    'right_front_wheel',    
    'right_rear_wheel',     
    'left_front_window',    
    'left_rear_window',     
    'left_other_window',    
    'right_front_window',   
    'right_rear_window',    
    'right_other_window',   
    'grille',               
    'left_rocker_panel',    
    'right_rocker_panel',   
    'left_wing_mirror',     
    'right_wing_mirror',    
    'bottom',               
    'lower_grille',         
    'camper_shell',         
    'left_aperture_panel',  
    'right_aperture_panel'
]
loc_list = [
    "All",
    "Upper Left", 
    "Upper Center",
    "Upper Right",
    "Center Left",
    "Center",
    "Center Right",
    "Lower Left",
    "Lower Center",
    "Lower Right"
]
TAG_LIST = [
    'front', 'rear', 'left', 'right', 
    'left_front', 'right_front', 'left_rear', 'right_rear',
    'zoom', 'very_zoom',

]

def process_siz_n_loc_output(entry_):
    # claim level butterfly plots
    r_c = entry_["claim_level"]["damage_location"]

    bflyinps = np.load(os.path.join(app_dir, "libs/BFcontours.npy"), allow_pickle=True)
    (PANEL_NAMES, PANEL_COLORS) = np.load(os.path.join(app_dir, "libs/PANELS.npy"), allow_pickle=True)

    r_c, butterfly_ = get_butterfly_plot(bflyinps, r_c, PANEL_NAMES, num_grid=3)
    # butterfly_ = cv2.imread(os.path.join(app_dir, "examples/butterfly.png"))
    butterfly_bytes = base64.b64encode(cv2.imencode('.jpg', butterfly_)[1]).decode()

    # image level info
    raw_image_list = []
    claim_size_pred_list = []
    claim_loc_pred_list = []

    size_example_count = 0
    loc_example_count = 0

    for ci, (image_name, image_info) in enumerate(entry_.items()):
        if image_name == "claim_level":
            continue

        file_ = image_info["image_path"]
        # <<< !!! LOCAL INFO
        # file_ = "/Users/mohanliu/Desktop/temp_images/{}".format(os.path.basename(image_info["image_path"]))
        # file_ = os.path.join(app_dir, "examples/placeholder.png")
        # >>>


        # apply tagnet filter (remove images with invalid tags)
        image_tag = image_info["output"]["image_tag"]

        if image_tag not in TAG_LIST:
            continue

        # load raw image
        raw_dmg_ = cv2.imread(file_)

        #== prepare damage size information ==#
        dmgsites = image_info["output"].get("damage_sites", {})

        if dmgsites == {}:
            #== prepare damage location information ==#
            # create damage mask to help damage location identification
            claim_loc_pred_temp_dict = {
                "image_id": loc_example_count,
                "image_name": image_name,
                "image_tag": image_tag, 
                "raw_image_bytes": base64.b64encode(cv2.imencode('.jpg', raw_dmg_)[1]).decode(),
                "damage_image_bytes": base64.b64encode(cv2.imencode('.jpg', raw_dmg_)[1]).decode(),
                "damage_flag": False,
            }

            claim_loc_pred_list.append(claim_loc_pred_temp_dict)
            
            loc_example_count += 1 

        else:
            # add bounding boxes
            pred_list = []
            bbox_list = []

            for i, (site_id, site_info) in enumerate(dmgsites.items()):
                image_ = raw_dmg_.copy()

                # get bbox info (1. for size survey; 2. for loc survey)
                bbox = site_info["bbox"]
                bbox_list.append(bbox)

                # skip image with bbox when no dimension predicted
                if site_info["lxw"] == ["N/A"]:
                    continue

                # draw bounding box on images
                x1, y1, x2, y2 = bbox
                image_temp = cv2.rectangle(image_, (x1, y1), (x2, y2), (255, 155, 100), 3)

                # draw reference arrow in image
                ref_x1, ref_y1, ref_x2, ref_y2 = image_info["vals"][3][0]

                start_1 = (ref_x1 + int((ref_x2 - ref_x1)/2), ref_y1 + int((ref_y2 - ref_y1)/2))
                end_1 = (ref_x1, ref_y1)

                start_2 = (ref_x1 + int((ref_x2 - ref_x1)/2), int(ref_y1 + (ref_y2 - ref_y1)/2))
                end_2 = (ref_x2, ref_y2)

                image_temp = cv2.arrowedLine(image_temp, start_1, end_1, (0, 0, 255), 5)
                image_temp = cv2.arrowedLine(image_temp, start_2, end_2, (0, 0, 255), 5)


                # put text for reference
                image_temp = cv2.putText(
                    image_temp, 
                    "{:.2f} cm".format(image_info["vals"][4][0]),
                    (ref_x1 + int((ref_x2 - ref_x1)/2), ref_y1 + int((ref_y2 - ref_y1)/2)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0, (0, 0, 255), 2, cv2.LINE_AA
                )

                # convert processed image to bytes
                image_temp_bytes = base64.b64encode(cv2.imencode('.jpg', image_temp)[1]).decode()

                # get predictions for size 
                if y2 - y1 > x2 - x1:
                    x_dim = site_info["lxw"][1]
                    y_dim = site_info["lxw"][0]
                else:
                    x_dim = site_info["lxw"][0]
                    y_dim = site_info["lxw"][1]

                # prepare image level output
                temp_dict = {
                    "id": site_id.split("_")[1],
                    "image_bytes": image_temp_bytes,
                    "x_dim": x_dim,
                    "y_dim": y_dim
                }
                pred_list.append(temp_dict)

            #== prepare damage location information ==#
            # create damage mask to help damage location identification
            damage_mask = raw_dmg_.copy()

            for bbox in bbox_list:
                x1, y1, x2, y2 = bbox
                damage_mask_temp = cv2.rectangle(damage_mask, (x1, y1), (x2, y2), (255, 155, 100), -1)

            damage_mask_bytes = base64.b64encode(cv2.imencode('.jpg', damage_mask_temp)[1]).decode()

            # prepare final claim level prediction information
            # prepare location survey dict 
            claim_loc_pred_temp_dict = {
                "image_id": loc_example_count,
                "image_name": image_name,
                "image_tag": image_tag, 
                "raw_image_bytes": base64.b64encode(cv2.imencode('.jpg', raw_dmg_)[1]).decode(),
                "damage_image_bytes": damage_mask_bytes,
                "damage_flag": True,
            }
            claim_loc_pred_list.append(claim_loc_pred_temp_dict)
            loc_example_count += 1

            # prepare location survey dict 
            if len(pred_list) > 0:
                claim_pred_temp_dict = {
                    "image_id": size_example_count,
                    "image_name": image_name,
                    "image_tag": image_tag, 
                    "damage_list": pred_list
                }
                claim_size_pred_list.append(claim_pred_temp_dict)
                size_example_count += 1

    return (
        claim_size_pred_list, 
        claim_loc_pred_list,
        butterfly_bytes,
    )

@local_bp.route('/', methods=['GET'])
@login_required
def main():
    # load data to be surveyed
    survey_folder = os.path.join(input_dir, "{}".format(current_user.id))

    if not os.path.exists(survey_folder):
        messages = "Nothing prepared for you. Ask admin for more info."
        return render_template(
            "info.html",
            messages=messages,
        )
    
    survey_pool = glob.glob(os.path.join(survey_folder, "*"))

    if len(survey_pool) == 0:
        messages = "You have done your task. Ask admin for more info."
        return render_template(
            "info.html",
            messages=messages,
        )
    else:
        survey_file = survey_pool[0]


    with open(survey_file, "r") as f:
        raw_data = json.load(f)

    # list of images
    claims_list = [v for v in raw_data.keys()]
    total_claims_present = len(claims_list)

    # a file to keep a record of the process
    record_file = os.path.join(input_dir, 'record_{}'.format(current_user.id))

    # current working image
    session['claim_index'] = get_current_index(record_file)
    progress = int((session['claim_index'] + 1) / total_claims_present * 100) 

    # exit if all images are processed
    if session['claim_index'] == len(claims_list):
        touch(os.path.join(input_dir, 'completed_by_{}'.format(current_user.id)))
        remove_if_exists(survey_file)
        remove_if_exists(record_file)
        messages = "Thank you for completing this round of survey. Go to homepage and re-enter for next round."
        return render_template(
            "info.html",
            messages=messages,
        )

    else:
        remove_if_exists(os.path.join(input_dir, 'completed_by_{}'.format(current_user.id)))

    session['claim_name'] = claims_list[session['claim_index']]

    claim_size_preds, claim_loc_preds, butterfly_bytes = process_siz_n_loc_output(raw_data[session['claim_name']])


    backtracking_file = os.path.join(output_dir, "backtracking_{}.json".format(current_user.id))

    if os.path.exists(backtracking_file):
        with open(backtracking_file, "r") as f:
            saved_data = json.load(f)
    else:
        saved_data = {
            "selected_buttons": [],
            "previous_comments": []
        }

    return render_template(
        "{}.html".format(tool_name), 
        butterfly_bytes=butterfly_bytes,
        claim_predictions=claim_size_preds,
        claim_damage_images=claim_loc_preds,
        image_number=len(claim_size_preds),
        claim_name=session['claim_name'], 
        index=session['claim_index'],
        total_claims_present=total_claims_present,
        progress=progress,
        panel_list=panel_list,
        loc_list=loc_list,
        saved_data=saved_data,
    )

@local_bp.route('/', methods=['POST'])
@login_required
def process():
    # file to keep the record
    record_file = os.path.join(input_dir, 'record_{}'.format(current_user.id))

    # output file
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    output_file = os.path.join(output_dir, "survey_results_{}.json".format(current_user.id))
    backtracking_file = os.path.join(output_dir, "backtracking_{}.json".format(current_user.id))

    # cases once we want to go back one example
    if request.form['submit'] == 'back' and session['claim_index'] != 0:
        update_current_index(record_file, session['claim_index'] - 1)
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                data = json.load(f)
            last_raw_data = data.pop(-1)

            with open(output_file, 'w+') as f:
                json.dump(data, f, indent=4)

            with open(backtracking_file, "w") as f:
                json.dump(process_last_data(last_raw_data), f, indent=4)

        return redirect(url_for('{}.main'.format(tool_name)))

    # cases when image is not relevant
    elif request.form['submit'] == 'skip':
        dmgsizeeval_comments = []
        img_id = 0
        while request.form.get("dmgsize_comment{}".format(img_id)) is not None:
            dmgsizeeval_comments.append(request.form.get("dmgsize_comment{}".format(img_id)))
            img_id += 1

        output = {
            "claim_id": session['claim_name'], 
            "relevant": False,
            "damage_size_comments": dmgsizeeval_comments,
            "damage_location_comments": request.form.get("dmgloc_comment", "")
        }
        remove_if_exists(backtracking_file)

    # cases when we have outputs
    else:
        dmgsizeeval_comments = []
        img_id = 0
        while request.form.get("dmgsize_comment{}".format(img_id)) is not None:
            dmgsizeeval_comments.append(request.form.get("dmgsize_comment{}".format(img_id)))
            img_id += 1

        dmgsizeeval_likert = []

        img_id = 0
        while request.form.get("dmgsizeeval-image{}-damage{}".format(img_id, 0)) is not None:
            dmg_id = 0
            while request.form.get("dmgsizeeval-image{}-damage{}".format(img_id, dmg_id)) is not None:
                dmgsizeeval_likert.append(request.form.get("dmgsizeeval-image{}-damage{}".format(img_id, dmg_id)))
                dmg_id += 1
            img_id += 1

        output = {
            "claim_id": session['claim_name'],
            "relevant": True, 
            "damage_size_evaluation": dmgsizeeval_likert,
            "damage_location_evaluation": request.form.get("dmgloc_eval"),
            "damage_location_mislabel_panels": request.form.getlist("mislabelpanel"),
            "damage_location_mislabel_grids": request.form.getlist("mislabelloc"),
            "damage_location_falselabel_panels": request.form.getlist("falslabelpanel"),
            "damage_location_falselabel_grids": request.form.getlist("falslabelloc"),
            "damage_size_comments": dmgsizeeval_comments,
            "damage_location_comments": request.form.get("dmgloc_comment", "")
        }


    # write output
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            data = json.load(f)
    else:
        data = []

    data.append(output)
    with open(output_file, 'w+') as f:
        json.dump(data, f, indent=4)

    session['claim_index'] += 1
    update_current_index(record_file, session['claim_index'])
    remove_if_exists(backtracking_file)

    return redirect(url_for('{}.main'.format(tool_name)))

def process_last_data(input_dict):
    output_dict = {}

    selected_buttons = []
    for item in input_dict.get("damage_size_evaluation", []):
        _, image_id, dmg_id, likert_scale = item.split("-")
        selected_buttons.append("dmgsizeeval{}_{}_{}".format(
            image_id.replace("image", ""),
            dmg_id.replace("damage", ""),
            likert_scale
        ))

    selected_buttons.append("dmgloc_eval_{}".format(input_dict.get("damage_location_evaluation", "")))

    output_dict["selected_buttons"] = selected_buttons

    prev_comments = []

    for i, v in enumerate(input_dict["damage_size_comments"]):
        tmp_ = {
            "id": "dmgsize_comment{}".format(i),
            "comments": v
        }
        prev_comments.append(tmp_)

    prev_comments.append({
        "id": "dmgloc_comment",
        "comments": input_dict["damage_location_comments"]
    })

    output_dict["previous_comments"] = prev_comments

    return output_dict

def get_current_index(record_file_dir):
    if os.path.isfile(record_file_dir):
        fd = open(record_file_dir, 'r')
        reader = csv.reader(fd)
        row1 = next(reader)[0].split()
        fd.close()
        return int(row1[0])
    else:
        fd = open(record_file_dir, 'a+')
        content = str(0)
        fd.write(content)
        fd.close()
        return 0


def update_current_index(record_file_dir, image_index):
    content = str(image_index)
    fd = open(record_file_dir, 'w')
    fd.write(content)
    fd.close()
