import csv
import json
import os
import shutil
from os.path import join, exists

from flask import render_template, url_for, request, redirect, Blueprint, session
from flask_login import login_required, current_user

from PIL import Image, ImageFont, ImageDraw, ImageEnhance
import cv2
import base64

from libs.utils import next_dirs, pop_workflow_session_keys, app_dir, to_base64, touch, remove_if_exists

tool_name = "tod_report"
local_bp = Blueprint(tool_name, __name__)


input_dir = join(app_dir, "output", "tod_survey")


@local_bp.route('/', methods=['GET'])
@login_required
def main():
    # load data to be surveyed
    survey_file = os.path.join(input_dir, "survey_results_{}.json".format(current_user.id))
    if not os.path.exists(survey_file):
        messages = "Nothing prepared for you. Ask admin for more info."
        return render_template(
            "info.html",
            messages=messages,
        )

    with open(survey_file, "r") as f:
        raw_data = json.load(f)

    output_dict = {}
    
    output_dict["num_case_surveyed"] = len(raw_data)

    if output_dict["num_case_surveyed"] == 0:
        for dmg in ["dent", "scratch", "tear", "crack", "misalignment"]:
            output_dict[dmg + "_mis"] = 0
            output_dict[dmg + "_fals"] = 0

        return render_template(
            "{}.html".format(tool_name), 
            stats=output_dict,
        )

    output_dict["not_relevant"] = len(list(filter(lambda x: x["overall_evaluation"] == "Not Relevant", raw_data)))
    output_dict["num_valid"] = output_dict["num_case_surveyed"] - output_dict["not_relevant"]
    output_dict["perc_valid"] = "{:.1%}".format(output_dict["num_valid"] / output_dict["num_case_surveyed"])
    output_dict["not_relevant_perc"] = "{:.1%}".format(output_dict["not_relevant"] / output_dict["num_case_surveyed"])

    dmg_types_mis = {}
    dmg_types_fals = []

    for dmg in ["dent", "scratch", "tear", "crack", "misalignment"]:
        output_dict[dmg + "_mis_cnt"] = sum(list(map(lambda x: 1 if dmg in x.get("mis_labels", []) else 0, raw_data)))
        output_dict[dmg + "_fals_cnt"] = sum(list(map(lambda x: 1 if dmg in x.get("wrong_labels", []) else 0, raw_data)))
        output_dict[dmg + "_mis"] = int(output_dict[dmg + "_mis_cnt"] / output_dict["num_case_surveyed"] * 100) 
        output_dict[dmg + "_fals"] = int(output_dict[dmg + "_fals_cnt"] / output_dict["num_case_surveyed"] * 100) 

    for likert in ["strong_agree", "agree", "neutral", "disagree", "strong_disagree"]:
        output_dict[likert] = len(list(filter(lambda x: x["overall_evaluation"] == likert, raw_data)))
        output_dict[likert + "_perc"] = "{:.1%}".format(output_dict[likert] / output_dict["num_valid"])

    output_dict["not_relevant"] = len(list(filter(lambda x: x["overall_evaluation"] == "Not Relevant", raw_data)))
    output_dict["num_valid"] = output_dict["num_case_surveyed"] - output_dict["not_relevant"]
    output_dict["perc_valid"] = "{:.1%}".format(output_dict["num_valid"] / output_dict["num_case_surveyed"])
    output_dict["not_relevant_perc"] = "{:.1%}".format(output_dict["not_relevant"] / output_dict["num_case_surveyed"])

    output_dict["damage_yes"] = len(list(filter(lambda x: x.get("damage_present", None) == "yes", raw_data)))
    output_dict["damage_maybe"] = len(list(filter(lambda x: x.get("damage_present", None) == "maybe", raw_data)))
    output_dict["damage_no"] = len(list(filter(lambda x: x.get("damage_present", None) == "no", raw_data)))

    output_dict["dmg_outside_bbox_yes"] = len(list(filter(lambda x: x.get("damage_outside_bbox", None) == "yes", raw_data)))
    output_dict["dmg_outside_bbox_maybe"] = len(list(filter(lambda x: x.get("damage_outside_bbox", None) == "maybe", raw_data)))
    output_dict["dmg_outside_bbox_no"] = len(list(filter(lambda x: x.get("damage_outside_bbox", None) == "no", raw_data)))

    return render_template(
        "{}.html".format(tool_name), 
        stats=output_dict,
    )
