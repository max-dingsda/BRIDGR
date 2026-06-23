from __future__ import annotations

import streamlit as st


def inject_global_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bridgr-navy-900: #0c1a38;
            --bridgr-navy-800: #112244;
            --bridgr-navy-700: #16264d;
            --bridgr-cyan-500: #14c4e0;
            --bridgr-slate-50: #f6f8fb;
            --bridgr-slate-100: #eef1f6;
            --bridgr-slate-200: #dee3ec;
            --bridgr-slate-500: #687288;
            --bridgr-slate-700: #2e3a4f;
            --bridgr-slate-900: #101725;
            --bridgr-success-bg: #e2f4ec;
            --bridgr-warning-bg: #fbeed6;
            --bridgr-danger-bg: #f8e3e1;
            --bridgr-info-bg: #dbf6fb;
            --bridgr-shadow-sm: 0 10px 30px rgba(12, 26, 56, 0.06);
            --bridgr-shadow-focus: 0 0 0 3px rgba(20, 196, 224, 0.25);
            --bridgr-radius-md: 8px;
            --bridgr-radius-lg: 14px;
        }

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(20, 196, 224, 0.10), transparent 18%),
                linear-gradient(180deg, #f9fbfe 0%, var(--bridgr-slate-50) 100%);
            color: var(--bridgr-slate-900);
        }

        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }

        h1, h2, h3, h4 {
            color: var(--bridgr-navy-900);
            letter-spacing: -0.02em;
        }

        div[data-testid="stTabs"] {
            background: rgba(255, 255, 255, 0.75);
            border: 1px solid var(--bridgr-slate-200);
            border-radius: var(--bridgr-radius-lg);
            padding: 0.5rem;
            box-shadow: var(--bridgr-shadow-sm);
            backdrop-filter: blur(10px);
        }

        button[data-baseweb="tab"] {
            border-radius: 10px;
            padding: 0.5rem 0.9rem;
            color: var(--bridgr-slate-700);
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            background: rgba(17, 34, 68, 0.08);
            color: var(--bridgr-navy-800);
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: var(--bridgr-radius-md);
            border: 1px solid var(--bridgr-slate-200);
            box-shadow: none;
        }

        .stButton > button[kind="primary"] {
            background: var(--bridgr-navy-700);
            border-color: var(--bridgr-navy-700);
            color: white;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            border-color: var(--bridgr-cyan-500);
            color: var(--bridgr-navy-800);
        }

        .stTextInput input:focus,
        .stTextArea textarea:focus,
        .stSelectbox div[data-baseweb="select"]:focus-within,
        .stMultiSelect div[data-baseweb="select"]:focus-within,
        .stNumberInput input:focus {
            border-color: var(--bridgr-cyan-500) !important;
            box-shadow: var(--bridgr-shadow-focus) !important;
        }

        div[data-testid="stMetric"] {
            background: white;
            border: 1px solid var(--bridgr-slate-200);
            border-radius: var(--bridgr-radius-md);
            padding: 0.9rem 1rem;
            box-shadow: var(--bridgr-shadow-sm);
        }

        div[data-testid="stExpander"] {
            border: 1px solid var(--bridgr-slate-200);
            border-radius: var(--bridgr-radius-md);
            background: white;
            box-shadow: var(--bridgr-shadow-sm);
        }

        div[data-testid="stDataFrame"],
        div[data-testid="stTable"] {
            border: 1px solid var(--bridgr-slate-200);
            border-radius: var(--bridgr-radius-md);
            overflow: hidden;
            background: white;
        }

        div[data-testid="stChatMessage"] {
            border: 1px solid var(--bridgr-slate-200);
            border-radius: var(--bridgr-radius-md);
            background: white;
            box-shadow: var(--bridgr-shadow-sm);
            padding: 0.4rem 0.2rem;
        }

        div[data-testid="stAlert"] {
            border-radius: var(--bridgr-radius-md);
            border-width: 1px;
        }

        .bridgr-app-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1.5rem;
            padding: 1.1rem 1.25rem;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, var(--bridgr-navy-900), var(--bridgr-navy-700));
            border-radius: 16px;
            color: white;
            box-shadow: 0 18px 40px rgba(12, 26, 56, 0.18);
        }

        .bridgr-app-header__brand {
            display: flex;
            align-items: center;
            gap: 0.9rem;
        }

        .bridgr-app-header__logo {
            width: 46px;
            height: 46px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: radial-gradient(circle, rgba(20, 196, 224, 0.95) 0%, rgba(20, 196, 224, 0.25) 45%, rgba(20, 196, 224, 0.08) 100%);
            box-shadow: 0 0 30px rgba(20, 196, 224, 0.35);
            font-weight: 700;
            color: var(--bridgr-navy-900);
        }

        .bridgr-app-header__title {
            margin: 0;
            font-size: 1.45rem;
            font-weight: 700;
        }

        .bridgr-app-header__subtitle,
        .bridgr-page-header__subtitle {
            margin: 0.15rem 0 0;
            color: rgba(255, 255, 255, 0.78);
            font-size: 0.96rem;
        }

        .bridgr-app-header__meta {
            text-align: right;
            font-size: 0.9rem;
            color: rgba(255, 255, 255, 0.82);
        }

        .bridgr-page-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 1rem;
            margin: 0.75rem 0 1rem;
            padding: 1rem 1.1rem;
            border: 1px solid var(--bridgr-slate-200);
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.88);
            box-shadow: var(--bridgr-shadow-sm);
        }

        .bridgr-page-header__eyebrow {
            color: var(--bridgr-cyan-500);
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.72rem;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }

        .bridgr-page-header__title {
            margin: 0;
            color: var(--bridgr-navy-900);
            font-size: 1.5rem;
            font-weight: 700;
        }

        .bridgr-page-header__subtitle {
            color: var(--bridgr-slate-500);
        }

        .bridgr-page-header__meta {
            margin-top: 0.2rem;
            color: var(--bridgr-slate-500);
            font-size: 0.88rem;
            white-space: nowrap;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_app_header() -> None:
    st.markdown(
        """
        <div class="bridgr-app-header">
            <div class="bridgr-app-header__brand">
                <div class="bridgr-app-header__logo">B</div>
                <div>
                    <p class="bridgr-app-header__title">BRIDGR</p>
                    <p class="bridgr-app-header__subtitle">Connecting Enterprise Knowledge</p>
                </div>
            </div>
            <div class="bridgr-app-header__meta">
                Wissensgraph aus Prozessen, CMDB und Architekturwissen
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str, meta: str | None = None) -> None:
    meta_html = f'<div class="bridgr-page-header__meta">{meta}</div>' if meta else ""
    st.markdown(
        f"""
        <div class="bridgr-page-header">
            <div>
                <div class="bridgr-page-header__eyebrow">BRIDGR Workspace</div>
                <h2 class="bridgr-page-header__title">{title}</h2>
                <p class="bridgr-page-header__subtitle">{subtitle}</p>
            </div>
            {meta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
