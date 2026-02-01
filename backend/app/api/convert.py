"""
業務文章を業務定義に変換するAPIルータを提供する。

入出力: ConvertRequest を受け取り、ConvertResponse を返す。
制約: agentic-core の Orchestrator を使用し、要約ログのみ返す。

Note:
    - text が空の場合は 400 を返す
    - Orchestrator の ValueError は 422 に変換する
    - 想定外の例外は 500 で簡易メッセージを返す
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict

from app.agent.orchestrator import Orchestrator

router = APIRouter()


class ConvertRequest(BaseModel):
    """変換APIの入力モデル。

    業務文章 text と任意の context を受け取る。
    主要な役割はPydanticによる型検証である。
    主なメソッド: なし（データ保持のみ）
    制約: extra fields は受け付けない。

    Variables:
        text:
            変換対象の業務文章。
        context:
            任意の補助情報（現在の実装では未使用）。

    Note:
        - context は任意で、現在の実装では処理に影響しない
    """

    model_config = ConfigDict(extra="forbid")

    text: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class ConvertResponse(BaseModel):
    """変換APIのレスポンスモデル。

    BusinessDefinition を dict として返し、agent_logs と meta を含む。
    主要な役割はレスポンス形式の固定化である。
    主なメソッド: なし（データ保持のみ）
    制約: extra fields は受け付けない。

    Variables:
        definition:
            業務定義のdict表現。
        agent_logs:
            各Agentの要約ログ一覧。
        meta:
            retries などのメタ情報。
            token_present はAuthorizationヘッダからIDトークンの有無を示す。
            actions と splitter_version は事前分割の結果を示す。
    """

    model_config = ConfigDict(extra="forbid")

    definition: Dict[str, Any]
    agent_logs: List[Dict[str, Any]]
    meta: Dict[str, Any]


def _is_bearer_token_present(authorization: Optional[str]) -> bool:
    """AuthorizationヘッダにBearerトークンが含まれるかを判定する。

    Args:
        authorization: Authorization ヘッダの値

    Returns:
        Bearer トークンが存在する場合は True

    Variables:
        normalized:
            Authorization ヘッダの前後空白を除去した文字列。
        token:
            "Bearer " 以降のトークン文字列。

    Note:
        - Authorization が空または Bearer 形式でない場合は False を返す
    """
    if not authorization:
        return False
    normalized = authorization.strip()
    if not normalized:
        return False
    if not normalized.lower().startswith("bearer "):
        return False
    token = normalized[7:].strip()
    return bool(token)


@router.post("/convert", response_model=ConvertResponse)
def convert(
    request: ConvertRequest,
    authorization: Optional[str] = Header(default=None),
) -> ConvertResponse:
    """業務文章を業務定義へ変換する。

    Args:
        request: 変換対象のテキストと任意コンテキスト
        authorization: Authorization ヘッダ（Bearer トークン想定）

    Returns:
        ConvertResponse: 業務定義と要約ログ、メタ情報

    Variables:
        text:
            前後空白を除去した入力文字列。
        token_present:
            Authorization ヘッダから判定したIDトークンの有無。
        orchestrator:
            Agentic変換の実行器。
        definition:
            変換後の業務定義（Pydanticモデル）。
        agent_logs:
            各Agentの要約ログ一覧。
        meta:
            retries などのメタ情報。
        definition_dict:
            definition を JSON 返却用にdict化した値。

    Raises:
        HTTPException: 入力不備や検証失敗、内部エラー時に発生

    Note:
        - text が空の場合は 400 を返す
        - ValueError は 422 に変換する
        - それ以外の例外は 500 を返す
        - Bearer トークンがある場合のみ meta に token_present を追加する
    """
    text = (request.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    orchestrator = Orchestrator()
    try:
        definition, agent_logs, meta = orchestrator.convert(text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="validation failed") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal server error") from exc

    token_present = _is_bearer_token_present(authorization)
    if token_present:
        meta = dict(meta)
        meta["token_present"] = True

    definition_dict = definition.model_dump()
    return ConvertResponse(
        definition=definition_dict,
        agent_logs=agent_logs,
        meta=meta,
    )
