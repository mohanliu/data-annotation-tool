import cv2
import numpy as np
import json


def im2box(im,size_th=10, MAflag=0):
    ret, thresh = cv2.threshold(im, .001, 1, 0)
    # get panel outline
    cnt, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    # merge if multiple outlines exist (if panel is split up)
    cntT = np.zeros((0, 2)).astype(np.int32)
    for j in cnt:
        if len(j) > size_th: #arbitrary small number larger than 1 (we don't want random pixels)
            j = np.squeeze(j, axis=1)
            cntT = np.vstack((cntT, j))

    cnt = np.expand_dims(cntT, axis=1)
    
    # get minimum area rectangle or simple bounding box
    if MAflag:
        rect = cv2.minAreaRect(cnt)
        box = cv2.boxPoints(rect)
    else:
        rect = cv2.boundingRect(cnt)
        box = cv2.boxPoints((
            (rect[0] + rect[2]/2, rect[1] + rect[3]/2), 
            (rect[2], rect[3]), 
            0.0
        ))

    # get box corners
    box = np.int0(box)
    return cnt, box, rect

 
def box2grid(box, num_grid):
    # set up grid points
    x2 = []
    for i in range(0, num_grid + 1):
        diffy = (box[0, :] - box[3, :])/num_grid * i
        for j in range(0, num_grid + 1):
            diffx = (box[0, :] - box[1, :])/num_grid * j
            x2.append(box[0, :] - diffx - diffy)
    x2 = np.stack(x2)
    return x2

 

def grid2sbox(x2, num_grid):
    # use grid points to construct mini boxes
    s_box = []
    for i in range(0, num_grid):
        for j in range(0, num_grid):
            lr = i * (num_grid + 1) + j
            lf = i * (num_grid + 1) + j + 1
            tr = (i + 1) * (num_grid + 1) + j + 1
            tf = (i + 1) * (num_grid + 1) + j
            s_box.append(np.int0(x2[[lr, lf, tr, tf], :]))
    return s_box


def get_butterfly_plot(bflyinps, r_c, dam_pan_cl, PANEL_NAMES, num_grid=3):
    (bfly, contoursBF, im_dict) = bflyinps
    r_c = np.array(r_c)

    #rotate grids for plot
    flatten = lambda l: [item for sublist in l for item in sublist]

    kmapb = list(np.linspace(0, num_grid ** 2 - 1, num_grid ** 2).astype(np.uint8))
    kmapl = flatten([[i for i in kmapb[num_grid - (j + 1)::3]] for j in range(0, num_grid)])
    kmapt = kmapb[::-1]
    kmapr = kmapl[::-1]
    kmap = { 
        0: kmapt,
        1: kmapl,
        2: kmapb,
        3: kmapr
    }
    
    totim = np.zeros(bfly.shape)
    for panel in dam_pan_cl:
        try:
            c_key = np.array(list(im_dict.keys()))
            c_val = np.array(list(im_dict.values()))[:, 0]
            c_map = np.array(list(im_dict.values()))[:, 1]

 

            c_ind = c_key[np.isin(c_val, PANEL_NAMES[panel])][0]
            cnt = contoursBF[c_ind]
            c_m = im_dict[c_ind][1]
 

            im = cv2.drawContours(
                np.zeros(bfly.shape),
                [np.hstack((cnt[:, :, 0],cnt[:, :, 1]))],
                0,
                1,
                thickness=cv2.FILLED
            ).astype(np.uint8)

            #convert mask to smallest bounding rectangle
            cnt, box, rect = im2box(im)

 

            #convert box to grid points
            x2 = box2grid(box, num_grid)
            #convert grid points to mini box corners
            s_box = grid2sbox(x2, num_grid)
            for k in range(0, num_grid ** 2): 
                xx = cv2.drawContours(np.zeros(bfly.shape), [s_box[kmap[c_m][k]]], 0, 1, thickness=cv2.FILLED)
                totim = totim + im * xx * r_c[k, panel]
        except:
            print('Not seen:', PANEL_NAMES[panel])
        

    totim[(totim > 0) & (totim <= 0.25)] = 0.25
    totim[(totim > 0.25) & (totim <= 0.5)] = 0.5
    totim[(totim > 0.5) & (totim <= 0.75)] = 0.75
    totim[(totim > 0.75) & (totim <= 1)] = 1
    
    newbfly = np.stack(
        (255 - bfly, 255 - bfly, np.minimum(255, 255 - bfly + totim * 255)), 
    axis=2).astype(np.uint8)
    
    
    return r_c, newbfly[300:1350, 200:1075]
