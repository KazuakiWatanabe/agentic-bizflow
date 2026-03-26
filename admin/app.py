"""
Agentic BizFlow 管理 UI（Streamlit）。

本モジュールはバックエンド API を呼び出し、
workload 状態・実行履歴・承認フローを可視化する管理ダッシュボードを提供する。

起動: streamlit run admin/app.py
制約: バックエンドが http://localhost:8080 で起動していること。
"""

import json
from datetime import datetime

import requests
import streamlit as st

# バックエンド URL
API_BASE = st.sidebar.text_input("Backend URL", value="http://localhost:8080")

st.set_page_config(page_title="Agentic BizFlow Admin", layout="wide")
st.title("Agentic BizFlow 管理ダッシュボード")


def api_get(path: str):
    """API GET リクエストを送信する。"""
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API エラー: {e}")
        return None


def api_post(path: str, body=None):
    """API POST リクエストを送信する。"""
    try:
        r = requests.post(f"{API_BASE}{path}", json=body, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API エラー: {e}")
        return None


# --- サイドバー ---
st.sidebar.markdown("---")
st.sidebar.header("ナビゲーション")
page = st.sidebar.radio(
    "ページ",
    [
        "Workload サマリー",
        "実行履歴",
        "承認管理",
        "Worker 状態",
        "ドメイン管理",
        "業務文章変換",
    ],
)

# ============================================================
# Workload サマリー
# ============================================================
if page == "Workload サマリー":
    st.header("Workload サマリー")
    data = api_get("/api/workloads/summary")
    if data:
        col1, col2, col3, col4 = st.columns(4)
        s = data.get("scenarios", {})
        b = data.get("broadcasts", {})
        r = data.get("reminders", {})
        t = data.get("tags", {})

        with col1:
            st.metric("シナリオ", s.get("total", 0))
            st.caption(
                f"active: {s.get('active_enrollments', 0)} / "
                f"completed: {s.get('completed_enrollments', 0)}"
            )
        with col2:
            st.metric("配信", b.get("sent", 0))
            st.caption(
                f"scheduled: {b.get('scheduled', 0)} / "
                f"failed: {b.get('failed', 0)}"
            )
        with col3:
            st.metric("リマインダー", r.get("total", 0))
            st.caption(
                f"active: {r.get('active_enrollments', 0)} / "
                f"completed: {r.get('completed_enrollments', 0)}"
            )
        with col4:
            st.metric("タグ", t.get("total", 0))
            st.caption(f"付与数: {t.get('total_assignments', 0)}")

    # 詳細テーブル
    st.subheader("Broadcasts")
    bc_data = api_get("/api/workloads/broadcasts")
    if bc_data:
        st.json(bc_data)

    st.subheader("Scenarios")
    sc_data = api_get("/api/workloads/scenarios")
    if sc_data:
        st.json(sc_data)

# ============================================================
# 実行履歴
# ============================================================
elif page == "実行履歴":
    st.header("実行履歴")
    data = api_get("/api/executions")
    if data:
        st.write(f"Total: {data.get('total', 0)} 件")
        for ex in data.get("executions", []):
            with st.expander(
                f"{ex.get('started_at', '')} - {ex['status']} "
                f"({ex.get('step_count', 0)} steps)"
            ):
                detail = api_get(f"/api/executions/{ex['execution_id']}")
                if detail:
                    st.json(detail)

    # Plan 一覧
    st.subheader("保存済み Plan")
    plans = api_get("/api/plans")
    if plans:
        st.write(f"Total: {plans.get('total', 0)} 件")
        for p in plans.get("plans", []):
            st.write(
                f"- {p['plan_id']} | {p.get('status', '')} | "
                f"{p.get('summary', '')}"
            )

# ============================================================
# 承認管理
# ============================================================
elif page == "承認管理":
    st.header("承認管理")
    tab1, tab2 = st.tabs(["承認待ち", "全件"])

    with tab1:
        data = api_get("/api/approvals?status=pending")
        if data:
            approvals = data.get("approvals", [])
            if not approvals:
                st.info("承認待ちはありません。")
            for a in approvals:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(
                        f"Plan: {a['plan_id']} | "
                        f"Requested: {a.get('requested_at', '')}"
                    )
                with col2:
                    if st.button("承認", key=f"approve_{a['id']}"):
                        api_post(f"/api/approvals/{a['id']}/approve")
                        st.rerun()
                with col3:
                    if st.button("却下", key=f"reject_{a['id']}"):
                        api_post(f"/api/approvals/{a['id']}/reject")
                        st.rerun()

    with tab2:
        data = api_get("/api/approvals")
        if data:
            for a in data.get("approvals", []):
                status_color = {
                    "pending": ":orange[pending]",
                    "approved": ":green[approved]",
                    "rejected": ":red[rejected]",
                }.get(a["status"], a["status"])
                st.write(
                    f"- {a['plan_id']} | {status_color} | "
                    f"{a.get('decided_at', '-')}"
                )

# ============================================================
# Worker 状態
# ============================================================
elif page == "Worker 状態":
    st.header("Worker 状態")
    data = api_get("/api/workers/status")
    if data:
        enabled = data.get("scheduler_enabled", False)
        st.metric("Scheduler", "有効" if enabled else "無効")

        workers = data.get("workers", [])
        if not workers:
            st.info("Worker の実行ログがありません。")
        for w in workers:
            status_icon = {"completed": "OK", "failed": "NG", "running": "..."}.get(
                w.get("status", ""), "?"
            )
            st.write(
                f"- {w['task_name']} | {status_icon} | "
                f"processed: {w.get('processed_count', 0)} | "
                f"errors: {w.get('error_count', 0)} | "
                f"last: {w.get('last_run', '-')}"
            )

# ============================================================
# ドメイン管理
# ============================================================
elif page == "ドメイン管理":
    st.header("ドメイン管理")

    # Workload Kinds
    st.subheader("Workload Kinds")
    kinds_data = api_get("/api/workload-kinds")
    if kinds_data:
        for k in kinds_data.get("kinds", []):
            st.write(
                f"- `{k['kind']}` | {k['domain']} | "
                f"{k.get('description', '')} | "
                f"approval: {k.get('requires_approval', 'none')}"
            )

    # Domain Config
    st.subheader("Domain 設定")
    domains_data = api_get("/api/domains")
    if domains_data:
        for d in domains_data.get("domains", []):
            enabled = d.get("is_enabled", False)
            icon = "ON" if enabled else "OFF"
            st.write(
                f"- {d['domain']} ({d.get('display_name', '')}) | {icon}"
            )

# ============================================================
# 業務文章変換
# ============================================================
elif page == "業務文章変換":
    st.header("業務文章変換")
    text = st.text_area(
        "業務文章を入力",
        value="VIPタグを付与し、全員に告知メッセージを一斉配信する",
        height=100,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("変換"):
            data = api_post("/api/convert", {"text": text})
            if data:
                st.session_state["definition"] = data.get("definition", {})
                st.session_state["agent_logs"] = data.get("agent_logs", [])
                st.json(data["definition"])

    with col2:
        if st.button("実行計画を生成") and "definition" in st.session_state:
            data = api_post(
                "/api/plan", {"definition": st.session_state["definition"]}
            )
            if data:
                st.session_state["plan"] = data.get("plan", {})
                st.json(data["plan"])

    if "plan" in st.session_state:
        st.subheader("実行")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Dry-run"):
                data = api_post(
                    "/api/dry-run", {"plan": st.session_state["plan"]}
                )
                if data:
                    st.json(data["preview"])
        with col2:
            if st.button("本実行"):
                data = api_post(
                    "/api/execute",
                    {"plan": st.session_state["plan"], "approved": True},
                )
                if data:
                    st.json(data["result"])
