import os
import hmac
import pandas as pd
import streamlit as st
import plotly.express as px

# =========================
# Configuração geral
# =========================
st.set_page_config(page_title="Dados das cirurgias", layout="wide")

# No Streamlit Cloud, o arquivo deve estar no repositório
ARQUIVO = "Dados.xlsx"
ABA = "Página1"

COL_ANO = "ANO"
COL_ID = "ID PACIENTE"
COL_SEXO = "SEXO"
COL_NASC = "DATA DE NASCIMENTO"
COL_CIRURGIA = "DATA DA CIRURGIA"
COL_TECNICA = "TÉCNICA"
COL_CONVENIO = "CONVÊNIO"
COL_HOSPITAL = "HOSPITAL"
COL_IDADE = "IDADE"

FAIXAS_ORDEM = [
    "Abaixo de 18",
    "18 a 24",
    "25 a 34",
    "35 a 44",
    "45 a 54",
    "55 a 64",
    "Acima de 64",
    "Não informado",
]

# =========================
# Constantes para tendência mensal
# =========================
MONTH_ORDER = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

MONTH_NUM_MAP = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr",
    5: "Mai", 6: "Jun", 7: "Jul", 8: "Ago",
    9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}

START_MONTHLY = pd.Timestamp("2021-05-01")

# Modebar: manter apenas baixar imagem e tela cheia
PLOTLY_CONFIG = {
    "displaylogo": False,
    "displayModeBar": "hover",
    "scrollZoom": False,
    "modeBarButtonsToRemove": [
        "zoom2d", "pan2d", "select2d", "lasso2d",
        "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d",
        "hoverClosestCartesian", "hoverCompareCartesian", "toggleHover",
        "toggleSpikelines",
        "resetViews", "sendDataToCloud", "editInChartStudio",
        "resetViewMapbox", "zoomInMapbox", "zoomOutMapbox",
        "hoverClosestPie", "hoverComparePie",
    ],
}

