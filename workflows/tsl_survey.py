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

tool_name = "tsl_survey"
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
DMG_TYPE_OPTIONS = [
    "dent", "scratch", "tear",
    "crack", "misalignment"
]
claim_damage_sites_aggregation_evals = [
    "Correct", "Partial", "Incorrect", "Unknown"
]


def _process_reference_arrow(input_vals=[], image_dimension=[]):
    if input_vals is None:
        return []

    if len(input_vals[0]) == 0:
        return []

    # pre selected panels for display
    _selected_panels = [
        'left_front_wheel',     
        'left_rear_wheel',      
        'right_front_wheel',    
        'right_rear_wheel',
        'left_headlight',       
        'right_headlight', 
    ]
    
    # variables
    _panel_names = input_vals[0]
    _long_axis_coords = [v[-1] for v in input_vals[3]]
    _panel_lenghts = input_vals[4]
    
    # output initialization
    output_list = []
    
    # get coords for selected panels
    for p, c, l in zip(_panel_names, _long_axis_coords, _panel_lenghts):
        if p not in _selected_panels:
            continue
        
        ref_x1, ref_y1, ref_x2, ref_y2 = [int(_) for _ in c]
        center_0 = (ref_x1 + int((ref_x2 - ref_x1)/2), ref_y1 + int((ref_y2 - ref_y1)/2))
        end_1 = (ref_x1, ref_y1)
        end_2 = (ref_x2, ref_y2)
        
        if center_0[0] > image_dimension[0] or center_0[1] > image_dimension[1]:
            continue
        
        output_list.append(
            [center_0, end_1, end_2, l]
        )
        
    # if none of the vals satisfied the preselection, get the longest arrow
    if output_list == []:
        _longest_index = np.argmax(_panel_lenghts)
        ref_x1, ref_y1, ref_x2, ref_y2 = [int(_) for _ in _long_axis_coords[_longest_index]]
        center_0 = (ref_x1 + int((ref_x2 - ref_x1)/2), ref_y1 + int((ref_y2 - ref_y1)/2))
        end_1 = (ref_x1, ref_y1)
        end_2 = (ref_x2, ref_y2)
        output_list.append(
            [center_0, end_1, end_2, _panel_lenghts[_longest_index]]
        )
        
    return output_list

def _collect_claim_damage_size_info(claim_size_dict_={}, image_mapping={}):
    output_list_ = []

    for site_id, site_info in claim_size_dict_.items():
        x1, y1, x2, y2 = site_info["bbox"]

        if site_info["lxw"] == ["N/A", "N/A"] or site_info["lxw"] == "unknown":
            x_dim = "N.A."
            y_dim = "N.A."
        elif y2 - y1 > x2 - x1:
            x_dim = site_info["lxw"][1]
            y_dim = site_info["lxw"][0]
        else:
            x_dim = site_info["lxw"][0]
            y_dim = site_info["lxw"][1]

        panel_list = list(site_info["panels"].keys())

        if panel_list == []:
            panel_list = ["No Panel Detected"]

        if site_info["damage_types"] == "unknown":
            type_list = ["Unknown Type"]
        else:
            type_list = site_info["damage_types"].get("predicted_damage_types", [])
            if type_list == []:
                type_list = ["No Type Detected"]


        origins = site_info.get("origin", [])
        image_name = origins[0]
        site_id_original = origins[1].strip().split("_")[-1]

        output_list_.append({
            "site_id": int(site_id.replace("site_", "")),
            "site_x": x_dim,
            "site_y": y_dim,
            "site_panels": panel_list,
            "site_types": type_list,
            "original_image_id": image_mapping[image_name],
            "original_site_id": site_id_original
        })

    return output_list_


def process_siz_n_loc_output(entry_):
    # claim level butterfly plots
    r_c = entry_["claim_level"]["damage_location"]

    bflyinps = np.load(os.path.join(app_dir, "libs/BFcontours.npy"), allow_pickle=True)
    (PANEL_NAMES, PANEL_COLORS) = np.load(os.path.join(app_dir, "libs/PANELS.npy"), allow_pickle=True)

    r_c, butterfly_ = get_butterfly_plot(
        bflyinps,
        r_c,
        entry_["claim_level"]["damage_panels"],
        PANEL_NAMES,
        num_grid=3)
