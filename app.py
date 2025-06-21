import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from peritos import carregar_servidores
from fluxo import criar_fluxo_caixa, CENARIOS, processar_todos_cenarios

st.set_page_config(page_title="Fluxo de Caixa", layout="wide")

st.title("💰 Fluxo de Caixa - Peritos PCI")

# DISCLAIMER COM PREMISSAS
st.warning(
    """
⚠️ **PREMISSAS IMPORTANTES DESTA ANÁLISE**

**1. Premissa sobre Promoções (Ago/2026):**  
Irão acontecer em agosto/2026 conforme artigo 69 do anteprojeto de Lei.

**2. Premissa sobre Aposentadoria:**  
O cálculo considera que os servidores se aposentam após 30 anos de carreira contando a partir de uma data base.
Não está sendo considerada a idade dos servidores.

**3. Premissa sobre Progressão na Carreira:**  
• As promoções seguem uma sequência linear (Cargo 1 → 2 → 3 → 4)  
• Os intervalos de tempo entre promoções variam conforme o cenário escolhido

**4. Premissa Financeira:**  
A taxa de desconto utilizada no cálculo do VPL representa o custo de oportunidade do capital e permite 
comparar valores em diferentes períodos. O valor nominal não considera o valor do dinheiro no tempo.
Os valores de salários são referentes aos valores a serem praticados em janeiro/2026 após consolidação de todas 
as parcelas relacionadas ao reajuste de 21,5%.
"""
)

st.markdown("---")

# Sidebar para configurações
st.sidebar.header("Configurações")


# Seletor de servidor
@st.cache_data
def obter_peritos():
    return carregar_servidores("peritos.xlsx")


peritos = obter_peritos()

# Obter lista de nomes únicos
nomes_disponiveis = sorted(peritos["Nome"].unique().tolist())

servidor_selecionado = st.sidebar.selectbox(
    "Selecione o Servidor",
    options=[""] + nomes_disponiveis,
    index=0,
    help="Escolha o servidor para análise do fluxo de caixa",
)

# Se nenhum servidor for selecionado, mostrar tela em branco
if not servidor_selecionado:
    st.info("Selecione um servidor na barra lateral para visualizar o fluxo de caixa")
    st.stop()

# Taxa
taxa_desconto = st.sidebar.slider(
    "Taxa de Desconto Anual (%)", min_value=1.0, max_value=15.0, value=6.0, step=0.5
)

# Anos de projeção
anos = st.sidebar.slider("Anos de Projeção", min_value=5, max_value=35, value=10)
cenarios_selecionados = ["Status Quo"] + [f"Regra {nome}" for nome in CENARIOS.keys()]


# Função para processar dados
@st.cache_data
def processar_comparacao_multipla(peritos, taxa, anos, cenarios_selecionados):
    """
    Processa múltiplos cenários para o servidor selecionado
    """
    todos_dados = []

    for cenario_nome in cenarios_selecionados:
        if cenario_nome == "Status Quo":
            df_fluxo, _ = criar_fluxo_caixa(
                df_servidores=peritos,
                anos=anos,
                estrategia="status_quo",
                taxa=taxa,
            )
        else:
            # Extrair nome do cenário (remover "Regra ")
            cenario_key = cenario_nome.replace("Regra ", "")
            df_fluxo, _ = criar_fluxo_caixa(
                df_servidores=peritos,
                anos=anos,
                estrategia="cenario",
                cenario=CENARIOS[cenario_key],
                taxa=taxa,
            )

        # Preparar dados para o gráfico
        colunas_extras = (
            ["Nome", "CargoAtual", "MesPromocao", "Rendimento"]
            if all(
                col in df_fluxo.columns
                for col in ["Nome", "CargoAtual", "MesPromocao", "Rendimento"]
            )
            else []
        )
        colunas_base = ["Data", "VPL_Acumulado", "ValorAcumulado"]
        colunas_tabela = colunas_base + colunas_extras

        dados_cenario = df_fluxo[colunas_tabela].copy()
        dados_cenario["Cenario"] = cenario_nome
        todos_dados.append(dados_cenario)

    df_comparacao = pd.concat(todos_dados)
    return df_comparacao


# Mostrar informações do servidor selecionado
servidor_info = peritos[peritos["Nome"] == servidor_selecionado].iloc[0]

st.subheader(f"Análise para: {servidor_selecionado}")

# Mostrar informações básicas do servidor
col_info1, col_info2, col_info3 = st.columns(3)

with col_info1:
    if "Cargo" in servidor_info:
        st.write(f"**Cargo Atual:** {servidor_info['Cargo']}")