CUSTOM_CSS = """
<style>
[data-testid="stAppViewContainer"] { background: #0A2C56; }
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, rgba(17,66,127,.40), rgba(21,166,214,.12));
  border-right: 1px solid rgba(255,255,255,.10);
}
h1, h2, h3, p, li, div, span { color: rgba(255,255,255,.95); }

.card {
  border: 1px solid rgba(255,255,255,.14);
  background: linear-gradient(180deg, rgba(255,255,255,.09), rgba(255,255,255,.05));
  border-radius: 18px;
  padding: 14px 16px;
}
.card-title { font-size: 12px; opacity: .85; margin-bottom: 6px; }
.card-value { font-size: 22px; font-weight: 760; }
hr { border: none; height: 1px; background: rgba(255,255,255,.12); margin: 16px 0; }
.small-note { opacity: .85; font-size: 12px; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =========================
# Senha simples (via st.secrets)
# =========================
def check_password() -> None:
    """
    Se APP_PASSWORD estiver definido em st.secrets, exige senha.
    Se não estiver definido, libera o app sem senha.
    """
    if "APP_PASSWORD" not in st.secrets:
        return

    if "password_ok" not in st.session_state:
        st.session_state["password_ok"] = False

    def _password_entered():
        st.session_state["password_ok"] = hmac.compare_digest(
            st.session_state.get("password", ""),
            st.secrets.get("APP_PASSWORD", "")
        )
        st.session_state["password"] = ""

    if not st.session_state["password_ok"]:
        st.markdown("### Acesso restrito")
        st.text_input("Senha", type="password", key="password", on_change=_password_entered)
        st.stop()

check_password()

# =========================
# Funções utilitárias
# =========================
def sentence_case(s: str) -> str:
    if s is None:
        return "Não informado"
    s = str(s).strip()
    if not s:
        return "Não informado"
    s = " ".join(s.split())
    return s.lower().capitalize()

def norm_text_series(s: pd.Series) -> pd.Series:
    return (
        s.astype(str)
         .str.replace("\n", " ", regex=False)
         .str.replace("\r", " ", regex=False)
         .str.strip()
         .replace({"nan": None, "None": None, "": None})
    )

def normalize_tecnica(v: str) -> str:
    if v is None:
        return "Não informado"
    raw = " ".join(str(v).strip().split()).upper()
    raw = raw.replace("Á", "A").replace("À", "A").replace("Ã", "A").replace("Â", "A")
    raw = raw.replace("É", "E").replace("Ê", "E")
    raw = raw.replace("Í", "I")
    raw = raw.replace("Ó", "O").replace("Ô", "O").replace("Õ", "O")
    raw = raw.replace("Ú", "U")

    mapa = {
        "SLEEVE": "Sleeve",
        "BYPASS": "Bypass",
        "REVISIONAL": "Revisional",
        "METABOLICA": "Metabólica",
        "METABÓLICA": "Metabólica",
    }
    return mapa.get(raw, sentence_case(v))

def normalize_hospital(v: str) -> str:
    if v is None:
        return "Não informado"
    raw = " ".join(str(v).strip().split()).upper()
    if raw == "H MILITAR":
        return "H militar"
    return sentence_case(v)

def normalize_convenio(v: str) -> str:
    if v is None:
        return "Não informado"
    return sentence_case(v)

def normalize_sexo(v: str) -> str:
    if v is None:
        return "Não informado"
    raw = str(v).strip().upper()
    if raw == "M":
        return "M"
    if raw == "F":
        return "F"
    return "Não informado"

def faixa_from_idade(idade) -> str:
    if pd.isna(idade):
        return "Não informado"
    try:
        idade = float(idade)
    except Exception:
        return "Não informado"

    if idade < 18:
        return "Abaixo de 18"
    if 18 <= idade <= 24:
        return "18 a 24"
    if 25 <= idade <= 34:
        return "25 a 34"
    if 35 <= idade <= 44:
        return "35 a 44"
    if 45 <= idade <= 54:
        return "45 a 54"
    if 55 <= idade <= 64:
        return "55 a 64"
    if idade >= 65:
        return "Acima de 64"
    return "Não informado"

def fmt_int(n) -> str:
    try:
        return f"{int(n):,}".replace(",", ".")
    except Exception:
        return "—"

def fmt_pct(p) -> str:
    try:
        return f"{p:.1f}%".replace(".", ",")
    except Exception:
        return "—"

def apply_global_style(fig, height=750):
    fig.update_layout(
        height=height,
        font=dict(size=18),
        title=dict(font=dict(size=26)),
        margin=dict(l=40, r=40, t=80, b=60),
        dragmode=False,
    )
    fig.update_xaxes(fixedrange=True, title_font=dict(size=18), tickfont=dict(size=16))
    fig.update_yaxes(fixedrange=True, title_font=dict(size=18), tickfont=dict(size=16))
    fig.update_traces(textfont=dict(size=18))
    return fig

def show(fig, height=750):
    fig = apply_global_style(fig, height=height)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

@st.cache_data
def load_data(path: str, sheet: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet)

    required = [COL_ANO, COL_ID, COL_SEXO, COL_CIRURGIA, COL_TECNICA, COL_CONVENIO, COL_HOSPITAL, COL_IDADE]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Colunas faltando: {missing}")

    df[COL_TECNICA] = norm_text_series(df[COL_TECNICA])
    df[COL_CONVENIO] = norm_text_series(df[COL_CONVENIO])
    df[COL_HOSPITAL] = norm_text_series(df[COL_HOSPITAL])
    df[COL_SEXO] = norm_text_series(df[COL_SEXO])

    df[COL_SEXO] = df[COL_SEXO].apply(normalize_sexo)
    df[COL_TECNICA] = df[COL_TECNICA].apply(normalize_tecnica)
    df[COL_CONVENIO] = df[COL_CONVENIO].apply(normalize_convenio)
    df[COL_HOSPITAL] = df[COL_HOSPITAL].apply(normalize_hospital)

    df[COL_CIRURGIA] = pd.to_datetime(df[COL_CIRURGIA], errors="coerce", dayfirst=True)
    if COL_NASC in df.columns:
        df[COL_NASC] = pd.to_datetime(df[COL_NASC], errors="coerce", dayfirst=True)

    df[COL_ANO] = pd.to_numeric(df[COL_ANO], errors="coerce").astype("Int64")
    df[COL_IDADE] = pd.to_numeric(df[COL_IDADE], errors="coerce")

    df["Faixa etária"] = df[COL_IDADE].apply(faixa_from_idade)
    return df

# =========================
# Gráficos
# =========================
def fig_tendencia_ano(df_base: pd.DataFrame):
    g = df_base.dropna(subset=[COL_ANO]).groupby(COL_ANO).size().reset_index(name="Cirurgias")
    g = g.sort_values(COL_ANO)

    fig = px.line(
        g, x=COL_ANO, y="Cirurgias",
        markers=True,
        title="Tendência de cirurgias por ano"
    )
    fig.update_traces(text=g["Cirurgias"], textposition="top center")
    return fig, g

def _monthly_base(df_base: pd.DataFrame) -> pd.DataFrame:
    """Base mensal imutável a partir de maio/2021."""
    d = df_base.dropna(subset=[COL_CIRURGIA]).copy()
    d = d[d[COL_CIRURGIA] >= START_MONTHLY]

    d["Ano"] = d[COL_CIRURGIA].dt.year.astype(int)
    d["Mes_num"] = d[COL_CIRURGIA].dt.month.astype(int)
    d["Mes"] = d["Mes_num"].map(MONTH_NUM_MAP)

    d["Mes"] = pd.Categorical(
        d["Mes"],
        categories=MONTH_ORDER,
        ordered=True
    )
    return d


def fig_mensal_media_agregado(df_base: pd.DataFrame):
    """
    Média de cirurgias por mês do ano (sazonalidade).
    X = meses (Jan–Dez)
    Y = média de cirurgias
    """
    d = _monthly_base(df_base)

    g = (
        d.groupby(["Ano", "Mes"], observed=True)
         .size()
         .reset_index(name="Cirurgias")
    )

    m = (
        g.groupby("Mes", observed=True)["Cirurgias"]
         .mean()
         .reindex(MONTH_ORDER)
         .fillna(0)
         .reset_index(name="Média")
    )

    fig = px.line(
        m,
        x="Mes",
        y="Média",
        markers=True,
        title="Tendência mensal (média do agregado)",
    )

    fig.update_traces(
        text=m["Média"].round(1),
        textposition="top center"
    )

    fig.update_xaxes(title_text="Mês")
    fig.update_yaxes(title_text="Média de cirurgias")
    return fig


def fig_mensal_por_ano(df_base: pd.DataFrame):
    """
    Tendência mensal por ano.
    X = meses (Jan–Dez)
    Y = cirurgias
    Regra: em 2021, Jan–Abr são inexistentes (NaN), então não plota pontos/linha.
    """
    d = _monthly_base(df_base)

    g = (
        d.groupby(["Ano", "Mes"], observed=True)
         .size()
         .reset_index(name="Cirurgias")
    )

    anos = sorted(g["Ano"].unique().tolist())
    linhas = []

    for ano in anos:
        gy = g[g["Ano"] == ano].copy()

        # garante eixo Jan–Dez para todos
        gy = (
            gy.set_index("Mes")
              .reindex(MONTH_ORDER)  # Jan..Dez
              .reset_index()
        )
        gy["Ano"] = ano

        # preenchimento padrão (anos != 2021): meses faltantes viram 0
        if ano != 2021:
            gy["Cirurgias"] = gy["Cirurgias"].fillna(0)
        else:
            # 2021: Jan–Abr devem ser inexistentes (NaN), e Mai–Dez faltantes viram 0
            meses_inexistentes = ["Jan", "Fev", "Mar", "Abr"]

            # Mai..Dez: se faltar, vira 0
            gy.loc[~gy["Mes"].isin(meses_inexistentes), "Cirurgias"] = (
                gy.loc[~gy["Mes"].isin(meses_inexistentes), "Cirurgias"].fillna(0)
            )
            # Jan..Abr: mantém NaN (não plota)
            # (não faz fillna nesses meses)

        linhas.append(gy)

    gg = pd.concat(linhas, ignore_index=True)

    fig = px.line(
        gg,
        x="Mes",
        y="Cirurgias",
        color="Ano",
        markers=True,
        title="Tendência mensal (por ano)",
    )

    # rótulo: só mostra onde existe valor (evita "nan" nos meses inexistentes)
    gg_text = gg["Cirurgias"].apply(lambda v: "" if pd.isna(v) else fmt_int(v))
    fig.update_traces(text=gg_text, textposition="top center")

    fig.update_xaxes(title_text="Mês")
    fig.update_yaxes(title_text="Número de cirurgias")
    return fig

def donut_sexo(df: pd.DataFrame):
    g = df.groupby(COL_SEXO).size().reset_index(name="Cirurgias").sort_values("Cirurgias", ascending=False)
    g[COL_SEXO] = g[COL_SEXO].replace({"M": "Masculino", "F": "Feminino", "Não informado": "Não informado"})

    fig = px.pie(g, names=COL_SEXO, values="Cirurgias", hole=0.55, title="Distribuição por sexo")
    fig.update_traces(textinfo="percent+label")
    return fig

def barh_faixa(df: pd.DataFrame):
    total = len(df)
    g = df.groupby("Faixa etária").size().reindex(FAIXAS_ORDEM, fill_value=0).reset_index()
    g.columns = ["Faixa etária", "Cirurgias"]
    g["Percentual"] = g["Cirurgias"].apply(lambda x: (x / total * 100) if total else 0)
    g["Texto"] = g.apply(lambda r: f"{fmt_int(r['Cirurgias'])} ({fmt_pct(r['Percentual'])})", axis=1)

    fig = px.bar(
        g, y="Faixa etária", x="Cirurgias",
        orientation="h",
        text="Texto",
        title="Distribuição por faixa etária",
        color="Faixa etária",
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(showlegend=False)
    return fig

def idade_histograma_barras(df: pd.DataFrame, bin_size: int = 5):
    s = df[COL_IDADE].dropna()
    if s.empty:
        return px.bar(title="Distribuição por idade")

    total = len(s)
    min_age = int(s.min())
    max_age = int(s.max())
    start = (min_age // bin_size) * bin_size
    end = ((max_age // bin_size) + 1) * bin_size
    bins = list(range(start, end + bin_size, bin_size))

    cats = pd.cut(s, bins=bins, right=False, include_lowest=True)
    g = cats.value_counts().sort_index().reset_index()
    g.columns = ["Faixa", "Cirurgias"]
    g["Percentual"] = g["Cirurgias"].apply(lambda x: (x / total * 100) if total else 0)

    def label_interval(iv):
        left = int(iv.left)
        right = int(iv.right) - 1
        return f"{left} a {right}"

    g["Idade"] = g["Faixa"].apply(label_interval)
    g["Texto"] = g.apply(lambda r: f"{fmt_int(r['Cirurgias'])} ({fmt_pct(r['Percentual'])})", axis=1)

    fig = px.bar(g, x="Idade", y="Cirurgias", text="Texto", title="Distribuição por idade", color="Idade")
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(showlegend=False)
    return fig

def bar_tecnica_vertical(df: pd.DataFrame):
    total = len(df)
    g = df.groupby(COL_TECNICA).size().reset_index(name="Cirurgias").sort_values("Cirurgias", ascending=False)
    g["Percentual"] = g["Cirurgias"].apply(lambda x: (x / total * 100) if total else 0)
    g["Texto"] = g.apply(lambda r: f"{fmt_int(r['Cirurgias'])} ({fmt_pct(r['Percentual'])})", axis=1)

    fig = px.bar(
        g, x=COL_TECNICA, y="Cirurgias",
        text="Texto",
        title="Distribuição das técnicas cirúrgicas",
        color=COL_TECNICA,
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(showlegend=False)
    return fig

def barh_convenio_top5_outros(df: pd.DataFrame):
    total = len(df)
    vc = df[COL_CONVENIO].fillna("Não informado").value_counts()

    top5 = vc.head(5)
    outros = vc.iloc[5:].sum()

    data = [(k, int(v)) for k, v in top5.items()]
    if outros > 0:
        data.append(("Outros", int(outros)))

    g = pd.DataFrame(data, columns=[COL_CONVENIO, "Cirurgias"]).sort_values("Cirurgias", ascending=False)
    g["Percentual"] = g["Cirurgias"].apply(lambda x: (x / total * 100) if total else 0)
    g["Texto"] = g.apply(lambda r: f"{fmt_int(r['Cirurgias'])} ({fmt_pct(r['Percentual'])})", axis=1)

    fig = px.bar(
        g, y=COL_CONVENIO, x="Cirurgias",
        orientation="h",
        text="Texto",
        title="Distribuição por convênio",
        color=COL_CONVENIO,
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(showlegend=False)
    return fig

def barh_hospital(df: pd.DataFrame):
    total = len(df)
    g = df.groupby(COL_HOSPITAL).size().reset_index(name="Cirurgias").sort_values("Cirurgias", ascending=False)
    g["Percentual"] = g["Cirurgias"].apply(lambda x: (x / total * 100) if total else 0)
    g["Texto"] = g.apply(lambda r: f"{fmt_int(r['Cirurgias'])} ({fmt_pct(r['Percentual'])})", axis=1)

    fig = px.bar(
        g, y=COL_HOSPITAL, x="Cirurgias",
        orientation="h",
        text="Texto",
        title="Distribuição por hospital",
        color=COL_HOSPITAL,
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(showlegend=False)
    return fig

def top3_list(series: pd.Series, total: int):
    vc = series.fillna("Não informado").value_counts().head(3)
    items = []
    for k, v in vc.items():
        pct = (v / total * 100) if total else 0
        items.append(f"- {k}: {fmt_int(v)} ({fmt_pct(pct)})")
    return "\n".join(items) if items else "- Não informado"

# =========================
# App
# =========================
st.title("Dados das cirurgias")

if not os.path.exists(ARQUIVO):
    st.error(f"Arquivo '{ARQUIVO}' não encontrado no repositório. Envie o arquivo para o GitHub junto do app.")
    st.stop()

df_base = load_data(ARQUIVO, ABA)

st.sidebar.header("Filtros do recorte")
st.sidebar.caption("Os indicadores do topo e a tendência são gerais e não mudam com os filtros.")

min_dt = df_base[COL_CIRURGIA].min()
max_dt = df_base[COL_CIRURGIA].max()

if pd.isna(min_dt) or pd.isna(max_dt):
    st.sidebar.warning("As datas de cirurgia não foram reconhecidas. Verifique o formato d/m/a.")
    date_range = None
else:
    date_range = st.sidebar.date_input(
        "Período (data da cirurgia)",
        value=(min_dt.date(), max_dt.date()),
        min_value=min_dt.date(),
        max_value=max_dt.date(),
    )

idade_valid = df_base[COL_IDADE].dropna()
idade_range = None
if len(idade_valid) > 0:
    idade_min = int(idade_valid.min())
    idade_max = int(idade_valid.max())
    idade_range = st.sidebar.slider("Idade", min_value=idade_min, max_value=idade_max, value=(idade_min, idade_max))

faixa_sel = st.sidebar.multiselect("Faixa etária", FAIXAS_ORDEM, default=FAIXAS_ORDEM)
sexo_sel = st.sidebar.multiselect("Sexo", ["M", "F", "Não informado"], default=["M", "F"])

tecnicas = sorted(df_base[COL_TECNICA].dropna().unique().tolist())
tecnica_sel = st.sidebar.multiselect("Técnica", tecnicas, default=tecnicas)

hospitais = sorted(df_base[COL_HOSPITAL].dropna().unique().tolist())
hospital_sel = st.sidebar.multiselect("Hospital", hospitais, default=hospitais)

convenios = sorted(df_base[COL_CONVENIO].dropna().unique().tolist())
convenio_sel = st.sidebar.multiselect("Convênio", convenios, default=convenios)

df = df_base.copy()

if date_range is not None:
    d0 = pd.to_datetime(date_range[0])
    d1 = pd.to_datetime(date_range[1])
    df = df[(df[COL_CIRURGIA] >= d0) & (df[COL_CIRURGIA] <= d1)]

if idade_range is not None:
    df = df[(df[COL_IDADE] >= idade_range[0]) & (df[COL_IDADE] <= idade_range[1])]

df = df[df["Faixa etária"].isin(faixa_sel)]
df = df[df[COL_SEXO].isin(sexo_sel)]
df = df[df[COL_TECNICA].isin(tecnica_sel)]
df = df[df[COL_HOSPITAL].isin(hospital_sel)]
df = df[df[COL_CONVENIO].isin(convenio_sel)]

# Storytelling
st.header("Visão geral")

total_pacientes = df_base[COL_ID].dropna().nunique()
top_hosp_vc = df_base[COL_HOSPITAL].fillna("Não informado").value_counts()
top_conv_vc = df_base[COL_CONVENIO].fillna("Não informado").value_counts()

top_hosp = top_hosp_vc.index[0] if len(top_hosp_vc) else "Não informado"
top_hosp_n = int(top_hosp_vc.iloc[0]) if len(top_hosp_vc) else 0

top_conv = top_conv_vc.index[0] if len(top_conv_vc) else "Não informado"
top_conv_n = int(top_conv_vc.iloc[0]) if len(top_conv_vc) else 0

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f"""
    <div class="card">
      <div class="card-title">Número de pacientes</div>
      <div class="card-value">{fmt_int(total_pacientes)}</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="card">
      <div class="card-title">Top convênio</div>
      <div class="card-value" style="font-size:16px;">{top_conv} ({fmt_int(top_conv_n)})</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="card">
      <div class="card-title">Top hospital</div>
      <div class="card-value" style="font-size:16px;">{top_hosp} ({fmt_int(top_hosp_n)})</div>
    </div>
    """, unsafe_allow_html=True)

min_geral = df_base[COL_CIRURGIA].min()
max_geral = df_base[COL_CIRURGIA].max()
if pd.notna(min_geral) and pd.notna(max_geral):
    st.write(
        f"Este painel apresenta um panorama geral das cirurgias registradas. "
        f"O período observado vai de {min_geral.strftime('%d/%m/%Y')} a {max_geral.strftime('%d/%m/%Y')}."
    )
else:
    st.write("Este painel apresenta um panorama geral das cirurgias registradas.")

st.markdown("<hr/>", unsafe_allow_html=True)

st.header("Evolução no tempo")
fig_trend, _ = fig_tendencia_ano(df_base)  # imutável
show(fig_trend, height=650)

st.subheader("Tendência mensal")

modo = st.radio(
    "Visualização",
    ["Média do agregado", "Tendência por ano"],
    horizontal=True,
)

if modo == "Média do agregado":
    show(fig_mensal_media_agregado(df_base), height=850)
else:
    show(fig_mensal_por_ano(df_base), height=900)

st.caption(
    "Os dados mensais consideram cirurgias a partir de maio de 2021. "
    "Todos os 12 meses são exibidos, e meses sem registros aparecem com valor zero. "
    "Em 2021, os meses antes de maio não são exibidos."
)

st.markdown("<hr/>", unsafe_allow_html=True)

st.header("Perfil dos pacientes")
cc1, cc2 = st.columns(2)
with cc1:
    show(donut_sexo(df), height=650)
with cc2:
    show(barh_faixa(df), height=750)
show(idade_histograma_barras(df, bin_size=5), height=850)

st.markdown("<hr/>", unsafe_allow_html=True)

st.header("Distribuição das técnicas cirúrgicas")
show(bar_tecnica_vertical(df), height=750)

st.markdown("<hr/>", unsafe_allow_html=True)

st.header("Convênios")
show(barh_convenio_top5_outros(df), height=750)

st.markdown("<hr/>", unsafe_allow_html=True)

st.header("Hospitais")
show(barh_hospital(df), height=750)

st.markdown("<hr/>", unsafe_allow_html=True)

st.header("Insights estratégicos")
total_recorte = len(df)

if total_recorte == 0:
    st.warning("Nenhum registro foi encontrado com os filtros atuais.")
else:
    i1, i2, i3, i4 = st.columns(4)

    with i1:
        sexo_top = top3_list(df[COL_SEXO].replace({"M": "Masculino", "F": "Feminino"}), total_recorte)
        faixa_top = top3_list(df["Faixa etária"], total_recorte)
        st.markdown(f"""
        <div class="card">
          <div class="card-title">Perfil predominante</div>
          <div class="small-note">Sexo</div>
          <div style="margin-top:6px; white-space:pre-wrap;">{sexo_top}</div>
          <div class="small-note" style="margin-top:10px;">Faixa etária</div>
          <div style="margin-top:6px; white-space:pre-wrap;">{faixa_top}</div>
        </div>
        """, unsafe_allow_html=True)

    with i2:
        tecn_top = top3_list(df[COL_TECNICA], total_recorte)
        st.markdown(f"""
        <div class="card">
          <div class="card-title">Procedimentos predominantes</div>
          <div style="margin-top:6px; white-space:pre-wrap;">{tecn_top}</div>
        </div>
        """, unsafe_allow_html=True)

    with i3:
        conv_top = top3_list(df[COL_CONVENIO], total_recorte)
        st.markdown(f"""
        <div class="card">
          <div class="card-title">Convênios predominantes</div>
          <div style="margin-top:6px; white-space:pre-wrap;">{conv_top}</div>
        </div>
        """, unsafe_allow_html=True)

    with i4:
        hosp_top = top3_list(df[COL_HOSPITAL], total_recorte)
        st.markdown(f"""
        <div class="card">
          <div class="card-title">Hospitais predominantes</div>
          <div style="margin-top:6px; white-space:pre-wrap;">{hosp_top}</div>
        </div>
        """, unsafe_allow_html=True)
