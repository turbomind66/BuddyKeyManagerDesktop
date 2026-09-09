"""测试公共配置：在导入 app 前将数据目录指向临时目录，避免污染真实 data/."""

import os
import shutil
import tempfile
from pathlib import Path

_TMP = Path(tempfile.gettempdir()) / 'bkm-test-data'
if _TMP.exists():
    shutil.rmtree(_TMP)
_TMP.mkdir(parents=True, exist_ok=True)

os.environ.setdefault('BKM_DATA_DIR', str(_TMP))
os.environ.setdefault('BKM_OPEN_BROWSER', 'false')
os.environ.setdefault('BKM_HOST', '127.0.0.1')
os.environ.setdefault('BKM_PORT', '0')