with col_info2:
    if "Salario" in servidor_info:
        st.write(f"**Salário:** R$ {servidor_info['Salario']:,.2f}")

with col_info3:
    if "Anos_Servico" in servidor_info:
        st.write(f"**Anos de Serviço:** {servidor_info['Anos_Servico']}")

with st.spinner("🔄 Calculando fluxo de caixa para todos os cenários..."):
    df_comparacao = processar_comparacao_multipla(
        peritos,
        taxa_desconto / 100,
        anos,
        cenarios_selecionados,
    )

    df_filtrado = df_comparacao[df_comparacao["Nome"] == servidor_info["Nome"]]

    # Calcular métricas finais para todos os cenários
    metricas_cenarios = []

    for cenario in cenarios_selecionados:
        df_cenario = df_filtrado[df_filtrado["Cenario"] == cenario]

        if len(df_cenario) > 0:
            vpl_final = df_cenario["VPL_Acumulado"].iloc[-1]
            valor_final = df_cenario["ValorAcumulado"].iloc[-1]

            metricas_cenarios.append(
                {
                    "Cenário": cenario,
                    "VPL Final": vpl_final,
                    "Valor Nominal Final": valor_final,
                }
            )

    df_metricas = pd.DataFrame(metricas_cenarios)

    # Calcular diferenças em relação ao Status Quo (se disponível)
    if "Status Quo" in df_metricas["Cenário"].values:
        vpl_status_quo = df_metricas[df_metricas["Cenário"] == "Status Quo"][
            "VPL Final"
        ].values[0]
        valor_status_quo = df_metricas[df_metricas["Cenário"] == "Status Quo"][
            "Valor Nominal Final"
        ].values[0]

        df_metricas["Diferença VPL (R$)"] = df_metricas["VPL Final"] - vpl_status_quo
        df_metricas["Diferença VPL (%)"] = (
            df_metricas["Diferença VPL (R$)"] / vpl_status_quo * 100
        ).round(1)
        df_metricas["Diferença Nominal (R$)"] = (
            df_metricas["Valor Nominal Final"] - valor_status_quo
        )
        df_metricas["Diferença Nominal (%)"] = (
            df_metricas["Diferença Nominal (R$)"] / valor_status_quo * 100
        ).round(1)

    # Métricas no topo - tabela comparativa
    st.subheader("📊 Resumo Comparativo dos Cenários")

    # Preparar dados para exibição
    df_display = df_metricas.copy()

    # Formatar valores monetários
    df_display["VPL Final (R$)"] = df_display["VPL Final"].apply(lambda x: f"{x:,.0f}")
    df_display["Valor Nominal Final (R$)"] = df_display["Valor Nominal Final"].apply(
        lambda x: f"{x:,.0f}"
    )

    # Se houver diferenças calculadas, formatá-las
    if "Diferença VPL (R$)" in df_display.columns:
        df_display["Diferença VPL"] = df_display.apply(
            lambda row: (
                f"{row['Diferença VPL (R$)']:+,.0f} ({row['Diferença VPL (%)']:+.1f}%)"
                if row["Cenário"] != "Status Quo"
                else "-"
            ),
            axis=1,
        )
        df_display["Diferença Nominal"] = df_display.apply(
            lambda row: (
                f"{row['Diferença Nominal (R$)']:+,.0f} ({row['Diferença Nominal (%)']:+.1f}%)"
                if row["Cenário"] != "Status Quo"
                else "-"
            ),
            axis=1,
        )

        # Selecionar colunas para exibição
        colunas_exibir = [
            "Cenário",
            "VPL Final (R$)",
            "Valor Nominal Final (R$)",
            "Diferença VPL",
            "Diferença Nominal",
        ]
    else:
        colunas_exibir = ["Cenário", "VPL Final (R$)", "Valor Nominal Final (R$)"]

    def highlight_diferencas(val):
        if isinstance(val, str) and val != "-":
            if val.startswith("+"):
                return "color: green"
            elif val.startswith("-"):
                return "color: red"
        return ""

    # Aplicar estilo condicional
    styled_df = df_display[colunas_exibir].style.applymap(
        highlight_diferencas, subset=["Diferença VPL", "Diferença Nominal"]
    )

    st.write(styled_df)

    # Gráficos comparativos
    st.subheader("📈 Comparação Temporal")

    tipo_grafico = st.radio(
        "Escolha o tipo de análise:",
        ["VPL Acumulado", "Valor Nominal Acumulado", "Ambos"],
        horizontal=True,
        help="VPL considera o valor do dinheiro no tempo, Valor Nominal não aplica desconto",
    )

    # Definir cores para cada cenário
    cores_cenarios = {
        "Status Quo": "#FF6B6B",
        "Regra 5-10-15": "#4ECDC4",
        "Regra 4-8-16": "#95E1D3",
        "Regra 3-6-15": "#C7CEEA",
        "Regra 3-6-16": "#FECA57",
    }

    if tipo_grafico == "VPL Acumulado":
        # Gráfico VPL
        fig = px.line(
            df_filtrado,
            x="Data",
            y="VPL_Acumulado",
            color="Cenario",
            title=f"Evolução do VPL Acumulado - {servidor_selecionado} ({anos} anos)",
            labels={
                "VPL_Acumulado": "VPL Acumulado (R$)",
                "Data": "Data",
                "Cenario": "Cenário",
            },
            color_discrete_map=cores_cenarios,
        )

    elif tipo_grafico == "Valor Nominal Acumulado":
        # Gráfico Valor Nominal
        fig = px.line(
            df_filtrado,
            x="Data",
            y="ValorAcumulado",
            color="Cenario",
            title=f"Evolução do Valor Nominal Acumulado - {servidor_selecionado} ({anos} anos)",
            labels={
                "ValorAcumulado": "Valor Nominal Acumulado (R$)",
                "Data": "Data",
                "Cenario": "Cenário",
            },
            color_discrete_map=cores_cenarios,
        )

    else:  # Ambos
        # Criar subplot com dois gráficos
        fig = make_subplots(
            rows=2,
            cols=1,
            subplot_titles=(
                "VPL Acumulado (com desconto)",
                "Valor Nominal Acumulado (sem desconto)",
            ),
            vertical_spacing=0.1,
        )

        # Adicionar traces para cada cenário
        for i, cenario in enumerate(cenarios_selecionados):
            df_cenario = df_filtrado[df_filtrado["Cenario"] == cenario]
            cor = cores_cenarios.get(cenario, "#888888")

            # Gráfico VPL (superior)
            fig.add_trace(
                go.Scatter(
                    x=df_cenario["Data"],
                    y=df_cenario["VPL_Acumulado"],
                    name=f"{cenario} (VPL)",
                    line=dict(color=cor, width=3),
                    legendgroup=cenario,
                ),
                row=1,
                col=1,
            )

            # Gráfico Valor Nominal (inferior)
            fig.add_trace(
                go.Scatter(
                    x=df_cenario["Data"],
                    y=df_cenario["ValorAcumulado"],
                    name=f"{cenario} (Nominal)",
                    line=dict(color=cor, width=3, dash="dash"),
                    legendgroup=cenario,
                    showlegend=False,
                ),
                row=2,
                col=1,
            )

        # Atualizar layout dos eixos Y
        fig.update_yaxes(title_text="VPL Acumulado (R$)", row=1, col=1)
        fig.update_yaxes(title_text="Valor Nominal (R$)", row=2, col=1)
        fig.update_xaxes(title_text="Data", row=2, col=1)

        fig.update_layout(
            height=800,
            title_text=f"Comparação Completa - {servidor_selecionado} ({anos} anos)",
            hovermode="x unified",
        )

    # Customizar o gráfico (para gráficos simples)
    if tipo_grafico != "Ambos":
        fig.update_layout(
            height=600,
            hovermode="x unified",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
        )

        # Aplicar largura de linha
        for trace in fig.data:
            trace.line.width = 3

    st.plotly_chart(fig, use_container_width=True)

    # Mostrar dados detalhados em abas
    st.subheader("📋 Dados Detalhados por Cenário")

    tabs = st.tabs(cenarios_selecionados)

    # Configuração das colunas para exibição
    column_config = {
        "Cenario": "Cenário",
        "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
        "VPL_Acumulado": st.column_config.NumberColumn(
            "VPL Acumulado", format="R$ %.2f"
        ),
        "ValorAcumulado": st.column_config.NumberColumn(
            "Valor Nominal", format="R$ %.2f"
        ),
        "Cargo": "Cargo",
        "TipoPerito": "Tipo Perito",
        "MesPromocao": st.column_config.DateColumn("Mês Promoção", format="MM/YYYY"),
    }

    for i, cenario in enumerate(cenarios_selecionados):
        with tabs[i]:
            df_cenario_display = df_filtrado[df_filtrado["Cenario"] == cenario].copy()
            st.write(f"**Dados do {cenario}:**")
            st.dataframe(
                df_cenario_display,
                use_container_width=True,
                hide_index=True,
                column_config=column_config,
            )

# Rodapé
st.markdown("---")
st.caption("💡 Dashboard de Análise de Fluxo de Caixa - Peritos PCI")
