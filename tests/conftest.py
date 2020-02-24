import os
from pathlib import Path

import pytest

@pytest.fixture(scope='module', autouse=True)
def setup_regression_test(request):
    # Change to test directory
    olddir = request.fspath.dirpath().chdir()
    try:
        yield
    finally:
        # some cleanup
        if Path("./plot_settings.pkl").exists():
            os.remove("plot_settings.pkl")

        olddir.chdir()
