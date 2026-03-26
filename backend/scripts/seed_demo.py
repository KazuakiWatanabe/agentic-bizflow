"""
デモ用データベースのセットアップスクリプト。

本モジュールは dev.db をリセットし、Alembic マイグレーションを適用して
クリーンなデモ環境を構築する。デモ実行後の結果検証機能も提供する。

入出力: コマンドライン実行 → dev.db のリセットとデモ手順の表示。
制約: 本番環境では使用しないこと。

Note:
    - dev.db が存在する場合は削除してから再作成する
    - alembic upgrade head でマイグレーションを適用する
    - verify_demo_results() でデモ実行後の整合性を確認する
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

# backend ディレクトリのパス
BACKEND_DIR = Path(__file__).resolve().parent.parent

# dev.db のパス
DB_PATH = BACKEND_DIR / "dev.db"


def reset_database() -> None:
    """dev.db を削除し、Alembic マイグレーションを再適用する。

    Note:
        - dev.db が存在しない場合は削除をスキップする
        - alembic upgrade head でテーブルを作成する
    """
    # 既存の dev.db を削除
    if DB_PATH.exists():
        os.remove(DB_PATH)
        print(f"[OK] 既存の dev.db を削除しました: {DB_PATH}")
    else:
        print("[INFO] dev.db は存在しません（新規作成します）")

    # Alembic マイグレーション適用
    print("[INFO] Alembic マイグレーションを適用中...")
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"[ERROR] Alembic マイグレーションに失敗しました:\n{result.stderr}")
        sys.exit(1)

    print("[OK] Alembic マイグレーション適用完了")


def print_demo_instructions() -> None:
    """デモシナリオの手順を表示する。

    Note:
        - 各ステップは API エンドポイント経由で実行する
        - dry-run → 承認 → 本実行 の 3 ステップフロー
    """
    instructions = """
============================================================
  Agentic BizFlow デモシナリオ
============================================================

【前提】
  サーバーを起動してください:
    cd backend && python -m uvicorn app.main:app --reload --port 8080

【Step 1: 計画生成（POST /api/plan）】
  自然文の業務定義から実行計画を生成します。

  curl -X POST http://localhost:8080/api/plan \\
    -H "Content-Type: application/json" \\
    -d '{
      "definition": {
        "title": "新規会員VIPタグ付与",
        "tasks": [
          {
            "name": "VIPタグ付与",
            "steps": ["対象者にVIPタグを付与する"],
            "role": "担当者"
          }
        ],
        "roles": [{"name": "担当者", "responsibilities": ["タグ管理"]}]
      }
    }'

【Step 2: Dry-Run（POST /api/dry-run）】
  副作用なしで実行プレビューを確認します。
  Step 1 のレスポンスから plan を取得し、リクエストボディに含めます。

【Step 3: 本実行（POST /api/execute）】
  承認付きで本実行します。
  curl -X POST http://localhost:8080/api/execute \\
    -H "Content-Type: application/json" \\
    -d '{"plan": <Step 1 の plan>, "approved": true}'

【Step 4: 状態確認】
  各状態 API でワークロードの状態を確認します。

  GET http://localhost:8080/api/workloads/summary
  GET http://localhost:8080/api/workloads/scenarios
  GET http://localhost:8080/api/workloads/broadcasts
  GET http://localhost:8080/api/workloads/reminders
  GET http://localhost:8080/api/workers/status

【Step 5: 履歴確認】
  実行履歴を確認します。

  GET http://localhost:8080/api/executions
  GET http://localhost:8080/api/plans

============================================================
"""
    print(instructions)


def verify_demo_results(db_path: str = str(DB_PATH)) -> dict:
    """デモ実行後の DB レコード件数を検証する。

    Args:
        db_path: 検証対象の SQLite DB ファイルパス

    Returns:
        テーブルごとのレコード件数 dict

    Note:
        - 期待される最低件数を確認する
        - デモシナリオの実行後に呼び出す想定
    """
    if not os.path.exists(db_path):
        print(f"[ERROR] DB ファイルが見つかりません: {db_path}")
        return {}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 検証対象テーブルと期待される最低件数
    tables_to_check = [
        "execution_plans",
        "execution_results",
        "step_results",
        "tags",
        "tag_assignments",
        "scenarios",
        "scenario_steps",
        "scenario_enrollments",
        "broadcasts",
        "reminders",
        "reminder_steps",
        "reminder_enrollments",
        "reminder_deliveries",
        "approval_requests",
        "processed_idempotency_keys",
        "execution_audit_logs",
        "worker_task_logs",
        "domain_configs",
        "email_broadcasts",
        "email_templates",
    ]

    # 各テーブルのレコード件数を取得
    counts = {}
    for table in tables_to_check:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
            count = cursor.fetchone()[0]
            counts[table] = count
        except sqlite3.OperationalError:
            counts[table] = -1  # テーブルが存在しない場合

    conn.close()

    # 結果表示
    print("\n============================================================")
    print("  デモ結果検証")
    print("============================================================")
    for table, count in counts.items():
        # ステータスアイコン
        status = "OK" if count >= 0 else "MISSING"
        print(f"  [{status}] {table}: {count} 件")

    # execution_plans が 1 件以上あればデモ実行済みと判断
    if counts.get("execution_plans", 0) >= 1:
        print("\n  [OK] デモシナリオの実行が確認されました")
    else:
        print("\n  [INFO] まだデモシナリオが実行されていません")

    print("============================================================\n")

    return counts


def main() -> None:
    """メインエントリポイント。

    Note:
        - --verify オプションで検証のみ実行可能
    """
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        verify_demo_results()
        return

    print("============================================================")
    print("  Agentic BizFlow デモ環境セットアップ")
    print("============================================================\n")

    reset_database()
    print_demo_instructions()

    print("[INFO] デモ実行後に検証するには:")
    print("  python scripts/seed_demo.py --verify")


if __name__ == "__main__":
    main()
