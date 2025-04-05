import sys
import os
from pathlib import Path

# Add the project root to the path so imports like 'from llm.llm_call' work
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))