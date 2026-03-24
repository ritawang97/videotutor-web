import logging
import os
from pathlib import Path

VERSION = "v1.3.3"
YEAR = 2025
APP_NAME = "RUII课堂助手 VideoCaptioner"
AUTHOR = "RUII"

HELP_URL = ""
GITHUB_REPO_URL = ""
RELEASE_URL = ""
FEEDBACK_URL = ""

# 路径
ROOT_PATH = Path(__file__).parent


def _path_from_env(env_name: str, default: Path) -> Path:
    raw = os.getenv(env_name, "").strip()
    return Path(raw).expanduser() if raw else default

RESOURCE_PATH = ROOT_PATH.parent / "resource"
APPDATA_PATH = _path_from_env("VIDEOTUTOR_APPDATA_PATH", ROOT_PATH.parent / "AppData")
WORK_PATH = _path_from_env("VIDEOTUTOR_WORK_PATH", ROOT_PATH.parent / "work-dir")


BIN_PATH = RESOURCE_PATH / "bin"
ASSETS_PATH = RESOURCE_PATH / "assets"
SUBTITLE_STYLE_PATH = RESOURCE_PATH / "subtitle_style"

LOG_PATH = APPDATA_PATH / "logs"
SETTINGS_PATH = APPDATA_PATH / "settings.json"
CACHE_PATH = APPDATA_PATH / "cache"
MODEL_PATH = APPDATA_PATH / "models"

FASER_WHISPER_PATH = BIN_PATH / "Faster-Whisper-XXL"

# 日志配置
LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 环境变量添加 bin 路径，添加到PATH开头以优先使用
os.environ["PATH"] = str(BIN_PATH) + os.pathsep + os.environ["PATH"]
os.environ["PATH"] = str(FASER_WHISPER_PATH) + os.pathsep + os.environ["PATH"]

# 添加 VLC 路径
os.environ["PYTHON_VLC_MODULE_PATH"] = str(BIN_PATH / "vlc")

# 创建路径
for p in [CACHE_PATH, LOG_PATH, WORK_PATH, MODEL_PATH]:
    p.mkdir(parents=True, exist_ok=True)
