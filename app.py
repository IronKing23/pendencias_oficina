import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime, date
import io
import base64

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Controle de Reforma",
    layout="wide",
    page_icon="🚜",
    initial_sidebar_state="collapsed"
)

# --- CSS BLINDADO ---
st.markdown("""
<style>
    .stApp { background-color: #f0f2f6; }
    .kanban-card {
        background-color: #ffffff !important;
        border: 1px solid #ccc !important;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 3px 6px rgba(0,0,0,0.1);
    }
    .k-title { font-size: 18px !important; font-weight: 800; margin-bottom: 5px; color: var(--text-color); }
    .k-desc { font-size: 16px; margin-bottom: 10px; opacity: 0.8; color: var(--text-color); }
    .k-meta { font-size: 13px; display: flex; justify-content: space-between; border-top: 1px solid #eee; padding-top: 8px; color: var(--text-color); opacity: 0.7; }
    .prio-Alta { border-left: 8px solid #ff4b4b; }
    .prio-Média { border-left: 8px solid #ffa421; }
    .prio-Baixa { border-left: 8px solid #21c354; }
    .status-badge { font-size: 12px; padding: 2px 8px; border-radius: 4px; background-color: #eee; color: #333; font-weight: bold; }
    [data-testid="stMetricValue"] { font-size: 32px !important; font-weight: 700 !important; }
</style>
""", unsafe_allow_html=True)


# --- BANCO DE DADOS ---
def get_connection(): return sqlite3.connect('reforma_db_final.sqlite')


