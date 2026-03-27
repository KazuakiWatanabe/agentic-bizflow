"""
Workload Kind Registry を提供する。

本モジュールは workload kind の動的登録・検索・エイリアス解決を管理する。
各ドメインモジュールが起動時に workload kind を登録し、
ExecutionPlanner と WorkloadRunner がこの Registry を参照する。

入出力: register() で kind を登録、get() / list_all() で取得する。
制約: エイリアス解決は get() / is_valid() で自動的に行う。

Note:
    - kind は '{domain}.{action}' 形式（例: line.tag.assign）
    - 旧形式（tag.assign）はエイリアスとして登録可能
    - シングルトンインスタンスを workload_kind_registry として公開する
"""

import logging
from typing import Dict, List, Optional

from app.schemas.workload_kind import ApprovalRule, WorkloadKindDefinition

logger = logging.getLogger(__name__)


class WorkloadKindRegistry:
    """workload kind の動的レジストリ。

    各ドメインモジュールが起動時に自身の workload kind を登録する。
    ExecutionPlanner と WorkloadRunner はこの Registry を参照する。

    主要メソッド:
        register: kind を登録する
        get: kind を取得する（エイリアス解決含む）
        list_by_domain: ドメイン別一覧
        list_all: 全 kind 一覧
        is_valid: kind が登録済みか判定する
        register_alias: エイリアスを登録する
        resolve_alias: エイリアスを解決する
        register_resolution: 共通 kind → ドメイン kind マッピングを登録する
        get_resolution: 共通 kind の resolution マッピングを取得する
        resolve_to_domain: 共通 kind を特定ドメインの kind に解決する

    Variables:
        _kinds: kind → WorkloadKindDefinition のマッピング
        _aliases: 旧 kind → 新 kind のマッピング
        _resolutions: 共通 kind → {ドメイン → ドメイン固有 kind} のマッピング

    Note:
        - エイリアスは get() / is_valid() で自動解決される
        - resolution は共通 kind をドメイン固有 kind に変換する
    """

    def __init__(self) -> None:
        """WorkloadKindRegistry を初期化する。"""
        # kind → WorkloadKindDefinition のマッピング
        self._kinds: Dict[str, WorkloadKindDefinition] = {}
        # 旧 kind → 新 kind のエイリアスマッピング
        self._aliases: Dict[str, str] = {}
        # 共通 kind → {ドメイン → ドメイン固有 kind} の解決マッピング
        self._resolutions: Dict[str, Dict[str, Optional[str]]] = {}

    def register(
        self,
        kind: str,
        domain: str,
        connector: str,
        requires_approval: ApprovalRule = ApprovalRule.NONE,
        description: str = "",
        keywords: Optional[List[str]] = None,
    ) -> None:
        """workload kind を登録する。

        Args:
            kind: workload kind の識別子
            domain: ドメイン名
            connector: connector registry のキー
            requires_approval: 承認ルール
            description: 人間向け説明
            keywords: キーワードマッチ用のリスト
        """
        definition = WorkloadKindDefinition(
            kind=kind,
            domain=domain,
            connector=connector,
            requires_approval=requires_approval,
            description=description,
            keywords=keywords or [],
        )
        self._kinds[kind] = definition
        logger.debug("workload kind 登録: %s (domain=%s)", kind, domain)

    def get(self, kind: str) -> Optional[WorkloadKindDefinition]:
        """kind を取得する（エイリアス解決含む）。

        Args:
            kind: 検索対象の kind

        Returns:
            WorkloadKindDefinition または None
        """
        resolved = self.resolve_alias(kind)
        return self._kinds.get(resolved)

    def list_by_domain(self, domain: str) -> List[WorkloadKindDefinition]:
        """ドメイン別の kind 一覧を返す。

        Args:
            domain: フィルタ対象のドメイン名

        Returns:
            WorkloadKindDefinition のリスト
        """
        return [d for d in self._kinds.values() if d.domain == domain]

    def list_all(self) -> List[WorkloadKindDefinition]:
        """全 kind 一覧を返す。

        Returns:
            WorkloadKindDefinition のリスト
        """
        return list(self._kinds.values())

    def is_valid(self, kind: str) -> bool:
        """kind が登録済みか判定する（エイリアス解決含む）。

        Args:
            kind: 判定対象の kind

        Returns:
            登録済みなら True
        """
        resolved = self.resolve_alias(kind)
        return resolved in self._kinds

    def register_alias(self, old_kind: str, new_kind: str) -> None:
        """エイリアスを登録する。

        Args:
            old_kind: 旧 kind（エイリアス元）
            new_kind: 新 kind（エイリアス先）

        Note:
            - 旧 kind で get() すると新 kind の定義が返る
        """
        self._aliases[old_kind] = new_kind
        logger.debug("エイリアス登録: %s → %s", old_kind, new_kind)

    def resolve_alias(self, kind: str) -> str:
        """エイリアスを解決する。

        Args:
            kind: 解決対象の kind

        Returns:
            解決後の kind（エイリアスでなければそのまま返す）
        """
        return self._aliases.get(kind, kind)

    def get_all_keywords(self) -> Dict[str, List[str]]:
        """全 kind のキーワードマッピングを返す。

        Returns:
            kind → keywords のマッピング

        Note:
            - ExecutionPlanner がキーワードマッチに使用する
        """
        return {d.kind: d.keywords for d in self._kinds.values() if d.keywords}

    def register_resolution(
        self,
        common_kind: str,
        mapping: Dict[str, Optional[str]],
    ) -> None:
        """共通 kind のドメイン解決マッピングを登録する。

        Args:
            common_kind: 共通 workload kind の識別子
            mapping: {ドメイン名: ドメイン固有 kind} のマッピング

        Note:
            - mapping の値が None の場合、そのドメインは該当 kind を未サポートとする
        """
        self._resolutions[common_kind] = mapping
        logger.debug(
            "resolution 登録: %s → %s",
            common_kind,
            mapping,
        )

    def get_resolution(self, common_kind: str) -> Optional[Dict[str, Optional[str]]]:
        """共通 kind の resolution マッピングを取得する。

        Args:
            common_kind: 共通 workload kind の識別子

        Returns:
            {ドメイン名: ドメイン固有 kind} のマッピング、未登録なら None
        """
        return self._resolutions.get(common_kind)

    def resolve_to_domain(
        self,
        common_kind: str,
        domain: str,
    ) -> Optional[str]:
        """共通 kind を特定ドメインの kind に解決する。

        Args:
            common_kind: 共通 workload kind の識別子
            domain: 解決先のドメイン名

        Returns:
            ドメイン固有の kind、未登録または未サポートなら None

        Note:
            - resolution マッピングにドメインが存在しない場合も None を返す
        """
        mapping = self._resolutions.get(common_kind)
        if mapping is None:
            return None
        return mapping.get(domain)


# シングルトンインスタンス
workload_kind_registry = WorkloadKindRegistry()
