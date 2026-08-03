from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

DARK_MODE_STATE_KEY = "bridgr_dark_mode"

_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
_LOGO_PATH = _ASSETS_DIR / "bridgr_logo_dark.png"

# Token values shared between light and dark mode. Selectors throughout the
# injected stylesheet reference these custom properties instead of literal
# colors, so the two dicts below are the only place a "theme" is defined.
_LIGHT_TOKENS = {
    "navy-900": "#0c1a38",
    "navy-800": "#112244",
    "navy-700": "#16264d",
    "cyan-500": "#14c4e0",
    "slate-50": "#f6f8fb",
    "slate-100": "#eef1f6",
    "slate-200": "#dee3ec",
    "slate-500": "#687288",
    "slate-700": "#2e3a4f",
    "slate-900": "#101725",
    "surface-card": "#ffffff",
    "tabs-bg": "rgba(255, 255, 255, 0.75)",
    "app-bg-from": "#f9fbfe",
    "app-bg-to": "#f6f8fb",
    "app-glow": "rgba(20, 196, 224, 0.10)",
    "success-bg": "#e2f4ec",
    "warning-bg": "#fbeed6",
    "danger-bg": "#f8e3e1",
    "info-bg": "#dbf6fb",
    "shadow-sm": "0 10px 30px rgba(12, 26, 56, 0.06)",
    "shadow-focus": "0 0 0 3px rgba(20, 196, 224, 0.25)",
}

_DARK_TOKENS = {
    "navy-900": "#0a1226",
    "navy-800": "#101d3a",
    "navy-700": "#18294f",
    "cyan-500": "#2fd6ef",
    "slate-50": "#e7ebf3",
    "slate-100": "#18294a",
    "slate-200": "#28395c",
    "slate-500": "#9aa7c4",
    "slate-700": "#c7cee3",
    "slate-900": "#f4f6fb",
    "surface-card": "#101d3a",
    "tabs-bg": "rgba(16, 29, 58, 0.75)",
    "app-bg-from": "#0a1226",
    "app-bg-to": "#0c1a38",
    "app-glow": "rgba(20, 196, 224, 0.14)",
    "success-bg": "rgba(31, 157, 107, 0.18)",
    "warning-bg": "rgba(217, 138, 31, 0.20)",
    "danger-bg": "rgba(192, 57, 43, 0.22)",
    "info-bg": "rgba(20, 196, 224, 0.16)",
    "shadow-sm": "0 10px 30px rgba(0, 0, 0, 0.35)",
    "shadow-focus": "0 0 0 3px rgba(47, 214, 239, 0.30)",
}

_DARK_MODE_WIDGET_OVERRIDES = """
        .stApp, .stApp p, .stApp li, .stApp label, .stMarkdown, [data-testid="stCaptionContainer"] {
            color: var(--bridgr-slate-700);
        }

        [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            background: transparent;
        }

        .stTextInput input,
        .stTextArea textarea,
        .stNumberInput input,
        .stSelectbox div[data-baseweb="select"] > div,
        .stMultiSelect div[data-baseweb="select"] {
            background: var(--bridgr-surface-card) !important;
            color: var(--bridgr-slate-900) !important;
            border-color: var(--bridgr-slate-200) !important;
        }

        div[data-baseweb="popover"] li,
        div[data-baseweb="popover"] div[role="listbox"] {
            background: var(--bridgr-surface-card);
            color: var(--bridgr-slate-900);
        }

        [data-testid="stForm"] {
            background: transparent;
            border-color: var(--bridgr-slate-200);
        }

        [data-testid="stFileUploaderDropzone"] {
            background: var(--bridgr-slate-100);
            border-color: var(--bridgr-slate-200);
        }

        .stApp code {
            background: var(--bridgr-slate-100);
            color: var(--bridgr-slate-700);
        }
"""


