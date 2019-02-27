
import openmc

from matplotlib import image as mpimage
from openmc.capi. plot import _Plot, image_data_for_plot
import numpy as np

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

    openmc_plot = _Plot()
    openmc_plot.origin = view.origin
    openmc_plot.basis = view.basis
    openmc_plot.width = view.width
    openmc_plot.height = view.height
    openmc_plot.hRes = view.hRes
    openmc_plot.vRes = view.vRes
    openmc_plot.level_ = -1

    img = image_data_for_plot(openmc_plot)

    image = np.zeros((view.hRes, view.vRes, 3), dtype = int)

    # set cell colors
    cell_ids = np.unique(img[:,:,0])
    for c in cell_ids:
        if c == -1:
            image[img[:,:,0] == c] = view.plotBackground
        else:
            image[img[:,:,0] == c] = view.cells[str(c)].color

    mpimage.imsave("test.png",np.swapaxes(image,0,1))
