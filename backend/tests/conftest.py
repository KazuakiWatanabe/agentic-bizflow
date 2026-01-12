"""
pytest の実行時設定を提供する。

入出力: sys.path を拡張し、app パッケージの import を可能にする。
制約: 追加は1回のみとし、外部API依存は持ち込まない。

Note:
    - backend 直下で pytest を実行する前提
"""

import sys
from pathlib import Path

# backend ルートの基準パス。
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
