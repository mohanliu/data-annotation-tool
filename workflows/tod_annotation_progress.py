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

from libs.utils import (
    app_dir, 
    touch, 
)

from collections import defaultdict

tool_name = 'tod_annotation_progress'
local_bp = Blueprint(tool_name, __name__)

input_dir = os.path.join(app_dir, "output", 'damage_type_annotation')

@local_bp.route('/', methods=['GET'])
def main():
    total_stats = defaultdict(int)

    for fol in glob.glob(os.path.join(input_dir, "*")):
        for f in glob.glob("{}/*.lock".format(fol)):
            user = f.split("/")[-1].replace('.lock', '')

            total_stats[user] += 1

    output_list = sorted(
        [
            {"name": k, "num": v} for k, v in total_stats.items()
        ], 
        key=lambda x: x["num"],
        reverse=True
    )

    return render_template(
        'tod_annotation_progress.html', 
        annotation_stats=output_list
    )