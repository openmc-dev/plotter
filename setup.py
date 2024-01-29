from pathlib import Path

from setuptools import setup

# Get version information from __init__.py. This is ugly, but more reliable than
# using an import.
with open('openmc_plotter/__init__.py', 'r') as f:
    version = f.readlines()[-1].split()[-1].strip("'")

# read the contents of your README file
long_description = Path(__file__).with_name("README.md").read_text()

kwargs = {
    'name': 'openmc-plotter',
    'version': version,
    'packages': ['openmc_plotter'],
    'package_data': {'openmc_plotter' : ['assets/*.png']},
    'entry_points': {
        'console_scripts': [
            'openmc-plotter=openmc_plotter.__main__:main'
        ]
    },

    # Metadata
    'author': 'OpenMC Development Team',
    'author_email': 'openmc@anl.gov',
    'description': 'Plotting tool for OpenMC models and tally data',
    'long_description': long_description,
    'long_description_content_type': 'text/markdown',
    'url': 'https://github.com/openmc-dev/plotter',
    'download_url': 'https://github.com/openmc-dev/plotter',
    'project_urls': {
        'Issue Tracker': 'https://github.com/openmc-dev/plotter/issues',
        'Source Code': 'https://github.com/openmc-dev/plotter',
    },
    'classifiers': [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Science/Research',
        'Natural Language :: English',
        'Topic :: Scientific/Engineering',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],

    # Dependencies
    'python_requires': '>=3.6',
    'install_requires': [
        'openmc>0.12.2', 'numpy', 'matplotlib', 'PySide6'
    ],
    'extras_require': {
        'test' : ['pytest', 'pytest-qt'],
        'vtk' : ['vtk']
    },
}

setup(**kwargs)
