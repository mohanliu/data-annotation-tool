import csv
import json
import os
import shutil
import glob
from collections import Counter, defaultdict

from flask import render_template, url_for, request, redirect, Blueprint, session
from flask_login import login_required, current_user

from PIL import Image, ImageFont, ImageDraw, ImageEnhance
import cv2
import base64

from libs.utils import next_dirs, pop_workflow_session_keys, app_dir, to_base64, touch, remove_if_exists

tool_name = "tod_survey"
local_bp = Blueprint(tool_name, __name__)

DMG_TYPE_OPTIONS = [
    "dent", "scratch", "tear",
    "crack", "misalignment"
]

output_dir = os.path.join(app_dir, 'output', tool_name)
input_dir = os.path.join(app_dir, 'input', tool_name)


def process_tod_output(entry_):
    # info from tod pipeline
    file_ = entry_["input"]["image_path"]
    # file_ = "/Users/mohanliu/Desktop/temp_images/{}".format(os.path.basename(entry_["input"]["image_path"]))
    
    # load image
    image_ = cv2.imread(file_) 

    # add bounding boxes
    try:
        bbox = entry_["output"]["bounding_boxes"]["zoomed_union"]
        image_ = cv2.rectangle(image_, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (255, 155, 100), 4)
    except KeyError:
        pass
    
    # prediction in text format
    output_text = "[{}]".format(
        ", ".join(entry_["output"]["predicted_damage_types"]
    ))

    alt_dict = entry_["output"]["alternative_predictions"]
    alt_dict["selected"] = entry_["output"]["predicted_damage_types"]

    process_output = defaultdict(list)
    for k, v in alt_dict.items():
        process_output["_".join(sorted(v))].append(k)

    postprocessed_output = []
    for i, (k, v) in enumerate(process_output.items()):
        temp_dict = {
            "index": i + 1,
            "predicted_damages": [] if k == "" else k.split("_"),
            "options": v,
            "checked": False
        }

        if "selected" in v:
            temp_dict["checked"] = True

        postprocessed_output.append(temp_dict)

    return (
        base64.b64encode(cv2.imencode('.jpg', image_)[1]).decode(), 
        entry_["output"]["predicted_damage_types"],
        postprocessed_output,
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
    images_list = [v for v in raw_data.keys()]
    total_images_present = len(images_list)

    # a file to keep a record of the process
    record_file = os.path.join(input_dir, 'record_{}'.format(current_user.id))

    # current working image
    session['image_index'] = get_current_index(record_file)
    progress = int((session['image_index'] + 1) / total_images_present * 100) 

    # exit if all images are processed
    if session['image_index'] == len(images_list):
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

    session['image_name'] = images_list[session['image_index']]

    image_bytes, preds, alt_preds = process_tod_output(raw_data[session['image_name']])

    return render_template(
        "{}.html".format(tool_name), 
        image_bytes=image_bytes,
        predictions=preds,
        alternative_predictions=alt_preds,
        image_name=session['image_name'], 
        type_options=DMG_TYPE_OPTIONS,
        index=session['image_index'],
        total_images_present=total_images_present,
        progress=progress,
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

    # cases once we want to go back one example
    if request.form['submit'] == 'back' and session['image_index'] != 0:
        update_current_index(record_file, session['image_index'] - 1)
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                data = json.load(f)
            data.pop(-1)

            with open(output_file, 'w+') as f:
                json.dump(data, f, indent=4)

        return redirect(url_for('{}.main'.format(tool_name)))

    # cases when image is not relevant
    elif request.form['submit'] == 'skip':
        comm = request.form['comment']
        output = {
            "image_id": session['image_name'], 
            "overall_evaluation": "Not Relevant",
            "comments": comm
        }

    # cases when we have outputs
    else:
        overall_agreement = request.form.get("overall_agreement")
        mis_labels = request.form.getlist("mislabels")
        wrong_labels = request.form.getlist("wronglabels")
        bbox_eval = request.form.get("bbox_eval")
        dmg_eval = request.form.get("dmg_eval")
        alt_selections = request.form.get("alt-selection")
        comm = request.form['comment']
        output = {
            "image_id": session['image_name'], 
            "overall_evaluation": overall_agreement,
            "mis_labels": mis_labels,
            "wrong_labels": wrong_labels,
            "damage_outside_bbox": bbox_eval,
            "damage_present": dmg_eval,
            "alternative_selection": eval(alt_selections),
            "comments": comm
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

    session['image_index'] += 1
    update_current_index(record_file, session['image_index'])

    return redirect(url_for('{}.main'.format(tool_name)))


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