def init_db():
    conn = get_connection();
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reformas
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY
                     AUTOINCREMENT,
                     lote
                     TEXT,
                     frota
                     TEXT,
                     modelo
                     TEXT,
                     responsavel
                     TEXT,
                     data_inicio
                     DATE,
                     data_previsao
                     DATE,
                     status
                     TEXT,
                     progresso
                     INTEGER,
                     observacao
                     TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS gestores
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY
                     AUTOINCREMENT,
                     nome
                     TEXT
                     UNIQUE,
                     setor
                     TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS status_config
                 (
                     nome
                     TEXT
                     UNIQUE,
                     cor
                     TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS pendencias
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY
                     AUTOINCREMENT,
                     titulo
                     TEXT,
                     descricao
                     TEXT,
                     responsavel
                     TEXT,
                     frota_vinculada
                     TEXT,
                     prioridade
                     TEXT,
                     status
                     TEXT,
                     data_criacao
                     DATE,
                     data_prazo
                     DATE
                 )''')
    try:
        c.execute("ALTER TABLE pendencias ADD COLUMN data_prazo DATE")
    except:
        pass
    try:
        if c.execute('SELECT count(*) FROM gestores').fetchone()[0] == 0:
            c.executemany("INSERT INTO gestores (nome, setor) VALUES (?, ?)",
                          [('Wendell', 'Coord'), ('Oficina', 'Manut'), ('Terceiro', 'Ext')])
        if c.execute('SELECT count(*) FROM status_config').fetchone()[0] == 0:
            c.executemany("INSERT INTO status_config (nome, cor) VALUES (?, ?)",
                          [("Aguardando", "#95a5a6"), ("Concluído", "#2ecc71")])
        conn.commit()
    except:
        pass
    conn.close()


init_db()


# --- FUNÇÕES ---
def carregar_dados(): conn = get_connection(); df = pd.read_sql('SELECT * FROM reformas', conn); conn.close(); return df


def carregar_gestores(): conn = get_connection(); df = pd.read_sql('SELECT * FROM gestores',
                                                                   conn); conn.close(); return df


def carregar_pendencias(): conn = get_connection(); df = pd.read_sql('SELECT * FROM pendencias',
                                                                     conn); conn.close(); return df


def carregar_cores_status(): conn = get_connection(); df = pd.read_sql('SELECT * FROM status_config',
                                                                       conn); conn.close(); return pd.Series(
    df.cor.values, index=df.nome).to_dict()


# --- 1. GERAR EXCEL (Mantido) ---
def gerar_excel():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_r = carregar_dados();
        df_p = carregar_pendencias()
        if not df_r.empty:
            df_r.to_excel(writer, sheet_name='Máquinas', index=False)
        else:
            pd.DataFrame({'A': ['Vazio']}).to_excel(writer, sheet_name='Vazio')
        if not df_p.empty: df_p.to_excel(writer, sheet_name='Pendências', index=False)
    return output.getvalue()


# --- 2. GERAR RELATÓRIO VISUAL PRO (KANBAN) ---
def gerar_relatorio_visual_html(df_pen):
    # CSS de Impressão Profissional
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Relatório Visual Kanban - {date.today().strftime('%d/%m/%Y')}</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap');

            body {{ 
                font-family: 'Roboto', sans-serif; 
                background-color: #f4f4f9; 
                margin: 0; padding: 20px;
                -webkit-print-color-adjust: exact; 
                print-color-adjust: exact; 
            }}

            .header {{ 
                text-align: center; padding: 15px; 
                background: #2c3e50; color: white; 
                border-radius: 8px; margin-bottom: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}

            /* Layout Kanban em Colunas */
            .kanban-board {{
                display: flex;
                justify-content: space-between;
                gap: 15px;
                align-items: flex-start;
            }}

            .coluna {{
                width: 32%;
                background: #e0e0e0;
                padding: 10px;
                border-radius: 8px;
                min-height: 600px;
            }}

            .col-header {{
                text-align: center;
                font-weight: bold;
                font-size: 18px;
                padding: 10px;
                background: rgba(0,0,0,0.05);
                border-radius: 5px;
                margin-bottom: 15px;
                border-bottom: 3px solid #aaa;
                color: #333;
            }}

            .card {{
                background: white;
                border-radius: 6px;
                padding: 12px;
                margin-bottom: 10px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                border: 1px solid #ddd;
                page-break-inside: avoid;
            }}

            .card-title {{ font-size: 16px; font-weight: bold; margin-bottom: 5px; color: #000; }}
            .card-desc {{ font-size: 13px; color: #444; margin-bottom: 8px; line-height: 1.3; }}

            .card-footer {{
                display: flex; justify-content: space-between;
                border-top: 1px solid #eee; padding-top: 5px;
                font-size: 11px; color: #666; font-weight: bold;
            }}

            /* Cores de Prioridade */
            .border-Alta {{ border-left: 6px solid #ff4b4b; }}
            .border-Média {{ border-left: 6px solid #ffa421; }}
            .border-Baixa {{ border-left: 6px solid #21c354; }}

            /* Cores de Fundo por Status (Para impressão visual) */
            .bg-fazendo {{ background-color: #d6eaf8 !important; }}
            .bg-feito {{ background-color: #d5f5e3 !important; }}

        </style>
    </head>
    <body>
        <div class="header">
            <h2 style="margin:0">Relatório de Pendências (Kanban)</h2>
            <p style="margin:5px 0 0 0; font-size:14px">Gerado em: {date.today().strftime('%d/%m/%Y')}</p>
        </div>

        <div class="kanban-board">
    """

    titulos_colunas = ["A Fazer", "Fazendo", "Feito"]

    for status in titulos_colunas:
        bg_col_class = ""
        if status == "Fazendo": bg_col_class = "bg-fazendo"
        if status == "Feito": bg_col_class = "bg-feito"

        html += f'<div class="coluna {bg_col_class}"><div class="col-header">{status}</div>'

        tasks = df_pen[df_pen['status'] == status]
        for _, row in tasks.iterrows():
            prio = row['prioridade'] if row['prioridade'] else "Baixa"
            frota = row['frota_vinculada'] if row['frota_vinculada'] else "Geral"

            prazo_html = ""
            if row['data_prazo']:
                dp = pd.to_datetime(row['data_prazo']).date()
                cor_p = "black"
                if dp < date.today() and status != "Feito": cor_p = "red"
                prazo_html = f"<span style='color:{cor_p}'>📅 {dp.strftime('%d/%m')}</span>"

            html += f"""
            <div class="card border-{prio}">
                <div style="display:flex; justify-content:space-between; font-size:10px; color:#666; margin-bottom:4px;">
                    <span>{prio.upper()}</span>
                    <span>{row['responsavel']}</span>
                </div>
                <div class="card-title">{row['titulo']}</div>
                <div class="card-desc">{row['descricao']}</div>
                <div class="card-footer">
                    <span>🚜 {frota}</span>
                    {prazo_html}
                </div>
            </div>
            """
        html += "</div>"

    html += "</div></body></html>"
    return html


# --- INTERFACE SIDEBAR ---
st.sidebar.image("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAANwAAADlCAMAAAAP8WnWAAAAulBMVEX///9RjEAAAADMzMx8fHxOijxIhzU9giZFhjHW1tby8vLf39+xsbH8/PzCwsJLiTnm5uZqampBhCyRkZEiIiKhoaF0dHQ6Ojo7gSPZ2dnr6+u8vLzJ2MWAgIC2y7Gqw6Stra1UVFQwMDDy9vFsm1+Xl5dLS0soKCjF1cF9pXJflFDj6+HZ49aKroGUtIyfn58RERFeXl6kv55ZkElERERSUlIoeQB1oWqRsohmmFm8z7cyfRbr8eobGxtJBPxyAAAJVElEQVR4nO2bbVviOhCGQ8pbS1sLCCi1WlBgdXUBV3fXPfr//9aZmfQlARVd3asnnLk/uDRt03mSyWSadIVgGIZhGIZhGIZhGIZhGIZhGIZhGIZhGIZhGIZhGIZhGIZhGIZhGIZhmP8IQdUG/DVObn5UbcJf4uSm1T5oVG3FXyD4cgnKarXGRdWWfDa5MuDgpmpjPptepgxo3lZtzOdxfgJ/frdrBe3fVZv0SZyfXvxAcVeNUlzvumqrPoPH04ej9sED/LruldpqrfOqDfswj2cPrTb0V/sLHNwcaOIOqjbtg5yfXbWajUJKcKRru6zaug9y0c7HWPMMDk+1cKJK7OT6FP+0CilHOMD0cFJrn1Rt459xfVv78RX+/VmIIR/82tK01Y5sTJuvvzV6zeYvYYihbrptatoaV1Ub+m6uvzV7zdwLtdjYw5Pfda+0Lj/51e4pPc1vcHRexsYDPDa90rYp/KyYoqnjzpqmkjPdK2utqq19H2VPqXxfm7Bpvn7QvdK2We6yUNPCUHlSploHG15ayxIWeygntQamkZpW5ZVf9BncNq+8aBi9ondUG8//MvJKu15UtWyE4v5pc0OJPuJsi5Vlx9EI01Mt6slHfSJo1Cq29n3oHYfhRJ/UKNEyhlz7tGp730UZPhrf8VhLtdQq1zd9yLWsyisfy/Ch8iot1VLvNvosRwmMPWgd1dr0ShU89FnuyK4FhnJAKa/UUy2a0r5qqyeWdZwWLZRXlrEzG3J6PLFrxOlayAn1xRKlVvPbtl3rC4+b2ciJvvZKywmXhXzL5jh9hKlsRI/7vUcsKbv2yK7kRI/7KtuvaXGf4klQRM+mXVmlEfdpGflcK1DxpAiWDds25fRshCYCfcgd/DJKjr5Wa+u70bxSJc36MpfKT/J3hJ5dkdLM99WQ+6kNORUsM7lNyxYXjDe3WotCo76XQ+8I2Zsq7fTYxYXeT1igx5Nso4peGhrf7UpNhJmNqDUtcxeOLsIGaNTsypcRPTSq6PHbWAqii+C9/MBCbUY2YkQPIvseo1FrXlnnk8LcAVDx5FJfjlXxsdf7WamRf4gRPWjdy3jpVhOf+GHbtodCf1HLfFCPJ9lmjqUbjfqQU6lWoPelxZvDwtwKbtKK3aPec5Yt4pkYHyioYGlMc1Z/JnS9nWqdGMuvdu3mmBg7imrl57deZOs3C4Q+p6nM0tRrtTh97yabCYyFc5vFGVN4tul2sy/ijHiSrSRf7ou4577mutiHj6AQc3ypOW0vvvBCnuulWm1PxOlDLt/oNl5VLZ7Ez80vnuhtThhlFqdfRrDMP1o2xdmbOJurJdm+myHO4lee22e+VdNf5xrNIztfwREjGdkU12i2vp/ZtjWgYcwEtSaVqSADyq7OHis272MYXpktUYK4PVAmNmKH2r4S5//sg7KN1ZL8k+zz2z1QJjanOQu/N38NfbWk0T6yclH5RYoXHlB2cbof3lig5nBQ9nBq4Q7ODuBtjvps/5QBl719VQbc7K0yhmGY/z1B8LmfVXxydW9k7Iahs/1kKYcv3BC57vGrNXp39a2yWMrOLksma+3AXRzmT4n8NFQVzxz4mw4Gzq6qciSx3C7etlCxhstfrXEgZbRZFu4WB/o1ox0pXfWrTgaqK0BkAAf3O6oqUOJkvFX8kji8+tWu86X0NsueFxek01KPa1xSiBuQeXf4M8F6HbmrcQ1bkwjMWWwVvyAukqupHLxaZepuFT0v7rjoHiQOtVOFOClXobvs48/RCv7M5GRH42pItLQvJQy70FfuFPghiYvg38EMhmXslzb4cjKUanSEceBFYxFEkRinMCSW9f4Yir3xOBBRFMB5dYvrdxwUF0XQ8uMIHxL5sScCkBzDkQflcSfA26DMD3VxnixbksLAvYSuSN8jDj1pnI89aE85X4G4UE4HciKGUnfzuuyn5BfBQsqnPpyHGztQ4pL/gJul6JZS+iNodIxUeP8axZE3rPFm8rWAPAyuTWQ/kQMHOyTFkpVniMvjjCt9svd4LbvvEQeDVqykPCTnyUZhHR5wuALju3SYN9aTjF2KGGt1WRefP4f74fcETVZjbiRXeLZPgYJAcYmA2g7BtWng5OL68h6scAtxaLvmlvJOefQAjYOWB89866DDMbcEu0K0aw6PB9uGXl2JA+t84UCdd3KuLveUlT4aOPdmOGNAkVx0YwxKMTZCJk724WgqxBS6s7MyxA3QOkd4ICWFaaiP7RKTuI6DcUNq4uJMLbamQLdY4LmtcPySONWuQ2xlX47Qi4QKKFDJjK4Jl/O8sUL8MQJJadbLJG4kitu6ubipKgtIUropDj1MdJSCPh06Kk44gy7eX04F1JnomuBEeHsiRHb7W8WF2MDKWeYUdzNxrjKhDL99+dTtwrVoERwulDjw7DmqgVrmubg1WY13x1m0LMRhjYedIlqqqkicp8wYa+LEeEiTT0QtnVn5UoaxJa4eYjVPubgRBQ9NHBQm61zcXXaZl+ji0pfFudhyG+KygPKMOKh+WN8QR/EuBf8Elx1nj1+9VZwKteBqruM4rpjobumSXcflGIZhNJ/DgAoHaELulikarW4bboiL6AGxEjfMxIloja61Ka5DVTlb4gIM4wnOVlBP0u/f07PfIa4un1RBH5s6LMWl2MbDTJxLwR5sSFw0NSzFpVlA8TfEwQNAzQTFTdUQPBQePXeJ7pka4khtaohLOtTRsVhgnqH8Jd7OqF4Xh9PUcAg14jQ3kkbPdZN8zC1VarWCmFV4vxJHOR9dtiEOR8whTQVDdceh8FezBJswUN5p9Nzd0hxz+WgJ0KdhGGBoGZODv0lcljQnVIkv1LzWBavLMScXmbiJ8nYwM8DWuBsV4rJJ/DgTN8XYRlZ71ARYFV2BUyrlwugoc1PcsbhXz4oKcZ084DlompfF77cOunqSp3TxZDSn/Km/mIzjeirGvo/dFN0vZuO6SjWTBHUIJ6l3xHiZQhhKRFBPKP31ZsOlp07CxJzgSEvwrmiy6It6HaameDoKo3oijofTaYLJS9CdTvLLOnhJ0D0cBvjDXSxUAhkORyN4GLQAVAAW0QznxG+cCz7CWO7IoT+PeOut7G8yG4bx4g3voFaicsv17gttJHlHpmAhnY6N/zeHYRiGYRiGYRiGYRiGYRiGYRiGYRiGYRiGYRiGYRiGYRiGYRiGYRiG2T/+BSIvmCduAUd0AAAAAElFTkSuQmCC", width=50)
st.sidebar.title("Menu Reforma")

st.sidebar.markdown("### 📥 Exportação")
# Botão Excel
if st.sidebar.button("📊 Excel (Dados Brutos)"):
    try:
        d_xls = gerar_excel()
        st.sidebar.download_button("📥 Baixar .xlsx", d_xls, f"Reforma_{date.today()}.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except:
        st.sidebar.error("Erro Excel")

# Botão PDF Visual
if st.sidebar.button("🎨 Relatório Visual (PDF)"):
    try:
        df_p = carregar_pendencias()
        html = gerar_relatorio_visual_html(df_p)
        b64 = base64.b64encode(html.encode()).decode()
        href = f'<a href="data:text/html;base64,{b64}" download="Relatorio_Visual_{date.today()}.html" target="_blank" style="text-decoration:none; background-color:#ff4b4b; color:white; padding:10px; border-radius:5px; display:block; text-align:center; font-weight:bold; margin-top:10px; box-shadow:0 2px 5px rgba(0,0,0,0.2);">🖨️ Clique aqui para Imprimir PDF</a>'
        st.sidebar.markdown(href, unsafe_allow_html=True)
        st.sidebar.info("Dica: Ao abrir, pressione Ctrl+P e selecione 'Salvar como PDF'.")
    except Exception as e:
        st.sidebar.error(f"Erro: {e}")

st.sidebar.markdown("---")
menu = st.sidebar.radio("Navegação", ["📊 Painel TV", "📋 Kanban (Pendências)", "📝 Cadastro Lotes", "👥 Gestores",
                                      "🛠️ Diário de Bordo"])


# --- MODAL EDIÇÃO ---
@st.dialog("✏️ Editar Pendência")
def editar_pendencia_modal(id_p, dados_atuais):
    with st.form("edit_form"):
        c1, c2 = st.columns([3, 2])
        nt = c1.text_input("Título", value=dados_atuais['titulo'])
        lg = carregar_gestores()['nome'].tolist();
        idx_r = lg.index(dados_atuais['responsavel']) if dados_atuais['responsavel'] in lg else 0
        nr = c2.selectbox("Responsável", lg, index=idx_r)
        nd = st.text_area("Descrição", value=dados_atuais['descricao'])
        dv = pd.to_datetime(dados_atuais['data_prazo']).date() if dados_atuais['data_prazo'] else None
        npz = st.date_input("Prazo", value=dv)
        c3, c4 = st.columns(2)
        pl = ["Alta", "Média", "Baixa"];
        idx_p = pl.index(dados_atuais['prioridade']) if dados_atuais['prioridade'] in pl else 1
        npr = c3.selectbox("Prioridade", pl, index=idx_p)
        sl = ["A Fazer", "Fazendo", "Feito"];
        idx_s = sl.index(dados_atuais['status']) if dados_atuais['status'] in sl else 0
        nst = c4.selectbox("Mover para:", sl, index=idx_s)
        if st.form_submit_button("Salvar", type="primary"):
            conn = get_connection();
            conn.execute(
                "UPDATE pendencias SET titulo=?, descricao=?, responsavel=?, prioridade=?, status=?, data_prazo=? WHERE id=?",
                (nt, nd, nr, npr, nst, npz, id_p));
            conn.commit();
            conn.close();
            st.rerun()


# --- ABA 1: DASHBOARD ---
if menu == "📊 Painel TV":
    st.title("🚜 Painel de Gestão à Vista")
    df = carregar_dados();
    cores = carregar_cores_status()
    if not df.empty:
        lotes = df['lote'].unique();
        c_f, c_k = st.columns([1, 4])
        with c_f:
            fl = st.multiselect("Lotes:", lotes, default=lotes)
        if fl:
            df_v = df[df['lote'].isin(fl)].copy()
            with c_k:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total", len(df_v))
                c2.metric("Prontas", len(df_v[df_v['status'] == 'Concluído']))
                pend = len(df_v[df_v['status'] == 'Peça Pendente']) if 'Peça Pendente' in df_v['status'].values else 0
                c3.metric("Pendentes", pend)
                c4.metric("Andamento", f"{df_v['progresso'].mean():.0f}%")
            st.markdown("---")
            df_v['rotulo'] = df_v['frota'] + " (" + df_v['responsavel'] + ")"
            df_v = df_v.sort_values(by=['lote', 'progresso'])
            h = 400 + (len(df_v) * 50)
            try:
                fig = px.bar(df_v, y='rotulo', x='progresso', color='status', facet_row='lote', text='progresso',
                             orientation='h', color_discrete_map=cores, height=h)
                fig.update_layout(xaxis_range=[0, 120], yaxis_title=None, font=dict(size=18, color="black"),
                                  margin=dict(l=220), legend=dict(orientation="h", y=1.01),
                                  paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                fig.update_traces(texttemplate='%{text}%', textposition='outside', textfont_size=20,
                                  textfont_weight="bold", textfont_color="black")
                fig.for_each_annotation(
                    lambda a: a.update(text=a.text.split("=")[-1], font=dict(size=22, color="black")))
                fig.update_yaxes(matches=None, showticklabels=True, tickfont=dict(size=18, color="black"))
                st.plotly_chart(fig, use_container_width=True)
            except:
                st.error("Erro gráfico")
    else:
        st.info("Vazio")

# --- ABA 2: KANBAN ---
elif menu == "📋 Kanban (Pendências)":
    c_head, c_btn = st.columns([4, 1])
    c_head.title("Quadro de Tarefas")
    with c_btn:
        st.write("")
        with st.popover("➕ Nova Tarefa", use_container_width=True):
            with st.form("np"):
                tt = st.text_input("Título");
                td = st.text_area("Descrição");
                dt = st.date_input("Prazo", value=None)
                lm = ["- Geral -"] + carregar_dados()['frota'].unique().tolist()
                tv = st.selectbox("Vincular Frota", lm)
                tr = st.selectbox("Resp.", carregar_gestores()['nome'].tolist())
                tp = st.selectbox("Prioridade", ["Alta", "Média", "Baixa"])
                if st.form_submit_button("Criar", type="primary"):
                    conn = get_connection();
                    v = tv if tv != "- Geral -" else None
                    conn.execute(
                        "INSERT INTO pendencias (titulo, descricao, responsavel, frota_vinculada, prioridade, status, data_criacao, data_prazo) VALUES (?,?,?,?,?, 'A Fazer', ?, ?)",
                        (tt, td, tr, v, tp, date.today(), dt))
                    conn.commit();
                    conn.close();
                    st.success("Ok");
                    st.rerun()

    df_pen = carregar_pendencias()
    gestores = carregar_gestores()['nome'].tolist()
    filtro_g = st.multiselect("👤 Filtrar por Gestor:", gestores, default=gestores)
    if not df_pen.empty and filtro_g: df_pen = df_pen[df_pen['responsavel'].isin(filtro_g)]

    st.divider()
    c_td, c_dg, c_dn = st.columns(3)
    prio_colors = {"Alta": "#ff4b4b", "Média": "#ffa421", "Baixa": "#27ae60"}
    status_bg = {"A Fazer": "#ffffff", "Fazendo": "#d4e6f1", "Feito": "#d5f5e3"}  # Fundos coloridos


    def render_card(row, col_type):
        border = prio_colors.get(row['prioridade'], "#ccc")
        bg = status_bg.get(row['status'], "#fff")  # Cor de fundo baseada no status
        frota = f"{row['frota_vinculada']}" if row['frota_vinculada'] else "Geral"
        txt_prazo = ""
        if row['data_prazo']:
            try:
                dp = pd.to_datetime(row['data_prazo']).date();
                hoje = date.today()
                if row['status'] == "Feito":
                    txt_prazo = f"<span style='color:#27ae60'>✔ {dp.strftime('%d/%m')}</span>"
                elif dp < hoje:
                    txt_prazo = f"<span style='color:#c0392b; font-weight:bold'>🔥 {dp.strftime('%d/%m')}</span>"
                elif dp == hoje:
                    txt_prazo = f"<span style='color:#e67e22; font-weight:bold'>⚠️ Hoje</span>"
                else:
                    txt_prazo = f"📅 {dp.strftime('%d/%m')}"
            except:
                pass

        html_card = f"""
<div class="kanban-card prio-{row['prioridade']}" style="background-color: {bg} !important;">
<div style="display:flex; justify-content:space-between; margin-bottom:5px;">
<span class="status-badge">{row['prioridade']}</span>
<span style="font-weight:bold; font-size:14px; color:#555;">👤 {row['responsavel']}</span>
</div>
<div class="k-title">{row['titulo']}</div>
<div class="k-desc">{row['descricao']}</div>
<div class="k-meta">
<span>🚜 {frota}</span>
<span>{txt_prazo}</span>
</div>
</div>
"""
        st.markdown(html_card, unsafe_allow_html=True)
        b1, b2, b3, b4 = st.columns([1, 1, 1, 1])
        if b1.button("✏️", key=f"e_{row['id']}"): editar_pendencia_modal(row['id'], row)
        if col_type == "todo":
            if b4.button("▶️", key=f"g_{row['id']}"): mudar_status(row['id'], "Fazendo")
        elif col_type == "doing":
            if b3.button("⏪", key=f"b_{row['id']}"): mudar_status(row['id'], "A Fazer")
            if b4.button("✅", key=f"f_{row['id']}"): mudar_status(row['id'], "Feito")
        elif col_type == "done":
            if b3.button("⏪", key=f"r_{row['id']}"): mudar_status(row['id'], "Fazendo")
            if b4.button("🗑️", key=f"d_{row['id']}"): deletar_pendencia(row['id'])


    def mudar_status(id, stt):
        conn = get_connection(); conn.execute("UPDATE pendencias SET status=? WHERE id=?",
                                              (stt, id)); conn.commit(); conn.close(); st.rerun()


    def deletar_pendencia(id):
        conn = get_connection(); conn.execute("DELETE FROM pendencias WHERE id=?",
                                              (id,)); conn.commit(); conn.close(); st.rerun()


    if not df_pen.empty:
        with c_td:
            st.header("📌 A Fazer")
            for _, r in df_pen[df_pen['status'] == "A Fazer"].iterrows(): render_card(r, "todo")
        with c_dg:
            st.header("🔨 Fazendo")
            for _, r in df_pen[df_pen['status'] == "Fazendo"].iterrows(): render_card(r, "doing")
        with c_dn:
            st.header("🏁 Feito")
            for _, r in df_pen[df_pen['status'] == "Feito"].iloc[::-1][:15].iterrows(): render_card(r, "done")

# --- ABA 3: CADASTRO ---
elif menu == "📝 Cadastro Lotes":
    st.header("Cadastro")
    a1, a2 = st.tabs(["📂 Lote Massa", "✏️ Manutenção"])
    dfg = carregar_gestores();
    lg = dfg['nome'].tolist() if not dfg.empty else []
    with a1:
        with st.form("nl"):
            c1, c2, c3 = st.columns(3)
            nl = c1.text_input("Lote");
            rl = c2.selectbox("Resp", lg) if lg else None;
            dp = c3.date_input("Prev")
            grid = st.data_editor(pd.DataFrame([{"Frota": "", "Modelo": "", "Obs": ""}]), num_rows="dynamic",
                                  use_container_width=True)
            if st.form_submit_button("Salvar", type="primary"):
                if nl and rl:
                    cn = get_connection();
                    ct = 0
                    for _, r in grid.iterrows():
                        if r['Frota']: cn.execute(
                            "INSERT INTO reformas (lote, frota, modelo, responsavel, data_inicio, data_previsao, status, progresso, observacao) VALUES (?,?,?,?,?,?,'Aguardando',0,?)",
                            (nl, r['Frota'], r['Modelo'], rl, date.today(), dp, r['Obs'])); ct += 1
                    cn.commit();
                    cn.close();
                    st.success(f"{ct} Salvos!");
                    st.rerun()
                else:
                    st.error("Erro")
    with a2:
        cn = get_connection();
        le = pd.read_sql("SELECT DISTINCT lote FROM reformas", cn)['lote'].tolist();
        cn.close()
        if le:
            ls = st.selectbox("Lote:", le)
            dfr = carregar_dados();
            dl = dfr[dfr['lote'] == ls]
            if not dl.empty:
                st.info(f"Resp: {dl.iloc[0]['responsavel']}")
                with st.expander("Dividir Lote"):
                    c1, c2 = st.columns([2, 1]);
                    mm = c1.multiselect("Frotas:", dl['frota'].unique());
                    ng = c1.selectbox("Novo:", lg, key="n")
                    if c2.button("Aplicar"): cn = get_connection(); pl = ','.join('?' * len(mm)); cn.execute(
                        f"UPDATE reformas SET responsavel=? WHERE lote=? AND frota IN ({pl})",
                        [ng, ls] + mm); cn.commit(); cn.close(); st.rerun()
                with st.expander("Trocar Tudo"):
                    nt = st.selectbox("Novo:", lg, key="nt")
                    if st.button("Trocar"): cn = get_connection(); cn.execute(
                        "UPDATE reformas SET responsavel=? WHERE lote=?",
                        (nt, ls)); cn.commit(); cn.close(); st.success("Ok"); st.rerun()
                st.divider()
                c_a, c_r = st.columns(2)
                with c_a:
                    with st.form("ad"):
                        fn = st.text_input("F");
                        mn = st.text_input("M")
                        if st.form_submit_button("Add"):
                            rd = pd.to_datetime(dl.iloc[0]['data_previsao']).date()
                            cn = get_connection();
                            cn.execute(
                                "INSERT INTO reformas (lote, frota, modelo, responsavel, data_inicio, data_previsao, status, progresso, observacao) VALUES (?,?,?,?,?,?,'Aguardando',0,'')",
                                (ls, fn, mn, dl.iloc[0]['responsavel'], date.today(), rd));
                            cn.commit();
                            cn.close();
                            st.success("Ok");
                            st.rerun()
                with c_r:
                    dm = st.multiselect("Remover:", dl['frota'].unique())
                    if st.button("Excluir"): cn = get_connection(); [
                        cn.execute("DELETE FROM reformas WHERE lote=? AND frota=?", (ls, m)) for m in
                        dm]; cn.commit(); cn.close(); st.rerun()
            else:
                st.warning("Vazio")
        else:
            st.warning("Sem lotes")
elif menu == "👥 Gestores":
    st.header("Equipe")
    ed = st.data_editor(carregar_gestores(), num_rows="dynamic", use_container_width=True, hide_index=True)
    if st.button("Salvar"):
        cn = get_connection();
        ids = [int(r['id']) for i, r in ed.iterrows() if pd.notna(r['id'])]
        if not ids:
            cn.execute("DELETE FROM gestores")
        else:
            cn.execute(f"DELETE FROM gestores WHERE id NOT IN ({','.join(['?'] * len(ids))})", ids)
        for i, r in ed.iterrows():
            if pd.isna(r['id']):
                cn.execute("INSERT INTO gestores (nome, setor) VALUES (?,?)", (r['nome'], r['setor'])) if r[
                    'nome'] else None
            else:
                cn.execute("UPDATE gestores SET nome=?, setor=? WHERE id=?", (r['nome'], r['setor'], int(r['id'])))
        cn.commit();
        cn.close();
        st.success("Ok");
        st.rerun()
elif menu == "🛠️ Diário de Bordo":
    st.header("Atualização")
    with st.expander("⚙️ Config Status"):
        c1, c2 = st.columns(2)
        with c1:
            with st.form("ns"):
                n = st.text_input("Nome");
                c = st.color_picker("Cor")
                if st.form_submit_button("Criar"):
                    try:
                        cn = get_connection(); cn.execute("INSERT INTO status_config VALUES (?,?)",
                                                          (n, c)); cn.commit(); cn.close(); st.rerun()
                    except:
                        pass
        with c2:
            cn = get_connection();
            ds = st.selectbox("Excluir:", pd.read_sql("SELECT * FROM status_config", cn)['nome'].tolist());
            cn.close()
            if st.button("Apagar"): cn = get_connection(); cn.execute("DELETE FROM status_config WHERE nome=?",
                                                                      (ds,)); cn.commit(); cn.close(); st.rerun()

    st.divider()
    df = carregar_dados();
    cd = carregar_cores_status()
    if not df.empty:
        fl = st.selectbox("Lote:", ["Todos"] + df['lote'].unique().tolist())
        dff = df if fl == "Todos" else df[df['lote'] == fl]
        b = st.text_input("Buscar:");
        dff = dff[dff['frota'].str.contains(b, case=False)] if b else dff
        if not dff.empty:
            op = dff.apply(lambda x: f"{x['frota']} - {x['modelo']} | {x['status']}", axis=1)
            sel = st.selectbox("Selecione:", op);
            idx = op[op == sel].index[0];
            d = dff.loc[idx]
            st.info(f"**{d['frota']}** ({d['responsavel']})")
            with st.form("up"):
                c1, c2 = st.columns(2)
                ls = list(cd.keys());
                ix = ls.index(d['status']) if d['status'] in ls else 0
                ns = c1.selectbox("Status", ls, index=ix);
                np = c2.slider("%", 0, 100, int(d['progresso']))
                no = st.text_area("Obs", value=d['observacao'] or "")
                dg = carregar_gestores();
                lg = dg['nome'].tolist();
                ir = lg.index(d['responsavel']) if d['responsavel'] in lg else 0
                nr = st.selectbox("Resp:", lg, index=ir)
                if st.form_submit_button("Salvar", type="primary"):
                    cn = get_connection();
                    cn.execute("UPDATE reformas SET status=?, progresso=?, observacao=?, responsavel=? WHERE id=?",
                               (ns, np, no, nr, int(d['id'])));
                    cn.commit();
                    cn.close();
                    st.success("Salvo");
                    st.rerun()
        else:
            st.warning("Nada encontrado")