"""Estilos de la aplicación (sistema de diseño). El color de marca sale de la configuración."""
import functools
import streamlit as st
from inventario.contexto import cfg


COLOR_BASE = "#EC3237"
BLOQUES = [
r"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"], .stMarkdown, div, button, input, select, textarea {
        font-family: 'Montserrat', sans-serif !important;
    }

    .stApp {
        background-color: #FAFAFA;
    }

    header[data-testid="stHeader"] {
        background-color: transparent !important;
        z-index: 100;
    }

    header[data-testid="stHeader"] button {
        color: #111827 !important;
    }

    .market-header {
        background-color: #FFFFFF;
        padding: 20px 24px;
        border-radius: 8px;
        border: 1px solid #E5E7EB;
        border-left: 4px solid #EC3237;
        margin-bottom: 24px;
    }
    .market-header h1 {
        color: #111827 !important;
        margin: 0;
        font-size: 1.3rem !important;
        font-weight: 600 !important;
        letter-spacing: -0.3px;
    }
    .market-header p {
        color: #6B7280;
        margin: 4px 0 0 0;
        font-size: 0.85rem;
        font-weight: 400;
    }

    .info-card {
        background-color: #FFFFFF;
        padding: 18px 20px;
        border-radius: 8px;
        border: 1px solid #E5E7EB;
        margin-bottom: 15px;
    }
    .info-label {
        color: #6B7280;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
    .info-value {
        color: #111827;
        font-size: 1.4rem;
        font-weight: 700;
        margin-top: 4px;
    }

    .stButton>button {
        background-color: #111827 !important;
        color: #FFFFFF !important;
        border-radius: 6px !important;
        border: none !important;
        font-weight: 500 !important;
        font-size: 0.82rem !important;
        height: 2.8em !important;
        transition: all 0.2s ease !important;
        letter-spacing: 0.3px;
    }
    .stButton>button:hover {
        background-color: #374151 !important;
    }

    .btn-ingreso > button {
        background-color: #00A959 !important;
    }
    .btn-ingreso > button:hover {
        background-color: #008847 !important;
    }

    .btn-salida > button {
        background-color: #EC3237 !important;
    }
    .btn-salida > button:hover {
        background-color: #D02429 !important;
    }

    [data-testid="stSidebar"] {
        background-color: #111827 !important;
        border-right: 1px solid #1F2937;
    }
    [data-testid="stSidebar"] * {
        color: #E5E7EB !important;
    }
    
    .btn-logout > button {
        background-color: transparent !important;
        border: 1px solid #374151 !important;
        color: #9CA3AF !important;
    }
    .btn-logout > button:hover {
        background-color: #1F2937 !important;
        color: #FFFFFF !important;
    }

    div[data-testid="stForm"], div[data-testid="stExpander"] {
        border-radius: 8px !important;
        border: 1px solid #E5E7EB !important;
        background-color: #FFFFFF !important;
        padding: 20px !important;
        box-shadow: none !important;
    }

    .app-footer {
        text-align: center;
        padding: 24px 10px 12px 10px;
        margin-top: 40px;
        border-top: 1px solid #E5E7EB;
        color: #6B7280;
        font-size: 0.8rem;
        line-height: 1.5;
    }
    .app-footer strong {
        color: #111827;
    }
</style>
""",
r"""
<style>
:root{
  --tp-red:#EC3237; --tp-red-dk:#C9262B; --tp-red-soft:#FDECEC;
  --tp-ink:#0F172A; --tp-ink-2:#334155; --tp-mute:#64748B;
  --tp-bg:#F3F4F7; --tp-surface:#FFFFFF; --tp-line:#E3E6EC;
  --tp-ok:#0B8F57; --tp-ok-soft:#E3F6EC; --tp-warn:#B45309; --tp-warn-soft:#FEF3C7;
  --tp-bad:#B42318; --tp-bad-soft:#FEE4E2; --tp-info:#1D4ED8; --tp-info-soft:#E0EAFF;
  --tp-r-sm:10px; --tp-r-md:14px; --tp-r-lg:20px;
  --tp-sh-1:0 1px 2px rgba(15,23,42,.05),0 1px 3px rgba(15,23,42,.04);
  --tp-sh-2:0 8px 24px -8px rgba(15,23,42,.14);
}
.stApp{background:var(--tp-bg);}
.block-container{max-width:1240px;padding-top:4.2rem;padding-bottom:3rem;}
#MainMenu,footer,[data-testid="stDecoration"],[data-testid="stAppDeployButton"],[data-testid="stMainMenu"],.stDeployButton{visibility:hidden;display:none;}
header[data-testid="stHeader"]{background:transparent!important;}
[data-testid="stToolbar"]{visibility:visible!important;display:flex!important;}
/* Botón para abrir el menú de vistas (siempre visible) */
[data-testid="stExpandSidebarButton"],[data-testid="stSidebarCollapsedControl"],[data-testid="collapsedControl"]{
  display:flex!important;visibility:visible!important;opacity:1!important;z-index:1000;
  position:fixed;top:12px;left:12px;width:46px;height:46px;align-items:center;justify-content:center;
  background:var(--tp-ink)!important;border-radius:14px;box-shadow:var(--tp-sh-2);}
[data-testid="stExpandSidebarButton"] *,[data-testid="stSidebarCollapsedControl"] *,[data-testid="collapsedControl"] *{color:#fff!important;fill:#fff!important;}
[data-testid="stExpandSidebarButton"]:hover,[data-testid="stSidebarCollapsedControl"]:hover{background:var(--tp-red)!important;}
[data-testid="stSidebarCollapseButton"] button,[data-testid="stSidebarCollapseButton"] *{color:#AEB8CC!important;}
h1,h2,h3,h4,h5{color:var(--tp-ink);letter-spacing:-.01em;}
h5{font-size:1.02rem!important;font-weight:650!important;margin:.4rem 0 .6rem!important;}
[data-testid="stMetricValue"],.info-value,.tp-kpi-val{font-variant-numeric:tabular-nums;}
:focus-visible{outline:3px solid rgba(236,50,55,.35)!important;outline-offset:2px;border-radius:8px;}

/* Encabezado de página */
.market-header{position:relative;background:var(--tp-surface);border:1px solid var(--tp-line);border-left:1px solid var(--tp-line);
  border-radius:var(--tp-r-lg);padding:22px 26px 20px;margin-bottom:22px;box-shadow:var(--tp-sh-1);}
.market-header::before{content:"";position:absolute;left:26px;top:0;width:36px;height:4px;background:var(--tp-red);border-radius:0 0 4px 4px;}
.market-header h1{font-size:1.45rem!important;font-weight:700!important;margin-top:6px!important;color:var(--tp-ink)!important;}
.market-header p{font-size:.9rem;color:var(--tp-mute);}

/* Tarjetas y contenedores */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]){border-radius:var(--tp-r-md);}
div[data-testid="stVerticalBlockBorderWrapper"]{border-color:var(--tp-line)!important;background:var(--tp-surface);box-shadow:var(--tp-sh-1);}
.info-card,.cal-card{border-radius:var(--tp-r-md)!important;border:1px solid var(--tp-line)!important;box-shadow:var(--tp-sh-1);}
div[data-testid="stForm"],div[data-testid="stExpander"]{border-radius:var(--tp-r-md)!important;border:1px solid var(--tp-line)!important;box-shadow:var(--tp-sh-1)!important;}
[data-testid="stMetric"]{background:var(--tp-surface);border:1px solid var(--tp-line);border-radius:var(--tp-r-md);padding:16px 18px;box-shadow:var(--tp-sh-1);}
[data-testid="stMetricLabel"] p{font-size:.78rem!important;font-weight:600;color:var(--tp-mute)!important;}
[data-testid="stMetricValue"]{font-weight:700;color:var(--tp-ink);}

/* Botones */
.stButton>button,.stDownloadButton>button,.stFormSubmitButton>button{min-height:46px;border-radius:var(--tp-r-sm)!important;font-weight:600!important;font-size:.9rem!important;
  box-shadow:var(--tp-sh-1);transition:transform .12s ease,box-shadow .12s ease,background-color .12s ease!important;}
.stButton>button:hover{transform:translateY(-1px);box-shadow:var(--tp-sh-2);}
.stButton>button:active{transform:translateY(0) scale(.98);}
.stDownloadButton>button{background:var(--tp-surface)!important;color:var(--tp-ink)!important;border:1px solid var(--tp-line)!important;}
.stDownloadButton>button:hover{border-color:var(--tp-ink)!important;background:#F8FAFC!important;}
.btn-ingreso>button,.btn-salida>button{min-height:64px!important;font-size:1.05rem!important;border-radius:var(--tp-r-md)!important;}
.btn-ingreso>button{background:var(--tp-ok)!important;}
.btn-ingreso>button:hover{background:#087548!important;}

/* Campos */
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="textarea"],.stDateInput>div>div,.stNumberInput>div>div{border-radius:var(--tp-r-sm)!important;}
[data-baseweb="input"],[data-baseweb="textarea"],[data-baseweb="select"]>div{border:1px solid var(--tp-line)!important;background:var(--tp-surface)!important;}
[data-baseweb="input"]:focus-within,[data-baseweb="textarea"]:focus-within,[data-baseweb="select"]>div:focus-within{border-color:var(--tp-red)!important;box-shadow:0 0 0 3px rgba(236,50,55,.15)!important;}
[data-testid="stWidgetLabel"] p{font-size:.82rem;font-weight:600;color:var(--tp-ink-2);}

/* Pestañas */
.stTabs [data-baseweb="tab-list"]{gap:6px;overflow-x:auto;scrollbar-width:none;border-bottom:1px solid var(--tp-line);}
.stTabs [data-baseweb="tab-list"]::-webkit-scrollbar{display:none;}
.stTabs [data-baseweb="tab"]{height:46px;padding:0 14px;font-weight:600;color:var(--tp-mute);white-space:nowrap;}
.stTabs [aria-selected="true"]{color:var(--tp-ink)!important;}
.stTabs [data-baseweb="tab-highlight"]{background:var(--tp-red)!important;height:3px;border-radius:3px;}

/* Tablas, alertas, progreso */
[data-testid="stDataFrame"]{border:1px solid var(--tp-line);border-radius:var(--tp-r-md);overflow:hidden;box-shadow:var(--tp-sh-1);}
[data-testid="stAlert"]{border-radius:var(--tp-r-md);border:1px solid var(--tp-line);}
.stProgress>div>div>div>div{background:var(--tp-red)!important;border-radius:999px;}
.stProgress>div>div>div{border-radius:999px;}

/* Barra lateral como navegación */
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0F172A 0%,#111C33 100%)!important;border-right:none;}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"]{display:none;}
[data-testid="stSidebar"] [role="radiogroup"]{gap:2px;}
[data-testid="stSidebar"] [role="radiogroup"] label{position:relative;padding:10px 14px 10px 16px;border-radius:12px;cursor:pointer;transition:background .12s ease;}
[data-testid="stSidebar"] [role="radiogroup"] label>div:first-child{display:none;}
[data-testid="stSidebar"] [role="radiogroup"] label p{font-size:.88rem;font-weight:500;color:#AEB8CC!important;}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:rgba(255,255,255,.06);}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:rgba(236,50,55,.16);}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked)::before{content:"";position:absolute;left:0;top:10px;bottom:10px;width:3px;border-radius:3px;background:var(--tp-red);}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p{color:#FFFFFF!important;font-weight:650;}
.tp-user{display:flex;align-items:center;gap:12px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.08);padding:12px;border-radius:14px;margin-bottom:18px;}
.tp-user b{display:block;font-size:.84rem;color:#fff!important;line-height:1.25;}
.tp-user span{font-size:.7rem;color:#8EA0BE!important;}
.btn-logout>button{border-radius:12px!important;border:1px solid rgba(255,255,255,.18)!important;box-shadow:none!important;}

/* Componentes reutilizables */
.tp-avatar{flex:0 0 auto;width:40px;height:40px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;
  background:var(--tp-red);color:#fff!important;font-weight:700;font-size:.85rem;letter-spacing:.02em;}
.tp-chip{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;font-size:.74rem;font-weight:650;line-height:1.5;}
.tp-chip::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor;}
.tp-chip.ok{background:var(--tp-ok-soft);color:var(--tp-ok);} .tp-chip.warn{background:var(--tp-warn-soft);color:var(--tp-warn);}
.tp-chip.bad{background:var(--tp-bad-soft);color:var(--tp-bad);} .tp-chip.info{background:var(--tp-info-soft);color:var(--tp-info);}
.tp-chip.neutral{background:#EEF1F5;color:var(--tp-ink-2);}
.tp-kpi{background:var(--tp-surface);border:1px solid var(--tp-line);border-radius:var(--tp-r-md);padding:16px 18px;box-shadow:var(--tp-sh-1);}
.tp-kpi-lbl{font-size:.78rem;font-weight:600;color:var(--tp-mute);}
.tp-kpi-val{font-size:1.7rem;font-weight:700;color:var(--tp-ink);margin-top:2px;}
.tp-kpi-sub{font-size:.78rem;color:var(--tp-mute);margin-top:2px;}
.app-footer{margin-top:40px;padding:22px 0;border-top:1px solid var(--tp-line);color:var(--tp-mute);font-size:.78rem;line-height:1.7;text-align:center;}

/* Pantallas medianas y celulares */
@media (max-width:900px){
  .block-container{padding:4.2rem .9rem 5rem;}
  .market-header{padding:18px 18px 16px;border-radius:var(--tp-r-md);margin-bottom:16px;}
  .market-header::before{left:18px;}
  .market-header h1{font-size:1.2rem!important;}
}
@media (max-width:640px){
  html,body,input,select,textarea{font-size:16px;}
  [data-testid="stHorizontalBlock"]{gap:.75rem!important;}
  .stButton>button,.stDownloadButton>button{min-height:50px;width:100%;}
  .btn-ingreso>button,.btn-salida>button{min-height:70px!important;}
  [data-testid="stMetric"],.tp-kpi{padding:14px 16px;}
  .cal-card{overflow-x:auto;-webkit-overflow-scrolling:touch;padding:14px!important;}
  .cal-table{min-width:540px;}
  .boleta-container{padding:16px!important;overflow-x:auto;}
  [data-testid="stDataFrame"]{overflow-x:auto;}
  .stTabs [data-baseweb="tab"]{padding:0 10px;font-size:.84rem;}
}
@supports (padding:max(0px)){.block-container{padding-bottom:max(3rem,env(safe-area-inset-bottom));}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important;}}
</style>
""",
r"""
<style>
/* Barra lateral clara */
[data-testid="stSidebar"]{background:#FFFFFF!important;border-right:1px solid var(--tp-line)!important;}
[data-testid="stSidebar"] *{color:var(--tp-ink)!important;}
[data-testid="stSidebar"] [role="radiogroup"] label>div:not(:has([data-testid="stMarkdownContainer"])){display:none!important;}
[data-testid="stSidebar"] [role="radiogroup"] label p{color:var(--tp-ink-2)!important;font-weight:550;}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:#F3F4F7;}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:var(--tp-red-soft);}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p{color:var(--tp-red-dk)!important;font-weight:700;}
[data-testid="stSidebarCollapseButton"] *{color:var(--tp-mute)!important;}
.tp-user{background:#F6F7FA;border:1px solid var(--tp-line);}
.tp-user b{color:var(--tp-ink)!important;} .tp-user span{color:var(--tp-mute)!important;}
[data-testid="stSidebar"] .tp-avatar{color:#fff!important;}
.tp-avatar{width:46px;height:46px;object-fit:cover;box-shadow:0 0 0 2px #fff,0 0 0 4px var(--tp-red);}
.tp-brand{padding:2px 2px 16px;} .tp-brand-name{font-weight:800;font-size:1rem;letter-spacing:-.01em;}
[data-testid="stSidebar"] .tp-brand-name span{color:var(--tp-red)!important;} .tp-brand-sub{font-size:.72rem;color:var(--tp-mute)!important;}
.btn-logout>button{background:#fff!important;border:1px solid var(--tp-line)!important;}
.btn-logout>button:hover{background:var(--tp-red-soft)!important;border-color:var(--tp-red)!important;}
/* Marcación: tarjeta de estado y lista */
.tp-hero{box-sizing:border-box;min-height:132px;background:var(--tp-surface);border:1px solid var(--tp-line);border-radius:var(--tp-r-lg);padding:18px 20px;box-shadow:var(--tp-sh-1);}
.tp-hero-top{display:flex;gap:14px;align-items:center;margin-bottom:16px;}
.tp-hero-hi{font-weight:700;font-size:1.08rem;margin-bottom:5px;}
.tp-prog-lbl{display:flex;justify-content:space-between;font-size:.76rem;color:var(--tp-mute);font-weight:600;margin-bottom:6px;}
.tp-prog{height:8px;background:#EEF1F5;border-radius:999px;overflow:hidden;}
.tp-prog i{display:block;height:100%;background:linear-gradient(90deg,var(--tp-red),#F26B6F);border-radius:999px;}
.tp-row{display:flex;align-items:center;gap:12px;background:var(--tp-surface);border:1px solid var(--tp-line);border-radius:14px;padding:12px 14px;margin-bottom:8px;}
.tp-row-time{font-weight:700;font-variant-numeric:tabular-nums;min-width:48px;}
.tp-row-main{flex:1;min-width:0;} .tp-row-main b{display:block;font-size:.9rem;}
.tp-row-main span{display:block;font-size:.78rem;color:var(--tp-mute);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.tp-chips{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;}
/* Barra inferior (celular) */
.st-key-tp_bottomnav{display:none;}
@media (max-width:900px){
  .st-key-tp_bottomnav{display:block;position:fixed;left:0;right:0;bottom:0;z-index:999;background:rgba(255,255,255,.96);backdrop-filter:blur(10px);
    border-top:1px solid var(--tp-line);padding:6px 8px calc(6px + env(safe-area-inset-bottom,0px));box-shadow:0 -8px 24px -12px rgba(15,23,42,.25);}
  .st-key-tp_bottomnav [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:4px!important;}
  .st-key-tp_bottomnav [data-testid="stColumn"],.st-key-tp_bottomnav [data-testid="column"]{min-width:0!important;flex:1 1 0!important;width:auto!important;}
  .st-key-tp_bottomnav button{background:transparent!important;color:var(--tp-mute)!important;box-shadow:none!important;border:none!important;min-height:56px!important;padding:4px 2px!important;border-radius:12px!important;}
  .st-key-tp_bottomnav button>div{display:flex;flex-direction:column;align-items:center;gap:2px;}
  .st-key-tp_bottomnav button p{font-size:.68rem!important;font-weight:650!important;margin:0;color:inherit!important;}
  .st-key-tp_bottomnav button[kind="primary"],.st-key-tp_bottomnav [data-testid="stBaseButton-primary"]{background:var(--tp-red-soft)!important;color:var(--tp-red-dk)!important;}
  .st-key-tp_bottomnav button:hover{transform:none!important;}
  .tp-row{padding:10px 12px;}
}
</style>
""",
r"""
<style>
/* Ajustes finales: botón de menú, cerrar sesión y opciones */
[data-testid="stSidebar"] [role="radiogroup"] label>*:not(input):not([data-testid="stMarkdownContainer"]):not(:has([data-testid="stMarkdownContainer"])){display:none!important;}
[data-testid="stSidebar"] .stButton>button{background:#fff!important;border:1.5px solid var(--tp-red)!important;box-shadow:none!important;}
[data-testid="stSidebar"] .stButton>button *{color:#111827!important;font-weight:650;}
[data-testid="stSidebar"] .stButton>button:hover{background:var(--tp-red)!important;}
[data-testid="stSidebar"] .stButton>button:hover *{color:#111827!important;}
[data-testid="stSidebar"] .stButton>button{color:#111827!important;}
[data-testid="stExpandSidebarButton"],[data-testid="stSidebarCollapsedControl"],[data-testid="collapsedControl"]{background:#fff!important;border:1.5px solid var(--tp-red)!important;}
[data-testid="stExpandSidebarButton"] *,[data-testid="stSidebarCollapsedControl"] *,[data-testid="collapsedControl"] *{color:var(--tp-red)!important;fill:var(--tp-red)!important;}
[data-testid="stExpandSidebarButton"] button,[data-testid="stSidebarCollapsedControl"] button{background:transparent!important;}
[data-testid="stExpandSidebarButton"]:hover,[data-testid="stSidebarCollapsedControl"]:hover,[data-testid="collapsedControl"]:hover{background:var(--tp-red)!important;}
[data-testid="stExpandSidebarButton"]:hover *,[data-testid="stSidebarCollapsedControl"]:hover *,[data-testid="collapsedControl"]:hover *{color:#fff!important;fill:#fff!important;}
/* Tarjetas de solicitud + línea de tiempo */
.tp-card{background:var(--tp-surface);border:1px solid var(--tp-line);border-radius:16px;padding:16px 18px;margin-bottom:12px;box-shadow:var(--tp-sh-1);}
.tp-card-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;}
.tp-card-title{font-weight:700;font-size:.95rem;} .tp-card-sub{font-size:.76rem;color:var(--tp-mute);margin-top:2px;}
.tp-card-body{font-size:.86rem;color:var(--tp-ink-2);margin:10px 0 14px;line-height:1.55;}
.tp-resp{background:#F6F7FA;border-left:3px solid var(--tp-red);border-radius:8px;padding:10px 12px;font-size:.82rem;margin-top:12px;color:var(--tp-ink-2);}
.tp-tl{display:flex;}
.tp-tl-step{flex:1;position:relative;text-align:center;font-size:.7rem;font-weight:600;color:var(--tp-mute);}
.tp-tl-step::before{content:"";position:relative;z-index:1;display:block;width:14px;height:14px;margin:0 auto 6px;border-radius:50%;background:#fff;border:2px solid #CBD2DC;}
.tp-tl-step::after{content:"";position:absolute;top:6px;left:-50%;width:100%;height:2px;background:#CBD2DC;}
.tp-tl-step:first-child::after{display:none;}
.tp-tl-step.done{color:var(--tp-ink-2);} .tp-tl-step.done::before{background:var(--tp-ok);border-color:var(--tp-ok);} .tp-tl-step.done::after{background:var(--tp-ok);}
.tp-tl-step.now{color:var(--tp-warn);} .tp-tl-step.now::before{background:#F59E0B;border-color:#F59E0B;box-shadow:0 0 0 4px rgba(245,158,11,.2);} .tp-tl-step.now::after{background:var(--tp-ok);}
.tp-tl-step.bad{color:var(--tp-bad);} .tp-tl-step.bad::before{background:var(--tp-bad);border-color:var(--tp-bad);} .tp-tl-step.bad::after{background:var(--tp-bad);}
.tp-notif{display:flex;align-items:center;justify-content:space-between;gap:8px;background:var(--tp-warn-soft);border-radius:12px;padding:9px 12px;margin:-6px 0 14px;font-size:.78rem;font-weight:650;}
[data-testid="stSidebar"] .tp-notif,[data-testid="stSidebar"] .tp-notif *{color:var(--tp-warn)!important;}
/* Tabla en PC, tarjetas en celular */
.st-key-vista_tarjetas{display:none;}
@media (max-width:900px){.st-key-vista_tabla{display:none;}.st-key-vista_tarjetas{display:block;}}
</style>
""",
r"""
<style>
.tp-card.flat{border:none;box-shadow:none;padding:0;margin:0 0 8px;}
[class*="st-key-ap_"] button{background:var(--tp-ok)!important;color:#fff!important;border:none!important;}
[class*="st-key-ap_"] button:hover{background:#087548!important;}
[class*="st-key-rec_"] button{background:#fff!important;border:1.5px solid var(--tp-red)!important;}
[class*="st-key-rec_"] button *{color:var(--tp-red)!important;}
[class*="st-key-rec_"] button:hover{background:var(--tp-red-soft)!important;}
[class*="st-key-ap_"] button *{color:#fff!important;}
.tp-sec{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:6px 0 16px;}
.tp-sec-title{font-size:1.12rem;font-weight:700;color:var(--tp-ink);} .tp-sec-sub{font-size:.8rem;color:var(--tp-mute);}
.tp-op-head{display:flex;align-items:center;gap:12px;margin-bottom:16px;} .tp-op-head .tp-chip{margin-left:auto;}
.tp-mgrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-bottom:14px;}
.tp-m{background:#F6F7FA;border-radius:12px;padding:12px 14px;}
.tp-m-l{font-size:.66rem;font-weight:700;color:var(--tp-mute);text-transform:uppercase;letter-spacing:.07em;}
.tp-m-v{font-size:1.05rem;font-weight:700;margin-top:5px;color:var(--tp-ink);font-variant-numeric:tabular-nums;} .tp-m-v.pos{color:var(--tp-ok);}
.tp-m .tp-prog{margin-top:9px;height:6px;}
.tp-ngrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:10px;}
.tp-note{border:1px solid var(--tp-line);border-radius:12px;padding:12px 14px;}
.tp-note-t{font-size:.66rem;font-weight:700;color:var(--tp-mute);text-transform:uppercase;letter-spacing:.07em;margin-bottom:6px;}
.tp-note ul{margin:0;padding-left:16px;font-size:.84rem;color:var(--tp-ink-2);line-height:1.8;} .tp-note li.mute{color:var(--tp-mute);list-style:none;margin-left:-16px;}
@media (max-width:900px){.tp-mgrid{grid-template-columns:repeat(2,minmax(0,1fr));}}
</style>
""",
r"""
<style>
/* Quita el espacio vacío superior: los bloques de estilo y el iframe invisible no deben ocupar lugar */
[data-testid="stElementContainer"]:has(style),.element-container:has(style),[data-testid="stElementContainer"]:has(iframe[height="0"]),.element-container:has(iframe[height="0"]){display:none!important;}
.stApp:has([data-testid="stSidebar"][aria-expanded="true"]) .block-container{padding-top:3.2rem;}
[data-testid="stToolbarActions"],[data-testid="stAppDeployButton"]{display:none!important;}
.tp-steps{margin:2px 0 14px;padding:0;list-style:none;counter-reset:paso;}
.tp-steps li{counter-increment:paso;position:relative;padding:5px 0 5px 34px;font-size:.84rem;line-height:1.45;color:var(--tp-ink-2);}
.tp-steps li::before{content:counter(paso);position:absolute;left:0;top:4px;width:23px;height:23px;border-radius:50%;background:var(--tp-red-soft);color:var(--tp-red-dk);font-weight:700;font-size:.74rem;display:flex;align-items:center;justify-content:center;}
.tp-steps-t{font-size:.7rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--tp-mute);margin:8px 0 4px;display:flex;gap:8px;align-items:center;}
</style>
""",
r"""
<style>
.tp-kpi.al-bad{border-left:4px solid var(--tp-bad);} .tp-kpi.al-warn{border-left:4px solid #F59E0B;} .tp-kpi.al-info{border-left:4px solid var(--tp-info);} .tp-kpi.al-ok{border-left:4px solid var(--tp-ok);}
.tp-banner{display:flex;align-items:center;gap:16px;border-radius:20px;padding:20px 24px;border:1px solid var(--tp-line);box-shadow:var(--tp-sh-1);}
.tp-banner.ok{background:linear-gradient(120deg,#E3F6EC,#F4FBF7);border-color:#BFE8D2;} .tp-banner.warn{background:linear-gradient(120deg,#FEF3C7,#FFFBEB);border-color:#F8DE95;} .tp-banner.bad{background:linear-gradient(120deg,#FEE4E2,#FFF5F4);border-color:#F9C4C0;}
.tp-banner b{font-size:1.1rem;color:var(--tp-ink);display:block;} .tp-banner span.s{font-size:.84rem;color:var(--tp-ink-2);}
.tp-al-ico{flex:0 0 auto;width:42px;height:42px;border-radius:13px;display:flex;align-items:center;justify-content:center;}
.tp-al-ico.bad{background:var(--tp-bad-soft);color:var(--tp-bad);} .tp-al-ico.warn{background:var(--tp-warn-soft);color:var(--tp-warn);} .tp-al-ico.info{background:var(--tp-info-soft);color:var(--tp-info);} .tp-al-ico.ok{background:var(--tp-ok-soft);color:var(--tp-ok);}
/* Saludo de cumpleaños */
</style>
""",
r"""
<style>
.stFormSubmitButton>button{background:linear-gradient(135deg,#EC3237,#C9262B)!important;border:none!important;box-shadow:0 14px 26px -12px rgba(236,50,55,.6);}
.stFormSubmitButton>button *{color:#fff!important;font-weight:700;}
.tp-callout{display:flex;gap:12px;align-items:flex-start;border-radius:14px;padding:14px 16px;margin:6px 0 14px;font-size:.88rem;line-height:1.55;color:var(--tp-ink-2);border:1px solid var(--tp-line);}
.tp-callout.info{background:var(--tp-info-soft);border-color:#C7D8FB;} .tp-callout.ok{background:var(--tp-ok-soft);border-color:#BFE8D2;} .tp-callout.warn{background:var(--tp-warn-soft);border-color:#F8DE95;}
.tp-callout i{flex:0 0 auto;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-style:normal;font-weight:800;font-size:.8rem;background:#fff;}
.tp-callout.info i{color:var(--tp-info);} .tp-callout.ok i{color:var(--tp-ok);} .tp-callout.warn i{color:var(--tp-warn);}
</style>
""",
r"""
<style>
/* Transición entre pestañas: la página entra suavemente */
@keyframes tpPgA{from{opacity:.5;transform:translateY(12px);}to{opacity:1;transform:none;}}
@keyframes tpPgB{from{opacity:.5;transform:translateY(12px);}to{opacity:1;transform:none;}}
.stApp:has(.tp-pg-a) .block-container{animation:tpPgA .45s cubic-bezier(.2,.7,.2,1);}
.stApp:has(.tp-pg-b) .block-container{animation:tpPgB .45s cubic-bezier(.2,.7,.2,1);}
[data-testid="stElementContainer"]:has(.tp-pg-a),[data-testid="stElementContainer"]:has(.tp-pg-b),.element-container:has(.tp-pg-a),.element-container:has(.tp-pg-b){display:none!important;}
[data-testid="stStatusWidget"]{display:none!important;}
[data-stale="true"],.stale-element{opacity:.45!important;transition:opacity .25s ease;}
</style>
""",
r"""
<style>
[data-testid="stSidebar"] a.tp-negosy{display:flex;align-items:center;justify-content:space-between;gap:10px;background:linear-gradient(135deg,#0F172A 0%,#1B2A4A 100%);
  border-radius:14px;padding:12px 16px;margin:6px 0 12px;text-decoration:none;box-shadow:var(--tp-sh-1);transition:transform .12s ease,box-shadow .12s ease;}
[data-testid="stSidebar"] a.tp-negosy:hover{transform:translateY(-1px);box-shadow:var(--tp-sh-2);}
[data-testid="stSidebar"] a.tp-negosy .tp-negosy-t{display:block;font-weight:800;font-size:.95rem;letter-spacing:.01em;color:#FFFFFF!important;}
[data-testid="stSidebar"] a.tp-negosy .tp-negosy-s{display:block;font-size:.7rem;color:#9FB0CC!important;margin-top:1px;}
[data-testid="stSidebar"] a.tp-negosy svg{flex:0 0 auto;color:#FF8A8E!important;stroke:#FF8A8E!important;}
</style>
""",
r"""
<style>
/* Acciones generales: superficie clara, acento corporativo y contraste accesible. */
.stButton > button:not([kind="primary"]):not([data-testid="stBaseButton-primary"]),
.stDownloadButton > button:not([kind="primary"]) {
  background:#FFFFFF !important; color:#334155 !important;
  border:1px solid #D9E0E9 !important; border-radius:11px !important;
  box-shadow:0 2px 5px rgba(24,39,75,.05) !important;
}
.stButton > button:not([kind="primary"]):hover,
.stDownloadButton > button:not([kind="primary"]):hover {
  background:#FFF4F4 !important; border-color:#EC3237 !important;
  color:#C8252B !important; box-shadow:0 4px 10px rgba(236,50,55,.09) !important;
}
.stButton > button:not([kind="primary"]) *,
.stDownloadButton > button:not([kind="primary"]) * {color:inherit !important;}
/* Botón de acción principal: rojo de Sistema, no negro. */
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {
  background:#EC3237 !important; border:1px solid #EC3237 !important;
  color:#FFFFFF !important; border-radius:11px !important;
  box-shadow:0 3px 9px rgba(236,50,55,.17) !important;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover {
  background:#D6282D !important; border-color:#D6282D !important;
}
.stButton > button[kind="primary"] *,
.stButton > button[data-testid="stBaseButton-primary"] * {color:#FFFFFF !important;}
/* En formularios, guardar/confirmar conserva el acento rojo existente. */
.stFormSubmitButton > button {border-radius:11px !important;}
/* Se respetan los botones de ingreso/salida, chatbot, menú lateral y navegación móvil. */
.btn-ingreso > button, .btn-ingreso button {background:#00A959 !important;color:#fff !important;border-color:#00A959 !important;}
.btn-salida > button, .btn-salida button {background:#EC3237 !important;color:#fff !important;border-color:#EC3237 !important;}
.st-key-tp_chat_fab button {border-radius:50% !important;background-color:#EC3237 !important;}
.st-key-tp_bottomnav button:not([kind="primary"]) {background:transparent !important;border:none !important;box-shadow:none !important;}
/* Acceso a Negosy: visible sin desentonar con la marca. */
[data-testid="stSidebar"] a.tp-negosy {
  background:linear-gradient(120deg,#EC3237 0%,#D52C32 100%) !important;
  border:1px solid #C9272D !important;border-radius:12px !important;
  box-shadow:0 4px 12px rgba(236,50,55,.18) !important;
  transition:transform .15s ease,box-shadow .15s ease !important;
}
[data-testid="stSidebar"] a.tp-negosy:hover {
  transform:translateY(-2px) !important;
  box-shadow:0 7px 17px rgba(236,50,55,.26) !important;
}
[data-testid="stSidebar"] a.tp-negosy .tp-negosy-t {color:#FFFFFF !important;}
[data-testid="stSidebar"] a.tp-negosy .tp-negosy-s {color:#FFE5E6 !important;}
[data-testid="stSidebar"] a.tp-negosy svg {color:#FFFFFF !important;stroke:#FFFFFF !important;}
/* Navegación lateral original: no modificar selección, disposición ni etiquetas. */
</style>
""",
r"""<style>
/* Tablets: controles y tarjetas se acomodan sin desbordar */
@media screen and (max-width: 900px) {
  .main .block-container {max-width:100%!important;padding-left:16px!important;padding-right:16px!important;}
  [data-testid="stMainBlockContainer"] {max-width:100%!important;}
  [data-testid="stHorizontalBlock"] {flex-wrap:wrap!important;}
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {min-width:min(260px,100%)!important;flex:1 1 260px!important;}
  .tp-up-calendar {max-width:100%!important;overflow-x:auto!important;-webkit-overflow-scrolling:touch;}
  .tp-up-calendar table {min-width:850px!important;}
  .tp-shift-detail-wrap {max-width:100%!important;overflow-x:auto!important;-webkit-overflow-scrolling:touch;}
  .tp-cal-grid {grid-template-columns:repeat(3,minmax(0,1fr))!important;}
  .tp-mgrid {grid-template-columns:repeat(2,minmax(0,1fr))!important;}
}
/* Teléfonos: una columna, tipografía legible y acciones táctiles */
@media screen and (max-width: 640px) {
  html,body {max-width:100%;overflow-x:hidden;}
  .main .block-container,[data-testid="stMainBlockContainer"] {padding:64px 12px 36px!important;max-width:100%!important;overflow-x:clip;}
  [data-testid="stHorizontalBlock"] {gap:10px!important;flex-wrap:wrap!important;}
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {flex:1 1 100%!important;min-width:0!important;width:100%!important;}
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] > div {min-width:0!important;}
  [data-testid="stSidebar"] {max-width:min(86vw,320px)!important;}
  [data-testid="stSidebar"] [role="radiogroup"] label {min-height:44px;}
  .market-header {padding:16px!important;margin-bottom:12px!important;}
  .market-header h1 {font-size:1.18rem!important;line-height:1.3!important;}
  .tp-kpi,.cal-card,.boleta-container {max-width:100%;box-sizing:border-box;}
  .tp-kpi-val {font-size:1.4rem!important;}
  .stButton>button,.stDownloadButton>button,.stFormSubmitButton>button {min-height:46px!important;max-width:100%;white-space:normal!important;line-height:1.3!important;}
  [data-baseweb="input"] input,[data-baseweb="textarea"] textarea {font-size:16px!important;}
  [data-testid="stDataFrame"],[data-testid="stDataEditor"] {max-width:100%!important;overflow-x:auto!important;}
  .stTabs [data-baseweb="tab-list"] {overflow-x:auto!important;flex-wrap:nowrap!important;}
  .stTabs [data-baseweb="tab"] {flex-shrink:0!important;}
  .tp-cal-shell {padding:12px!important;margin:8px 0 12px!important;}
  .tp-cal-head {align-items:flex-start!important;gap:8px!important;}
  .tp-cal-head h3 {font-size:1rem!important;}
  .tp-cal-grid {grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:7px!important;}
  .tp-cal-day {min-height:112px!important;border-radius:10px!important;}
  .tp-cal-date {padding:8px!important;}
  .tp-cal-body {padding:9px 8px!important;gap:5px!important;}
  .tp-cal-body b {font-size:.78rem!important;}
  .tp-cal-body span {font-size:.73rem!important;}
  .tp-cal-legend {gap:8px!important;}
  .tp-up-calendar {width:100%!important;overflow-x:auto!important;border-radius:10px!important;}
  .tp-up-calendar table {min-width:820px!important;}
  .tp-up-calendar th.tp-up-person {min-width:145px!important;width:145px!important;}
  .tp-up-calendar thead th:first-child {width:145px!important;}
  .tp-up-calendar th.tp-up-person,.tp-up-calendar thead th:first-child {position:sticky;left:0;z-index:2;background:#fff;box-shadow:2px 0 5px rgba(0,0,0,.05);}
  .tp-up-calendar thead th:first-child {background:#f8fafc;z-index:3;}
  .tp-shift-detail-wrap {width:100%!important;overflow-x:auto!important;border-radius:0!important;}
  table.tp-shift-detail {min-width:950px!important;border-radius:0!important;}
  .tp-mgrid,.tp-id-grid {grid-template-columns:1fr!important;}
  .tp-hb {display:flex!important;flex-wrap:wrap!important;gap:8px!important;}
  .tp-hb-t {flex-basis:100%!important;}
  .tp-lg-hero {padding:16px!important;min-height:0!important;border-radius:16px!important;}
  .tp-lg-h {font-size:1.32rem!important;line-height:1.25!important;}
  .tp-lg-p {font-size:.88rem!important;line-height:1.5!important;}
  .tp-lg-quote {margin-top:12px!important;padding:12px!important;}
  .tp-lg-quote p {font-size:.86rem!important;}
  .tp-lg-who .tp-avatar {width:64px!important;height:64px!important;}
  .tp-lg-t {font-size:1.2rem!important;}
  .tp-lg-note {font-size:.71rem!important;line-height:1.4!important;}
  .st-key-tp_chat_fab {right:10px!important;top:60px!important;}
  .st-key-tp_chat_panel {right:8px!important;top:125px!important;width:calc(100vw - 16px)!important;max-height:65dvh!important;}
}
@media screen and (max-width:380px) {
  .main .block-container,[data-testid="stMainBlockContainer"] {padding-left:9px!important;padding-right:9px!important;}
  .tp-cal-grid {grid-template-columns:1fr!important;}
  .tp-cal-day {min-height:0!important;}
  .tp-cal-body {gap:3px!important;}
  .tp-cal-legend {font-size:.65rem!important;}
}
</style>""",
r"""<style>
@media (max-width: 767px) {
  html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
  body, .stApp, [data-testid="stAppViewContainer"] { width:100%; max-width:100%; }
  [data-testid="stMainBlockContainer"], .main .block-container {
    width:100%!important; max-width:100%!important;
    padding: max(70px, env(safe-area-inset-top)) 12px calc(28px + env(safe-area-inset-bottom))!important;
    box-sizing:border-box!important;
  }
  /* No recortar elementos desplegables ni ventanas de Streamlit */
  [data-testid="stMain"], [data-testid="stVerticalBlock"], [data-testid="stVerticalBlockBorderWrapper"] {
    min-width:0!important; max-width:100%;
  }
  [data-testid="stHorizontalBlock"] { flex-wrap:wrap!important; gap:12px!important; align-items:stretch!important; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    flex:1 1 100%!important; width:100%!important; min-width:0!important; max-width:100%!important;
  }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] > div { min-width:0!important; }
  [data-testid="stForm"], [data-testid="stExpander"], [data-testid="stVerticalBlockBorderWrapper"] {
    max-width:100%; box-sizing:border-box;
  }
  [data-testid="stForm"] { padding:12px!important; }
  [data-testid="stWidgetLabel"] p { line-height:1.35!important; }
  [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
  [data-testid="stTextArea"] textarea, [data-baseweb="select"] input {
    font-size:16px!important; min-height:44px;
  }
  [data-testid="stButton"] button, [data-testid="stFormSubmitButton"] button,
  [data-testid="stDownloadButton"] button, [data-testid="stPopover"] button {
    min-height:48px!important; width:100%; touch-action:manipulation;
    white-space:normal!important; overflow-wrap:anywhere; line-height:1.3!important;
  }
  /* Ingreso y salida: botones cómodos y diferenciados en móvil */
  .btn-ingreso button, .btn-salida button { min-height:60px!important; font-size:1rem!important; }
  .tp-hero, .tp-card, .tp-kpi, .market-header, .cal-card, .boleta-container {
    max-width:100%!important; min-width:0!important; box-sizing:border-box!important;
    overflow-wrap:anywhere;
  }
  .tp-hero-top { flex-wrap:wrap; }
  .tp-hero-hi { overflow-wrap:anywhere; }
  .tp-kpi-val { overflow-wrap:anywhere; font-size:clamp(1.25rem,6vw,1.7rem)!important; }
  .tp-mgrid, .tp-gridk, .tp-id-grid { grid-template-columns:minmax(0,1fr)!important; }
  .tp-cal-grid { grid-template-columns:repeat(2,minmax(0,1fr))!important; }
  .tp-up-calendar, .tp-shift-detail-wrap, .cal-card, .boleta-container,
  [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
    max-width:100%!important; overflow-x:auto!important; -webkit-overflow-scrolling:touch;
  }
  .stTabs [data-baseweb="tab-list"] { max-width:100%; overflow-x:auto!important; scrollbar-width:thin; }
  .stTabs [data-baseweb="tab"] { white-space:nowrap!important; min-height:44px; }
  /* Dialogos de cumpleaños, botellas y formularios: visibles sin salir de pantalla */
  [role="dialog"] { max-width:calc(100vw - 20px)!important; max-height:calc(100dvh - 32px)!important;
    overflow-y:auto!important; box-sizing:border-box!important; }
  [data-testid="stDialog"] { max-width:100vw!important; }
  [data-testid="stDialog"] [data-testid="stVerticalBlock"] { min-width:0!important; }
  [data-testid="stDialog"] button { min-height:48px!important; white-space:normal!important; }
  [data-testid="stSidebar"] { width:min(88vw,330px)!important; max-width:min(88vw,330px)!important; }
  [data-testid="stSidebar"] button { min-height:44px; }
  /* Chatbot: sin tapar la navegación ni el contenido inferior */
  .st-key-tp_chat_fab { right:12px!important; top:70px!important; }
  .st-key-tp_chat_panel { right:8px!important; top:135px!important;
    width:calc(100vw - 16px)!important; max-width:calc(100vw - 16px)!important;
    max-height:calc(100dvh - 150px)!important; overflow-y:auto!important; }
  [data-testid="stToastContainer"] { max-width:calc(100vw - 20px)!important; }
  [data-testid="stToast"] { max-width:calc(100vw - 24px)!important; }
}
@media (max-width: 390px) {
  [data-testid="stMainBlockContainer"], .main .block-container { padding-left:9px!important; padding-right:9px!important; }
  .tp-cal-grid { grid-template-columns:minmax(0,1fr)!important; }
  .tp-cal-day { min-height:0!important; }
}
@media (orientation: landscape) and (max-height: 480px) {
  [role="dialog"] { max-height:calc(100dvh - 12px)!important; }
  .st-key-tp_chat_panel { top:65px!important; max-height:calc(100dvh - 75px)!important; }
}
</style>""",
r"""
<style>
/* =====================================================================
   Componentes propios de Inventario, escritos con los tokens de Asistencia
   (mismos colores, radios, sombras y tipografía: --tp-*)
   ===================================================================== */
.section-title{font-size:1.02rem;font-weight:700;color:var(--tp-ink);margin:20px 0 10px;letter-spacing:-.01em;}
.card{background:var(--tp-surface);border:1px solid var(--tp-line);border-radius:var(--tp-r-md);padding:14px 18px;margin-bottom:12px;box-shadow:var(--tp-sh-1);color:var(--tp-ink-2);font-size:.9rem;line-height:1.5;}
.card b{color:var(--tp-ink);}
.mobile-note{background:var(--tp-info-soft);border:1px solid #C7D8FB;border-radius:14px;padding:12px 16px;margin:6px 0 14px;font-size:.84rem;line-height:1.55;color:var(--tp-ink-2);}
.mobile-note b{color:var(--tp-ink);}
.tp-kpi{min-height:128px;}

/* Ficha de producto */
.product-card{background:var(--tp-surface);border:1px solid var(--tp-line);border-top:3px solid var(--tp-red);border-radius:var(--tp-r-md);padding:18px 20px;margin:10px 0 15px;box-shadow:var(--tp-sh-1);}
.product-name{font-size:1.15rem;font-weight:700;color:var(--tp-ink);line-height:1.25;}
.product-meta{color:var(--tp-ink-2);font-size:.82rem;margin-top:4px;}
.stock-box{background:#F6F7FA;border:1px solid var(--tp-line);border-radius:12px;padding:13px;text-align:center;}
.stock-label{font-size:.66rem;font-weight:700;color:var(--tp-mute);text-transform:uppercase;letter-spacing:.07em;}
.stock-number{font-size:1.5rem;font-weight:700;color:var(--tp-ink);margin-top:4px;font-variant-numeric:tabular-nums;}

/* Consulta de precios */
.price-hero{background:var(--tp-surface);border:1px solid var(--tp-line);border-radius:var(--tp-r-lg);padding:26px 22px;text-align:center;box-shadow:var(--tp-sh-1);margin:14px 0;}
.price-hero .price-label{font-size:.72rem;font-weight:700;text-transform:uppercase;color:var(--tp-mute);letter-spacing:.09em;}
.price-hero .price-value{font-size:3rem;font-weight:800;margin:6px 0 2px;line-height:1;color:var(--tp-ink);font-variant-numeric:tabular-nums;}
.price-hero .price-sub{font-size:.85rem;color:var(--tp-mute);}
.price-info-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-top:12px;}
.price-info-item{background:#F6F7FA;border-radius:12px;padding:12px;text-align:center;}
.price-info-item .lbl{font-size:.66rem;font-weight:700;color:var(--tp-mute);text-transform:uppercase;letter-spacing:.07em;}
.price-info-item .val{font-size:1.05rem;font-weight:700;margin-top:5px;color:var(--tp-ink);font-variant-numeric:tabular-nums;}

/* Plan de compras (Stock Intelligence) */
.psi-executive{position:relative;background:var(--tp-surface);border:1px solid var(--tp-line);border-radius:var(--tp-r-lg);padding:22px 24px 20px;margin:10px 0 18px;box-shadow:var(--tp-sh-1);}
.psi-executive::before{content:"";position:absolute;left:24px;top:0;width:36px;height:4px;background:var(--tp-red);border-radius:0 0 4px 4px;}
.psi-executive h3{font-size:1.04rem;color:var(--tp-ink);margin:4px 0 7px;font-weight:700;}
.psi-executive p{font-size:.92rem;color:var(--tp-ink-2);line-height:1.6;margin:0;}
.psi-eyebrow{color:var(--tp-mute);font-size:.7rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;margin:12px 0 8px;}
.psi-section{display:flex;align-items:center;gap:10px;margin:22px 0 12px;color:var(--tp-ink);font-size:1.08rem;font-weight:700;}
.psi-section .psi-index{display:inline-grid;place-items:center;width:28px;height:28px;border-radius:9px;background:var(--tp-red-soft);color:var(--tp-red-dk);font-size:.8rem;font-weight:700;}
.psi-smallnote{color:var(--tp-mute);font-size:.83rem;margin:0 0 10px;}

@media (max-width:640px){
  .price-hero{padding:22px 16px;} .price-hero .price-value{font-size:2.3rem;}
  .product-card{padding:14px;} .psi-executive{padding:18px 16px 16px;}
  .psi-executive::before{left:16px;}
}
</style>
"""
]
LOGIN_CSS = r"""
<style>
.stApp:has(.tp-lg-hero){background:radial-gradient(1100px 560px at 8% -10%,#FDECEC 0%,transparent 60%),radial-gradient(900px 520px at 100% 110%,#E4EBF8 0%,transparent 58%),var(--tp-bg);}
.stApp:has(.tp-lg-hero) .block-container{padding-top:1.6rem;max-width:1180px;}
.tp-lg-hero{position:relative;overflow:hidden;border-radius:28px;padding:36px 38px;min-height:640px;color:#fff;display:flex;flex-direction:column;justify-content:space-between;
  background:linear-gradient(150deg,#0B1220 0%,#111C33 55%,#1B2A4A 100%);box-shadow:0 30px 60px -30px rgba(15,23,42,.6);}
.tp-lg-hero::before{content:"";position:absolute;width:540px;height:540px;right:-190px;top:-170px;border-radius:50%;background:radial-gradient(circle,rgba(236,50,55,.55),rgba(236,50,55,0) 68%);}
.tp-lg-hero::after{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.045) 1px,transparent 1px);background-size:44px 44px;-webkit-mask-image:linear-gradient(180deg,#000,transparent 88%);mask-image:linear-gradient(180deg,#000,transparent 88%);}
.tp-lg-hero>*{position:relative;z-index:1;}
.tp-lg-logo{display:inline-flex;background:#fff;border-radius:16px;padding:10px 18px;box-shadow:0 12px 30px -12px rgba(0,0,0,.6);}
.tp-lg-k{font-size:.72rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#FF8A8E;margin:34px 0 10px;}
.tp-lg-h{font-size:2.2rem;font-weight:800;line-height:1.14;letter-spacing:-.02em;margin:0 0 14px;color:#fff;}
.tp-lg-h em{font-style:normal;color:#FF6B70;}
.tp-lg-p{color:#B7C2D9;font-size:.98rem;line-height:1.65;max-width:440px;margin:0;}
.tp-lg-feat{display:grid;gap:10px;margin-top:26px;max-width:460px;}
.tp-lg-feat div{display:flex;align-items:center;gap:12px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:14px;padding:12px 14px;font-size:.87rem;font-weight:600;color:#E6ECF8;}
.tp-lg-feat i{flex:0 0 auto;width:32px;height:32px;border-radius:10px;background:rgba(236,50,55,.2);color:#FF8A8E;display:flex;align-items:center;justify-content:center;}
.tp-lg-quote{position:relative;margin-top:26px;padding:18px 20px 18px 24px;border-radius:16px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);}
.tp-lg-quote::before{content:"";position:absolute;left:0;top:16px;bottom:16px;width:4px;border-radius:4px;background:#EC3237;}
.tp-lg-quote small{display:block;font-size:.68rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#FF8A8E;margin-bottom:8px;}
.tp-lg-quote p{margin:0;font-size:1.1rem;font-weight:600;line-height:1.5;color:#fff;}
.tp-lg-spacer{height:64px;}
.tp-lg-who{display:flex;flex-direction:column;align-items:center;text-align:center;margin-bottom:10px;animation:tpPop .4s ease;}
.tp-lg-who .tp-avatar{box-shadow:0 0 0 3px #fff,0 0 0 6px var(--tp-red),0 14px 30px -10px rgba(236,50,55,.55);}
.tp-lg-t{font-size:1.45rem;font-weight:800;color:var(--tp-ink);margin-top:16px;letter-spacing:-.01em;}
.tp-lg-s{font-size:.86rem;color:var(--tp-mute);margin-top:4px;}
.tp-lg-lock{width:58px;height:58px;border-radius:18px;background:var(--tp-red-soft);color:var(--tp-red);display:flex;align-items:center;justify-content:center;}
@keyframes tpPop{from{opacity:0;transform:translateY(8px) scale(.97);}to{opacity:1;transform:none;}}
.st-key-tpc_login_form{padding:32px 30px 26px!important;border-radius:26px!important;box-shadow:var(--tp-sh-2)!important;}
.st-key-tpc_login_form [data-baseweb="input"]{min-height:50px;background:#F6F7FA!important;}
.st-key-tpc_login_form .stButton>button{min-height:52px;border:none!important;background:linear-gradient(135deg,#EC3237,#C9262B)!important;box-shadow:0 14px 26px -12px rgba(236,50,55,.7);}
.st-key-tpc_login_form .stButton>button *{color:#111827!important;font-weight:700;}
.st-key-tpc_login_form .stButton>button{color:#111827!important;}
.tp-lg-note{display:flex;gap:8px;align-items:center;justify-content:center;font-size:.76rem;color:var(--tp-mute);margin-top:14px;}
@media (max-width:900px){.tp-lg-hero{min-height:0;padding:22px;border-radius:22px;}.tp-lg-k{margin-top:20px;}.tp-lg-h{font-size:1.5rem;}.tp-lg-feat,.tp-lg-spacer{display:none;}.tp-lg-quote{margin-top:16px;padding:14px 16px 14px 20px;}.tp-lg-quote p{font-size:.95rem;}}
</style>
"""


def _rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _mezclar(h, otro, t):
    r, g, b = _rgb(h)
    o = (0, 0, 0) if otro == "negro" else (255, 255, 255)
    return "#%02X%02X%02X" % tuple(round(c + (x - c) * t) for c, x in zip((r, g, b), o))


@functools.lru_cache(maxsize=64)
def aplicar_marca(css, primario):
    """Cambia el rojo de la marca original por el color de la empresa (y sus tonos derivados)."""
    p = str(primario or COLOR_BASE).upper()
    if p == COLOR_BASE or len(p) != 7:
        return css
    cambios = {"#EC3237": p, "#FDECEC": _mezclar(p, "blanco", .92), "#F26B6F": _mezclar(p, "blanco", .35)}
    for oscuro in ("#C9262B", "#D6282D", "#D02429", "#C8252B", "#D52C32", "#C9272D"):
        cambios[oscuro] = _mezclar(p, "negro", .14)
    for viejo, nuevo in cambios.items():
        css = css.replace(viejo, nuevo).replace(viejo.lower(), nuevo)
    r, g, b = _rgb(p)
    return css.replace("rgba(236,50,55,", f"rgba({r},{g},{b},")


def inyectar_estilos():
    p = cfg().color_primario
    for bloque in BLOQUES:
        st.markdown(aplicar_marca(bloque, p), unsafe_allow_html=True)


def inyectar_estilos_login():
    st.markdown(aplicar_marca(LOGIN_CSS, cfg().color_primario), unsafe_allow_html=True)
