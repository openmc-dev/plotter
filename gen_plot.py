
import openmc

from matplotlib import image as mpimage
from openmc.capi. plot import _Plot, image_data_for_plot
import numpy as np

def rand_color():
    return tuple(np.random.choice(range(256), size=3))

def gen_ids(view):
    p = view.asPlot()
    ids = image_data_for_plot(p)
    return np.swapaxes(ids, 0, 1)

def gen_plot(view):
    # generate colors if not present
    for cell_id, cell in view.cells.items():
        if cell.color == None:
            cell.color = rand_color()

    for mat_id, mat in view.materials.items():
        if mat.color == None:
            mat.color = rand_color()

    ids = gen_ids(view)

    image = np.zeros((view.vRes, view.hRes, 3), dtype = int)

    # set cell colors
    cell_ids = np.unique(ids[:,:,0])
    for c in cell_ids:
        if c == -1:
            image[ids[:,:,0] == c] = view.plotBackground
        else:
            image[ids[:,:,0] == c] = view.cells[str(c)].color

    return image, ids
