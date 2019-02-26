
import openmc

from matplotlib import image as mpimage
from ctypes import c_int
from openmc.capi import core
from openmc.capi. plot import _Plot, _Position, _RGBColor, image_data_for_plot
import numpy as np

bases = ('xy', 'xz', 'yz')

def rand_color():
    return tuple(np.random.choice(range(256), size=3))

def gen_plot(view):
    # generate colors if not present
    for cell_id, cell in view.cells.items():
        if cell.color == None:
            cell.color = rand_color()

    for mat_id, mat in view.materials.items():
        if mat.color == None:
            mat.color = rand_color()

    # create empty image data
    pixels  = np.ndarray((view.vRes,view.hRes,3), dtype=int)
    IntThree = c_int*3

    # calculate positions
    xstep = view.width / view.hRes
    ystep = view.height / view.vRes
    print(xstep, ystep)

    xidx = bases.index(view.basis)
    yidx = min(xidx + 1, 2)
    zidx = [0,1,2]
    zidx.remove(xidx)
    zidx.remove(yidx)
    zidx = zidx[0]

    openmc_plot = _Plot()

    openmc_plot.origin_ = _Position()
    openmc_plot.origin_.x = view.origin[0]
    openmc_plot.origin_.y = view.origin[1]
    openmc_plot.origin_.z = view.origin[2]

    width = _Position()
    width.x = view.width
    width.y = view.height
    width.z = 0

    openmc_plot.width_ = width

    openmc_plot.basis_ = 1
    openmc_plot.pixels_ = IntThree(view.hRes, view.vRes, 0)
    openmc_plot.level_ = -1

    img = image_data_for_plot(openmc_plot)

    image = np.zeros((view.hRes, view.vRes, 3), dtype = int)
    # set cell colors
    cell_ids = np.unique(img[:,:,0])
    print(cell_ids)
    for c in cell_ids:
        print(c)
        if c == -1:
            image[img[:,:,0] == c] = view.plotBackground
        else:
            image[img[:,:,0] == c] = view.cells[str(c)].color


    mpimage.imsave("test.png",np.swapaxes(image,0,1))

    # pixels = np.array([view.hRes, view.vRes, 0], dtype = int)

    # for i in range(view.hRes):
    #     x = x_start + (i * xstep)
    #     for j in range(view.vRes):
    #         y = y_start - (j * ystep)
    #         try:
    #             cell, err_code = core.find_cell([x, y, z])
    #             image[j][i] = view.cells[str(cell.id)].color
    #         except:
    #             image[j][i] = view.plotBackground
