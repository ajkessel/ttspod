"""placeholder init module"""
import os
import sys
from pathlib import Path
# allow components to be run separately
sys.path.append(Path(os.path.realpath(__file__)).parent)
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
