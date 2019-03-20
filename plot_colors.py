
import numpy as np

# for consistent, but random, colors
np.random.seed(10)

def random_rgb():
    return tuple(np.random.choice(range(256), size=3))

def rgb_normalize(rgb):
    return tuple([c/255. for c in rgb])
