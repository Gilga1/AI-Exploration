from pathlib import Path

from qwen_agentic_ft.train.data import load_training_config


def test_training_config_loads():
    config = load_training_config(Path("config/training.yaml"))
    assert config["model_name"] == "Qwen/Qwen3.5-2B-Instruct"
    assert config["lora"]["r"] == 16
    assert "training" in config
