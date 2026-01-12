"""
Vertex AI 経由で Gemini を呼び出す最小クライアントを提供する。

入出力: 環境変数を読み取り、prompt(str) -> str の生成を行う。
制約: GCP_PROJECT_ID が必須で、ログにプロンプトや生応答を保存しない。

Note:
    - GCP_PROJECT_ID が未設定の場合は RuntimeError を送出する
"""

from __future__ import annotations

import os

from google import genai


class VertexGeminiClient:
    """Vertex AI 経由で Gemini を呼び出すクライアント。

    主なメソッド: generate_text()
    制約: 環境変数に依存し、プロンプトや生応答はログに保存しない。

    Note:
        - GCP_PROJECT_ID が未設定の場合は初期化に失敗する
    """

    def __init__(self) -> None:
        """クライアントを初期化する。

        Args:
            None

        Returns:
            None

        Variables:
            project:
                GCPのプロジェクトID（必須）。
            location:
                Vertex AI のリージョン設定。
            self._client:
                Vertex AI 用のSDKクライアント。
            self._model:
                使用するGeminiモデル名。

        Raises:
            RuntimeError: GCP_PROJECT_ID が未設定の場合に発生

        Note:
            - GCP_LOCATION と GEMINI_MODEL は未設定時に既定値を使用する
        """
        project = os.getenv("GCP_PROJECT_ID")
        location = os.getenv("GCP_LOCATION", "asia-northeast1")
        if not project:
            raise RuntimeError("GCP_PROJECT_ID is required")

        self._client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
        )
        self._model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    def generate_text(self, prompt: str) -> str:
        """テキスト生成を実行する。

        Args:
            prompt: LLMに渡すプロンプト

        Returns:
            生成テキスト（空文字の場合もある）

        Variables:
            resp:
                Vertex AI の生成レスポンス。

        Raises:
            Exception: SDKの例外をそのまま送出する

        Note:
            - 生のプロンプトや応答をログ出力しない
        """
        resp = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
        )
        return resp.text or ""
