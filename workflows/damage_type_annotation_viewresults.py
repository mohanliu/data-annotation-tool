import base64
import io
import csv
import json
import os
import shutil
import glob
import cv2
import numpy as np
from datetime import datetime

from PIL import Image
from flask import render_template, url_for, request, redirect, Blueprint, session
from flask_login import login_required, current_user

from libs.stats import daily_stat_count, Stat
from libs.utils import (
    next_dirs, 
    ensure_dirs, 
    glob_images, 
    pop_workflow_session_keys, 
    app_dir, 
    touch, 
    create_logger,
    remove_if_exists
)

tool_name = 'damage_type_annotation_viewresults'
local_bp = Blueprint(tool_name, __name__)

output_dir = os.path.join(app_dir, "output", 'damage_type_annotation')
input_dir = os.path.join(app_dir, "input", 'damage_type_annotation')

def _crop_image_with_mask(mask_image_arr, originl_img_arr):
    result_ = originl_img_arr.copy()
    result_[mask_image_arr == 0] = 0
    result_[mask_image_arr != 0] = originl_img_arr[mask_image_arr != 0]

    return base64.b64encode(cv2.imencode('.png', result_)[1]).decode()

@local_bp.route('/', methods=['GET'])
@login_required
def main():
    # check temp image storage
    if not os.path.exists(os.path.join(app_dir, "temp_images")):
        os.makedirs(os.path.join(app_dir, "temp_images"))

    # load data to be annotated
    annotation_folder = os.path.join(input_dir, "{}".format(current_user.id))

    if not os.path.exists(annotation_folder):
        messages = "Nothing prepared for you. Ask admin for more info."
        return render_template(
            "info.html",
            messages=messages,
        )
    
    data_pool = glob.glob(os.path.join(annotation_folder, "*"))

    if len(data_pool) == 0:
        messages = "You have done your task. Ask admin for more info."
        return render_template(
            "info.html",
            messages=messages,
        )
    else:
        annotation_file = sorted(data_pool)[0]


    with open(annotation_file, "r") as f:
        raw_data = json.load(f)

    # list of images
    images_list = sorted([v for v in raw_data.keys()])

    # a file to keep a record of the process
    record_file = os.path.join(input_dir, 'record_{}'.format(current_user.id))

    # current working image
    session['image_index'] = get_current_index(record_file)

    # prepare annotation results
    annotation_results = []

    page_ = 0
    for image_name in images_list:
        tmp = {}

        ori_path = raw_data[image_name]["raw_image_path"]
        ori_img_arr = cv2.imread(ori_path)
        tmp["original_image"] = base64.b64encode(
            cv2.imencode('.png', ori_img_arr)[1]
        ).decode()
        tmp["page"] = page_
        tmp["image_name"] = image_name

        image_output_dir = os.path.join(output_dir, image_name)


        temp_annotated_data = []
        if os.path.exists(image_output_dir):
            for saved_image_name in glob.glob(os.path.join(
                image_output_dir, "annotation_site_*.png"
            )):
                type_ = os.path.basename(saved_image_name).replace(".png", "").split("_")[-1]

                img_ = cv2.imread(saved_image_name, 0)

                temp_annotated_data.append({
                    "type": type_,
                    "image_mask": _crop_image_with_mask(
                        mask_image_arr=img_,
                        originl_img_arr=ori_img_arr
                    ) 
                })

        tmp["annotations"] = temp_annotated_data

        page_ += 1

        annotation_results.append(tmp)


    return render_template(
        'damage_type_annotation_viewresults.html', 
        index=session['image_index'],
        annotation_results=annotation_results,
    )


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

def record_current_state(record_file_dir):
    if os.path.isfile(record_file_dir):
        fd = open(record_file_dir, 'r')
        reader = csv.reader(fd)
        row1 = next(reader)[0].split()
        fd.close()
        return row1
    else:
        fd = open(record_file_dir, 'a+')
        content = str(0)
        fd.write(content)
        fd.close()
        return ['0']

def update_current_index(record_file_dir, image_index):
    content = str(image_index)
    fd = open(record_file_dir, 'w')
    fd.write(content)
    fd.close()