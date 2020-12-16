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
DMG_TYPE_OPTIONS = [
    "dent", "scratch", "tear",
    "crack", "misalignment", 
    "buckle", "crease", "ding", "missing", 
    "bent", "twist", "kink", "hole",
    "other", "unknown"
]

tool_name = 'damage_type_annotation'
local_bp = Blueprint(tool_name, __name__)

output_dir = os.path.join(app_dir, "output", tool_name)
input_dir = os.path.join(app_dir, "input", tool_name)


def _clear_black_bg(image_arr):
    tmp = cv2.cvtColor(image_arr, cv2.COLOR_BGR2GRAY)
    _, alpha = cv2.threshold(tmp, 0, 255, cv2.THRESH_BINARY)

    b, g, r = cv2.split(image_arr)
    rgba = [b, g, r, alpha]
    dst = cv2.merge(rgba, 4)

    return base64.b64encode(cv2.imencode('.png', dst)[1]).decode()

def _get_contours(image_array, pixel_th=50, area_th=100):
    contours = []
    
    img = (cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY) > pixel_th).astype(np.uint8)
    imsize = img.shape

    kernel = np.ones((5, 5), dtype=np.uint8)
    closing = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel, iterations=1)
    opening = cv2.morphologyEx(closing, cv2.MORPH_OPEN, kernel, iterations=1)
    conts, heirarchy = cv2.findContours(opening, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for i in conts:
        area = cv2.contourArea(i)
        if area > area_th: 
            contours.append(i)
        
    return contours

def _split_original_mask(mask_cv_image_arr, **kwargs):
    contours_ = _get_contours(mask_cv_image_arr)

    single_mask_bytes = []

    ctr = 0
    for cont in contours_:
        blank_image = np.zeros(mask_cv_image_arr.shape, np.uint8)
        single_mask_ = cv2.drawContours(blank_image, [cont], 0, (0, 255, 255), thickness=cv2.FILLED)

        single_mask_bytes.append({
            "site_id": ctr,
            "mask_bytes": _clear_black_bg(single_mask_)
        })

        ctr += 1

    return single_mask_bytes


def process_tod_data(entry_):
    # info from tod pipeline
    file_ = entry_["raw_image_path"]
    mask_ = entry_["damage_mask_path"]

    # load image
    image_ = cv2.imread(file_)
    mask_image_array = cv2.imread(mask_)

    try:
        mask_bytes_data = _split_original_mask(mask_image_array)
    except cv2.error:
        mask_bytes_data = {}

    # get original image dimension
    width, height = Image.open(file_).size

    # return file_
    return (
        file_, 
        mask_bytes_data,
        width,
        height
    )

def load_previous_data(image_output_dir):
    counter_ = -1
    previous_data = []
    for saved_image_name in glob.glob(os.path.join(
            image_output_dir, "annotation_site_*.png"
        )):
        counter_ += 1
        type_ = os.path.basename(saved_image_name).replace(".png", "").split("_")[-1]
        img_ = cv2.imread(saved_image_name)

        previous_data.append({
            "id": counter_,
            "type": type_,
            "image_mask": _clear_black_bg(img_) 
        })

    return previous_data, max(0, counter_)



@local_bp.route('/', methods=['GET'])
@login_required
def entry():
    record_file = os.path.join(input_dir, 'record_{}'.format(current_user.id))

    if not os.path.exists(record_file):
        redirect(url_for('{}.main'.format(tool_name), page=0))

    page_ = get_current_index(record_file)
    
    return redirect(url_for('{}.main'.format(tool_name), page=page_))

@local_bp.route('/page<page>', methods=['GET'])
@login_required
def main(page):
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
    total_images_present = len(images_list)

    # a file to keep a record of the process
    record_file = os.path.join(input_dir, 'record_{}'.format(current_user.id))

    # current working image
    session['image_index'] = int(page)
    progress = int((session['image_index'] + 1) / total_images_present * 100) 

    # exit if all images are processed
    if session['image_index'] == len(images_list):
        return redirect(url_for('{}.final'.format(tool_name)))

        

    session['image_name'] = images_list[session['image_index']]

    raw_image_path, mask_image_bytes_data, w, h = process_tod_data(raw_data[session['image_name']])

    # store a temporary image in static for easy flask access
    # This can be optimzed in future
    temp_static_path = os.path.join(
        app_dir, 
        "temp_images",
        os.path.basename(raw_image_path)
    )

    if not os.path.exists(temp_static_path):
        shutil.copy(raw_image_path, temp_static_path)

    temp_image_path = os.path.basename(raw_image_path)

    # load previous data
    image_output_dir = os.path.join(output_dir, session['image_name'])
    if os.path.exists(image_output_dir):
        previous_data, previous_counter = load_previous_data(image_output_dir)
    else:
        previous_data = []
        previous_counter = 0

    return render_template(
        'damage_type_annotation.html', 
        mask_image_bytes_data=mask_image_bytes_data, 
        image_basepath=temp_image_path,
        width=w,
        height=h,
        image_name=session['image_name'], 
        index=session['image_index'],
        total_images_present=total_images_present,
        progress=progress,
        damage_type_options=DMG_TYPE_OPTIONS,
        previous_data=previous_data,
        previous_counter=previous_counter,
    )


# Hit submit button
@local_bp.route('/', methods=['POST'])
@login_required
def process():
    # file to keep the record
    record_file = os.path.join(input_dir, 'record_{}'.format(current_user.id))

    # output file
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    output_file = os.path.join(output_dir, "annotation_results_{}.json".format(current_user.id))

    # post request from html
        # cases once we want to go back one example
    if request.form['submit_done'] == 'back':
        update_current_index(record_file, session['image_index'] - 1)

        return redirect(url_for('{}.main'.format(tool_name), page=session['image_index'] - 1))

    # cases when image is not relevant
    elif request.form['submit_done'] == 'next':
        # output image directory
        image_name = request.form.get("image_name")
        image_output_dir = os.path.join(output_dir, image_name)

        # cleanup stuff in output folder and created a new empty one
        if os.path.exists(image_output_dir):
            shutil.rmtree(image_output_dir)

        os.makedirs(image_output_dir)


        # original image saved in `static` folder
        image_path = request.form.get("image_path")
        original_image_path = os.path.join(app_dir, "temp_images", image_path)
        background = Image.open(original_image_path)

        # wip collect all annotations
        annotation_output_list = []
        annotation_html_keys = [v for v in request.form.keys() if v.startswith("annotation_site_")]

        for k in annotation_html_keys:
            site_id_ = k.strip().split("_")[-1]
            annotated_type = request.form["dmg_type_site_{}".format(site_id_)]

            tem_ann = request.form[k]
            pic_temp = io.BytesIO(base64.b64decode(tem_ann.partition('base64,')[2]))

            foreground_temp = Image.open(pic_temp)
            annotation_output_list.append(foreground_temp)

            foreground_temp_out = foreground_temp.convert("RGB")
            foreground_temp_out.save(os.path.join(
                image_output_dir, 
                "{}_{}.png".format(k, annotated_type)
            ))

        # save all annotations
        for fg in annotation_output_list:
            background.paste(fg, (0, 0), fg)

        background.save(os.path.join(image_output_dir, "all_annotations.png"))
        touch(os.path.join(image_output_dir, "{}.lock".format(current_user.id)))

    # update progress
    session['image_index'] += 1
    update_current_index(record_file, session['image_index'])

    return redirect(url_for('{}.main'.format(tool_name), page=session['image_index']))


@local_bp.route('/transition', methods=['GET'])
@login_required
def final():
    return render_template(
        "tod_annotation_transition.html",
    )

@local_bp.route('/transition', methods=['POST'])
@login_required
def nextbatch():
    if not os.path.exists(os.path.join(input_dir, "annotated_data")):
        os.makedirs(os.path.join(input_dir, "annotated_data"))


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

    # a file to keep a record of the process
    record_file = os.path.join(input_dir, 'record_{}'.format(current_user.id))


    if request.form.get("submit") == "next":
#         touch(os.path.join(input_dir, '{}_completed_by_{}'.format(
#             os.path.basename(annotation_file), current_user.id
#         )))
        remove_if_exists(record_file)
        shutil.move(
            annotation_file,
            os.path.join(
                input_dir, "annotated_data", os.path.basename(annotation_file)
            )
        )
        return redirect(url_for('{}.entry'.format(tool_name)))

    return render_template(
        "tod_annotation_transition.html",
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