"""
Connector Adapter の抽象基底クラスを定義する。

本モジュールは全ての connector が実装すべきインターフェースを提供する。
WorkloadRunner は BaseConnector のインターフェースのみに依存する。

入出力: execute / dry_run / capabilities メソッドの型定義。
制約: 具象 connector はこのクラスを継承して実装すること。

Note:
    - execute() は副作用を伴う本実行を行う
    - dry_run() は副作用なしでプレビュー情報を返す
    - capabilities() はサポートするアクション一覧を返す
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from app.schemas.connector_capability import ConnectorCapability


class BaseConnector(ABC):
    """Connector の抽象基底クラス。

    全ての connector はこのクラスを継承し、
    execute / dry_run / capabilities を実装する。

    主要メソッド:
        execute: workload ステップを本実行する
        dry_run: 副作用なしで実行プレビューを返す
        capabilities: サポートするアクション一覧を返す

    Note:
        - WorkloadRunner はこのインターフェースのみに依存する
        - 具象実装は connector registry に登録して使用する
    """

    @abstractmethod
    def execute(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """workload ステップを本実行する。

        Args:
            action: 実行するアクション名（例: "tag.assign"）
            inputs: アクションに渡す入力パラメータ

        Returns:
            実行結果を含む dict（status, message 等）

        Raises:
            NotImplementedError: サブクラスで未実装の場合

        Note:
            - 副作用を伴う処理を実行する
            - 失敗時は status="failed" と error_code を含む dict を返す
        """

    @abstractmethod
    def dry_run(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """副作用なしで実行プレビューを返す。

        Args:
            action: プレビュー対象のアクション名
            inputs: アクションに渡す入力パラメータ

        Returns:
            プレビュー情報を含む dict（preview, estimated_target_count 等）

        Raises:
            NotImplementedError: サブクラスで未実装の場合

        Note:
            - 外部システムへの書き込みは一切行わない
        """

    @abstractmethod
    def capabilities(self) -> ConnectorCapability:
        """この connector がサポートするアクション一覧を返す。

        Returns:
            ConnectorCapability モデル

        Raises:
            NotImplementedError: サブクラスで未実装の場合
        """
