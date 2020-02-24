from setuptools import setup

kwargs = {
    'name': 'openmc-plotter',
    'version': '0.1.0',
    'packages': ['openmc_plotter'],
    'entry_points': {
        'console_scripts': [
            'openmc-plotter=openmc_plotter.plotter:main'
        ]
    },

    # Metadata
    'author': 'Patrick Shriwise',
    'author_email': 'pshriwise@anl.gov',
    'description': 'Plotting tool for OpenMC',
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
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Topic :: Scientific/Engineering'
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],

    # Dependencies
    'python_requires': '>=3.6',
    'install_requires': [
        'numpy', 'h5py', 'prompt_toolkit',
    ],
}

setup(**kwargs)
