import os, glob, base64, shutil
from os.path import join

import logging
from logging.handlers import TimedRotatingFileHandler

app_dir = join(os.path.dirname(os.path.realpath(__file__)), '..')
corners = ['LF', 'RF', 'RR', 'LR']
ann_ops = corners + [None]

def remove_if_exists(path):
    try:
        os.remove(path)
    except OSError:
        pass

def touch(fname):
    if os.path.exists(fname):
        os.utime(fname, None)
    else:
        open(fname, 'a').close()

def next_dirs(input_dir, user):
    # determine the model and claim folder
    # gracefully handle the edge/failure cases
    for model in os.listdir(input_dir):
        model_dir = join(input_dir, model)
        if not os.path.isdir(model_dir):
            continue

        model_has_claim = False
        for claim in os.listdir(model_dir):
            claim_dir = join(model_dir, claim)
            if not os.path.isdir(claim_dir):
                continue
            model_has_claim = True

            # make sure the claim is not locked by another user
            curr_user_lock = join(claim_dir, user+'.lock')
            other_user_lock = [f for f in glob.glob(join(claim_dir, '*.lock')) if f != curr_user_lock]
            if other_user_lock:
                continue

            # we have reached a valid claim
            # lock it for the current user
            touch(curr_user_lock)
            return (model_dir, claim_dir)

        # delete the model dir if it has no claims
        if not model_has_claim:
            shutil.rmtree(model_dir)

    return (None, None)

def ensure_dirs(paths):
    for p in paths:
        if not os.path.exists(p):
            os.mkdir(p)

def to_base64(path):
    try:
        return base64.b64encode(open(path, "rb").read()).decode("utf-8")
    except:
        return ""

def multi_glob(path, arr):
    files = []
    for ext in arr:
        files.extend(glob.glob(join(path, ext)))
    return files

def glob_images(path):
    return multi_glob(path, ('*.gif', '*.png', '*.jpg', '*.jpeg'))

def listdir_fullpath(d):
    return [os.path.join(d, f) for f in os.listdir(d)]

def pop_workflow_session_keys(session):
    # pops all keys in a session except the ones used by flask for login, etc.
    for k in list(session):
        if k not in [u'_fresh', u'_user_id', u'_id']: # the user id was user_id and not _user_id
            session.pop(k)

def delete_lock_files(claim_dir):
    [os.remove(f) for f in glob.glob(join(claim_dir, "*.lock"))]

def create_logger(nam, path, freq, form):
    logger = logging.getLogger(nam)
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        handler = TimedRotatingFileHandler(path, when=freq)
        handler.setLevel(logging.INFO)

        formatter = logging.Formatter(form)
        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger
