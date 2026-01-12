"""
LLM呼び出しの単一入口を提供する。

入出力: prompt(str) -> str の生成結果を返す。
制約: SDK直呼びを避け、VertexGeminiClientに集約する。

Note:
    - 初回呼び出し時のみクライアントを初期化する
"""

from __future__ import annotations

from .llm_client_vertex import VertexGeminiClient

# LLMクライアントのシングルトン参照（遅延初期化）
_client: VertexGeminiClient | None = None


def llm_generate(prompt: str) -> str:
    """LLM 呼び出しの単一入口。

    Args:
        prompt: LLMに渡すプロンプト

    Returns:
        生成テキスト

    Variables:
        _client:
            共有クライアント（初回呼び出し時に生成される）。

    Raises:
        Exception: SDKの例外をそのまま送出する

    Note:
        - プロンプトや生応答をログに保存しない
        - 初回呼び出し時のみクライアントを初期化する
    """
    global _client
    if _client is None:
        _client = VertexGeminiClient()
    return _client.generate_text(prompt)