#     r_c, butterfly_ = get_butterfly_plot(bflyinps, r_c, PANEL_NAMES, num_grid=3)
    # butterfly_ = cv2.imread(os.path.join(app_dir, "examples/butterfly.png"))
    butterfly_bytes = base64.b64encode(cv2.imencode('.jpg', butterfly_)[1]).decode()

    # claim-level damage_types
    claim_damage_types = entry_["claim_level"].get("damage_types", [])



    # image level info
    raw_image_list = []
    claim_size_pred_list = []
    claim_loc_pred_list = []

    size_example_count = 0
    loc_example_count = 0

    # mapping from image name to image id
    # this is useful for claim-level site evaluation
    image_mapping = {}

    for ci, (image_name, image_info) in enumerate(entry_.items()):
        if image_name == "claim_level":
            continue

        file_ = image_info["image_path"]
        # <<< !!! LOCAL INFO
        # file_ = "/Users/mohanliu/Desktop/temp_images/{}".format(os.path.basename(image_info["image_path"]))
        # file_ = os.path.join(app_dir, "examples/placeholder.png")
        # >>>


        # apply tagnet filter (remove images with invalid tags)
        if "output" not in image_info:
            continue
            
        image_tag = image_info["output"].get("image_tag", "unknown")

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


                # draw bounding box on images
                x1, y1, x2, y2 = bbox
                image_temp = cv2.rectangle(image_, (x1, y1), (x2, y2), (255, 155, 100), 3)

                # draw reference arrow and length in text in the image
                ref_arrow_info = _process_reference_arrow(
                    image_info["output"]["vals"], image_info["output"].get("img_size", [800, 600])
                )
                
                if ref_arrow_info != []:
                    for (center_0, end_1, end_2, arrow_length_) in ref_arrow_info:
                        # draw the arrow 
                        image_temp = cv2.arrowedLine(image_temp, center_0, end_1, (0, 255, 255), 5)
                        image_temp = cv2.arrowedLine(image_temp, center_0, end_2, (0, 255, 255), 5)
                        
                        # put the text on 
                        image_temp = cv2.putText(
                            image_temp, 
                            "{:.2f} cm".format(arrow_length_),
                            center_0,
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1.0, (0, 255, 255), 2, cv2.LINE_AA
                        )

                # convert processed image to bytes
                image_temp_bytes = base64.b64encode(cv2.imencode('.jpg', image_temp)[1]).decode()

                # get predictions for size 
                if site_info["lxw"] == ["N/A", "N/A"] or site_info["lxw"] == "unknown":
                    x_dim = "N.A."
                    y_dim = "N.A."
                elif y2 - y1 > x2 - x1:
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
                    "y_dim": y_dim,
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
                if image_info["output"]["damage_types"] == "unknown":
                    _dmgtype = []
                else:
                    _dmgtype = image_info["output"]["damage_types"].get(
                        "predicted_damage_types", []
                    )

                claim_pred_temp_dict = {
                    "image_id": size_example_count,
                    "image_name": image_name,
                    "image_tag": image_tag, 
                    "damage_list": pred_list,
                    "damage_types": _dmgtype
                }
                image_mapping[image_name] = size_example_count

                claim_size_pred_list.append(claim_pred_temp_dict)
                size_example_count += 1

    # claim-level damage sites
    claim_damage_sizes_panels = _collect_claim_damage_size_info(
        entry_["claim_level"].get("damage_sites", {}), image_mapping
    )

    return (
        claim_size_pred_list, 
        claim_loc_pred_list,
        butterfly_bytes,
        claim_damage_types,
        claim_damage_sizes_panels
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

    (
        claim_size_preds, 
        claim_loc_preds, 
        butterfly_bytes, 
        claim_damage_types,
        claim_damage_sizes_panels
    ) = process_siz_n_loc_output(raw_data[session['claim_name']])


    backtracking_file = os.path.join(output_dir, "backtracking_{}.json".format(current_user.id))

    if os.path.exists(backtracking_file):
        with open(backtracking_file, "r") as f:
            saved_data = json.load(f)
    else:
        saved_data = {
            "selected_buttons": [],
            "selected_dropdowns": [],
            "previous_comments": []
        }

    return render_template(
        "{}.html".format(tool_name), 
        butterfly_bytes=butterfly_bytes,
        claim_predictions=claim_size_preds,
        claim_damage_images=claim_loc_preds,
        claim_damage_types=claim_damage_types,
        claim_damage_sizes_panels=claim_damage_sizes_panels,
        sites_aggregation_evals=claim_damage_sites_aggregation_evals,
        image_number=len(claim_size_preds),
        claim_name=session['claim_name'], 
        index=session['claim_index'],
        total_claims_present=total_claims_present,
        progress=progress,
        panel_list=panel_list,
        loc_list=loc_list,
        type_options=DMG_TYPE_OPTIONS,
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
        # collect image level evaluations
        wrong_arrows = []
        missed_damages = []
        dmgtype_mislabel_image_level = []
        dmgtype_falselabel_image_level = []
        dmgsizeeval_comments = []
        

        img_id = 0
        while request.form.get("dmgsize_comment{}".format(img_id)) is not None:
            _wrong_arrow = request.form.get("wrongarrows-image{}".format(img_id))
            if _wrong_arrow is not None:
                wrong_arrows.append(_wrong_arrow)
            _missed_damages = request.form.get("misdamage-image{}".format(img_id))
            if _missed_damages is not None:
                missed_damages.append(_missed_damages)
            dmgtype_mislabel_image_level.append(request.form.getlist("mislabels-image{}".format(img_id)))
            dmgtype_falselabel_image_level.append(request.form.getlist("wronglabels-image{}".format(img_id)))
            dmgsizeeval_comments.append(request.form.get("dmgsize_comment{}".format(img_id)))
            img_id += 1

        # collect site level evaluations
        dmgsizeeval_likert = []

        img_id = 0
        while request.form.get("dmgsizeeval-image{}-damage{}".format(img_id, 0)) is not None:
            dmg_id = 0
            while request.form.get("dmgsizeeval-image{}-damage{}".format(img_id, dmg_id)) is not None:
                dmgsizeeval_likert.append(request.form.get("dmgsizeeval-image{}-damage{}".format(img_id, dmg_id)))
                dmg_id += 1
            img_id += 1

        # collect claim level evalutions
        claim_damage_sites_evals_selection = []
        claim_damage_sites_evals_panel = []
        claim_damage_sites_evals_type = []

        site_id = 0
        while request.form.get("claim_damage_eval_site_selection_{}".format(site_id)) is not None:
            claim_damage_sites_evals_selection.append(request.form.get("claim_damage_eval_site_selection_{}".format(site_id)))
            claim_damage_sites_evals_panel.append(request.form.get("claim_damage_eval_site_panel_{}".format(site_id)))
            claim_damage_sites_evals_type.append(request.form.get("claim_damage_eval_site_type_{}".format(site_id)))
            site_id += 1


        output = {
            "claim_id": session['claim_name'],
            "relevant": True, 
            "damage_size_wrong_arrows": wrong_arrows,
            "damage_size_missed_damages": missed_damages,
            "damage_size_evaluation": dmgsizeeval_likert,
            "damage_location_evaluation": request.form.get("dmgloc_eval"),
            "damage_location_mislabel_panels": request.form.getlist("mislabelpanel"),
            "damage_location_mislabel_grids": request.form.getlist("mislabelloc"),
            "damage_location_falselabel_panels": request.form.getlist("falslabelpanel"),
            "damage_location_falselabel_grids": request.form.getlist("falslabelloc"),
            "damage_type_mislabels_image_level": dmgtype_mislabel_image_level,
            "damage_type_falselabels_image_level": dmgtype_falselabel_image_level,
            "damage_types_correct_claim_level": request.form.getlist("dmg-type-claim"),
            "damage_sites_claim_evaluations_selection": claim_damage_sites_evals_selection,
            "damage_sites_claim_evaluations_panel": claim_damage_sites_evals_panel,
            "damage_sites_claim_evaluations_type": claim_damage_sites_evals_type,
            "damage_sites_claim_num_missed_sites": request.form.get("num_sites_missed"),
            "damage_sites_claim_num_missed_panels": request.form.get("num_panels_missed"),
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

    # collect selected buttons
    selected_buttons = []
    selected_dropdowns = []


    for item in input_dict.get("damage_size_evaluation", []):
        _, image_id, dmg_id, likert_scale = item.split("-")
        selected_buttons.append("dmgsizeeval{}_{}_{}".format(
            image_id.replace("image", ""),
            dmg_id.replace("damage", ""),
            likert_scale
        ))

    selected_buttons.append("dmgloc_eval_{}".format(input_dict.get("damage_location_evaluation", "")))

    for item in input_dict.get("damage_sites_claim_evaluations_selection", []):
        selected_dropdowns.append(item)
        
    for item in input_dict.get("damage_sites_claim_evaluations_panel", []):
        selected_dropdowns.append(item)

    for item in input_dict.get("damage_sites_claim_evaluations_type", []):
        selected_dropdowns.append(item)
        
    for item in input_dict.get("damage_size_wrong_arrows", []):
        selected_buttons.append(item)
        
    for item in input_dict.get("damage_size_missed_damages", []):
        selected_buttons.append(item)

    output_dict["selected_dropdowns"] = selected_dropdowns
    output_dict["selected_buttons"] = selected_buttons

    # collect previous comments
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
