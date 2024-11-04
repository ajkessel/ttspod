"""placeholder init module"""
import os
import sys
from pathlib import Path
# allow components to be run and referenced separately for troubleshooting
sys.path.append(str(Path(os.path.realpath(__file__)).parent))
sys.path.append(str(os.path.dirname(os.path.realpath(__file__))))
