"""
外部システム接続用の Connector パッケージ。

本パッケージは BaseConnector 抽象基底クラスと具象 connector を提供する。
WorkloadRunner は connector registry を通じて connector 名で解決する。

Note:
    - Phase 2.5 では mock connector のみ実装する
    - 具象 connector を直接 import するのではなく、registry 経由で参照する
"""