def _build_theme_stylesheet(dark_mode: bool) -> str:
    tokens = _DARK_TOKENS if dark_mode else _LIGHT_TOKENS
    root_vars = "\n".join(f"            --bridgr-{name}: {value};" for name, value in tokens.items())
    widget_overrides = _DARK_MODE_WIDGET_OVERRIDES if dark_mode else ""

    return f"""
        <style>
        :root {{
{root_vars}
            --bridgr-radius-md: 8px;
            --bridgr-radius-lg: 14px;
        }}

        .stApp {{
            background:
                radial-gradient(circle at top right, var(--bridgr-app-glow), transparent 18%),
                linear-gradient(180deg, var(--bridgr-app-bg-from) 0%, var(--bridgr-app-bg-to) 100%);
            color: var(--bridgr-slate-900);
        }}

        .block-container {{
            padding-top: 3rem;
            padding-bottom: 2rem;
        }}

        h1, h2, h3, h4 {{
            color: var(--bridgr-navy-900);
            letter-spacing: -0.02em;
        }}

        div[data-testid="stTabs"] {{
            background: var(--bridgr-tabs-bg);
            border: 1px solid var(--bridgr-slate-200);
            border-radius: var(--bridgr-radius-lg);
            padding: 0.5rem;
            box-shadow: var(--bridgr-shadow-sm);
            backdrop-filter: blur(10px);
        }}

        button[data-baseweb="tab"] {{
            border-radius: 10px;
            padding: 0.5rem 0.9rem;
            color: var(--bridgr-slate-700);
        }}

        button[data-baseweb="tab"][aria-selected="true"] {{
            background: rgba(20, 196, 224, 0.12);
            color: var(--bridgr-cyan-500);
        }}

        .stButton > button,
        .stDownloadButton > button {{
            border-radius: var(--bridgr-radius-md);
            border: 1px solid var(--bridgr-slate-200);
            box-shadow: none;
        }}

        .stButton > button[kind="primary"] {{
            background: var(--bridgr-navy-700);
            border-color: var(--bridgr-navy-700);
            color: white;
        }}

        .stButton > button:hover,
        .stDownloadButton > button:hover {{
            border-color: var(--bridgr-cyan-500);
            color: var(--bridgr-cyan-500);
        }}

        .stTextInput input:focus,
        .stTextArea textarea:focus,
        .stSelectbox div[data-baseweb="select"]:focus-within,
        .stMultiSelect div[data-baseweb="select"]:focus-within,
        .stNumberInput input:focus {{
            border-color: var(--bridgr-cyan-500) !important;
            box-shadow: var(--bridgr-shadow-focus) !important;
        }}

        div[data-testid="stMetric"] {{
            background: var(--bridgr-surface-card);
            border: 1px solid var(--bridgr-slate-200);
            border-radius: var(--bridgr-radius-md);
            padding: 0.9rem 1rem;
            box-shadow: var(--bridgr-shadow-sm);
        }}

        div[data-testid="stExpander"] {{
            border: 1px solid var(--bridgr-slate-200);
            border-radius: var(--bridgr-radius-md);
            background: var(--bridgr-surface-card);
            box-shadow: var(--bridgr-shadow-sm);
        }}

        div[data-testid="stDataFrame"],
        div[data-testid="stTable"] {{
            border: 1px solid var(--bridgr-slate-200);
            border-radius: var(--bridgr-radius-md);
            overflow: hidden;
            background: var(--bridgr-surface-card);
        }}

        div[data-testid="stChatMessage"] {{
            border: 1px solid var(--bridgr-slate-200);
            border-radius: var(--bridgr-radius-md);
            background: var(--bridgr-surface-card);
            box-shadow: var(--bridgr-shadow-sm);
            padding: 0.4rem 0.2rem;
        }}

        div[data-testid="stAlert"] {{
            border-radius: var(--bridgr-radius-md);
            border-width: 1px;
        }}

        .st-key-bridgr-app-header {{
            padding: 0.9rem 1.25rem;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, var(--bridgr-navy-900), var(--bridgr-navy-700));
            border-radius: 16px;
            color: white;
            box-shadow: 0 18px 40px rgba(12, 26, 56, 0.18);
        }}

        .st-key-bridgr-app-header {{
            position: relative;
        }}

        .st-key-bridgr-app-header p {{
            margin: 0;
        }}

        .bridgr-app-header__row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1.5rem;
            padding-right: 12rem;
            min-height: 38px;
        }}

        .bridgr-app-header__logo {{
            height: 38px;
            width: auto;
            display: block;
        }}

        .bridgr-app-header__meta {{
            text-align: right;
            font-size: 0.9rem;
            color: rgba(255, 255, 255, 0.82);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .st-key-bridgr-dark-toggle {{
            position: absolute;
            top: 50%;
            right: 1.25rem;
            transform: translateY(-50%);
            width: fit-content;
            background: rgba(255, 255, 255, 0.14);
            border: 1px solid rgba(255, 255, 255, 0.32);
            border-radius: 999px;
            padding: 0.3rem 0.9rem;
        }}

        .st-key-bridgr-dark-toggle div[data-testid="stToggle"] label {{
            gap: 0.5rem;
        }}

        .st-key-bridgr-dark-toggle div[data-testid="stToggle"] p {{
            color: rgba(255, 255, 255, 0.9);
            font-size: 0.82rem;
        }}

        .st-key-bridgr-dark-toggle [data-baseweb="checkbox"] span:first-child {{
            background: rgba(255, 255, 255, 0.35) !important;
            border: 1px solid rgba(255, 255, 255, 0.6) !important;
        }}

        .st-key-bridgr-dark-toggle [data-baseweb="checkbox"] input:checked ~ span:first-child {{
            background: var(--bridgr-cyan-500) !important;
            border-color: var(--bridgr-cyan-500) !important;
        }}

        .bridgr-page-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 1rem;
            margin: 0.75rem 0 1rem;
            padding: 1rem 1.1rem;
            border: 1px solid var(--bridgr-slate-200);
            border-radius: 12px;
            background: var(--bridgr-surface-card);
            box-shadow: var(--bridgr-shadow-sm);
        }}

        .bridgr-page-header__eyebrow {{
            color: var(--bridgr-cyan-500);
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.72rem;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }}

        .bridgr-page-header__title {{
            margin: 0;
            color: var(--bridgr-navy-900);
            font-size: 1.5rem;
            font-weight: 700;
        }}

        .bridgr-page-header__subtitle {{
            margin: 0.15rem 0 0;
            color: var(--bridgr-slate-500);
        }}

        .bridgr-page-header__meta {{
            margin-top: 0.2rem;
            color: var(--bridgr-slate-500);
            font-size: 0.88rem;
            white-space: nowrap;
        }}
        {widget_overrides}
        </style>
        """


def inject_global_styles(dark_mode: bool = False) -> None:
    st.markdown(_build_theme_stylesheet(dark_mode), unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _load_logo_data_uri() -> str:
    encoded = base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def get_dark_mode_preference() -> bool:
    """Read the session-scoped dark-mode toggle, seeding it to light mode on first use."""
    st.session_state.setdefault(DARK_MODE_STATE_KEY, False)
    return bool(st.session_state[DARK_MODE_STATE_KEY])


def render_app_header() -> None:
    with st.container(key="bridgr-app-header"):
        st.markdown(
            f"""
            <div class="bridgr-app-header__row">
                <img class="bridgr-app-header__logo" src="{_load_logo_data_uri()}" alt="BRIDGR" />
                <div class="bridgr-app-header__meta">Wissensgraph aus Prozessen, CMDB und Architekturwissen</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.container(key="bridgr-dark-toggle"):
            st.toggle("Dark", key=DARK_MODE_STATE_KEY)


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
