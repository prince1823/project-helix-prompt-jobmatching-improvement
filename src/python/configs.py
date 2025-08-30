import yaml
from pathlib import Path

with open(
    Path(__file__).parent.parent.parent.joinpath("config", "app", "config.yaml"), "r"
) as f:
    config = yaml.load(f, Loader=yaml.FullLoader)
