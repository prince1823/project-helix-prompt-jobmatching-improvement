import os
import yaml
from pathlib import Path

CONFIG_PATH = os.getenv(
    "CONFIG_PATH",
    "/app/config/app/config.yaml",
)
with open(Path(CONFIG_PATH), "r") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)
