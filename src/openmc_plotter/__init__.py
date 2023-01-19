try:
    # this works for python 3.8 and higher
    from importlib.metadata import version, PackageNotFoundError
except (ModuleNotFoundError, ImportError):
    # this works for python 3.7 and lower
    from importlib_metadata import version, PackageNotFoundError
try:
    __version__ = version("openmc_plotter")
except PackageNotFoundError:
    from setuptools_scm import get_version

    __version__ = get_version(root="..", relative_to=__file__)

__all__ = ["__version__"]
