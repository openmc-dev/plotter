import numpy as np


def random_rgb():
    return tuple(np.random.choice(range(256), size=3))


def rgb_normalize(rgb):
    return tuple([c/255. for c in rgb])


def invert_rgb(rgb, normalized=False):
    rgb_max = 1.0 if normalized else 255.
    inv = [rgb_max - c for c in rgb[0:3]]
    return (*inv, *rgb[3:])
