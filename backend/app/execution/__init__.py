"""
実行計画・実行エンジンパッケージ。

本パッケージは ExecutionPlanner / WorkloadRunner / ApprovalCheck を提供する。
Agent 層（app/agent/）とは分離され、BusinessDefinition の実行責務を担う。

Note:
    - Agent 層のコードには依存しない（スキーマのみ参照）
    - 外部 API 呼び出しは Connector 層に委譲する
"""
