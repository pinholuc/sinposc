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


# Carregar dados
@st.cache_data
def obter_peritos():
    return carregar_servidores("peritos.xlsx")


peritos = obter_peritos()

# Taxa e anos de projeção (globais)
taxa_desconto = st.sidebar.slider(
    "Taxa de Desconto Anual (%)", min_value=1.0, max_value=15.0, value=6.0, step=0.5
)
anos = st.sidebar.slider("Anos de Projeção", min_value=5, max_value=35, value=10)

# Cenários disponíveis
cenarios_selecionados = ["Status Quo"] + [f"Regra {nome}" for nome in CENARIOS.keys()]

# ===================== SEÇÃO FIXA: VISÃO DO GOVERNO =====================
st.header("🏛️ Visão Governo SC")


@st.cache_data
def processar_custos_governo(peritos, taxa, anos, cenarios):
    """
    Processa os custos totais do governo para todos os servidores em cada cenário
    """
    custos_por_cenario = {}

    for cenario_nome in cenarios:
        if cenario_nome == "Status Quo":
            df_fluxo, _ = criar_fluxo_caixa(
                df_servidores=peritos,
                anos=anos,
                estrategia="status_quo",
                taxa=taxa,
            )
        else:
            cenario_key = cenario_nome.replace("Regra ", "")
            df_fluxo, _ = criar_fluxo_caixa(
                df_servidores=peritos,
                anos=anos,
                estrategia="cenario",
                cenario=CENARIOS[cenario_key],
                taxa=taxa,
            )

        # Verificar quais colunas estão disponíveis
        # Possíveis nomes de colunas para rendimento/salário
        col_rendimento = None
        for col in ["Rendimento", "Salario", "ValorMensal", "Valor"]:
            if col in df_fluxo.columns:
                col_rendimento = col
                break

        if not col_rendimento:
            st.error(
                f"Não foi possível encontrar coluna de rendimento. Colunas disponíveis: {df_fluxo.columns.tolist()}"
            )
            continue

        # Agregar custos por data
        custos_agregados = (
            df_fluxo.groupby("Data").agg({col_rendimento: "sum"}).reset_index()
        )
        custos_agregados.rename(columns={col_rendimento: "Rendimento"}, inplace=True)

        # Calcular VPL manualmente se não existir
        custos_agregados["VPL"] = custos_agregados.apply(
            lambda row: row["Rendimento"]
            / (
                (1 + taxa)
                ** ((row["Data"] - custos_agregados["Data"].min()).days / 365.25)
            ),
            axis=1,
        )

        # Calcular acumulados
        custos_agregados["CustoNominalAcumulado"] = custos_agregados[
            "Rendimento"
        ].cumsum()
        custos_agregados["CustoVPLAcumulado"] = custos_agregados["VPL"].cumsum()
        custos_agregados["Cenario"] = cenario_nome

        custos_por_cenario[cenario_nome] = custos_agregados

    return pd.concat(custos_por_cenario.values())


# Processar custos do governo
with st.spinner("🔄 Calculando custos totais do governo..."):
    df_custos_governo = processar_custos_governo(
        peritos, taxa_desconto / 100, anos, cenarios_selecionados
    )

# Tabs para diferentes visualizações
tab_resumo, tab_temporal, tab_evolucao_carreiras, tab_detalhes = st.tabs(
    [
        "📊 Resumo",
        "📈 Evolução Temporal",
        "📊 Evolução das Carreiras",
        "📋 Dados Detalhados",
    ]
)

with tab_resumo:
    # Calcular métricas para os 4 primeiros anos (2025, 2026, 2027, 2028)
    df_custos_4anos = df_custos_governo.copy()
    df_custos_4anos["Ano"] = pd.to_datetime(df_custos_4anos["Data"]).dt.year
    df_custos_4anos = df_custos_4anos[df_custos_4anos["Ano"].isin([2025, 2026, 2027, 2028])]

    # Agregar custos dos 4 primeiros anos por cenário
    custos_4anos = (
        df_custos_4anos.groupby(["Cenario", "Ano"])
        .agg({"Rendimento": "sum", "VPL": "sum"})
        .reset_index()
    )

    # Calcular totais dos 4 anos
    totais_4anos = (
        custos_4anos.groupby("Cenario")
        .agg({"Rendimento": "sum", "VPL": "sum"})
        .reset_index()
    )

    # Exibir métricas em colunas
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Total de Servidores",
            f"{len(peritos):,}",
            help="Número total de peritos incluídos na análise",
        )

    with col2:
        st.metric(
            "Período de Análise",
            "2025-2028",
            help="Foco nos 4 primeiros anos de implementação",
        )

    with col3:
        st.metric(
            "Taxa de Desconto",
            f"{taxa_desconto}% a.a.",
            help="Taxa utilizada para cálculo do VPL",
        )

    # Tabela comparativa para os 4 primeiros anos
    st.subheader("Comparação de Custos - Primeiros 4 Anos (2025-2028)")

    # Preparar dados para exibição anual
    df_display_anual = custos_4anos.pivot(
        index="Cenario", columns="Ano", values="Rendimento"
    ).reset_index()
    df_display_anual["Total 4 Anos"] = df_display_anual[[2025, 2026, 2027, 2028]].sum(axis=1)

    # Reorganizar para que Status Quo apareça primeiro
    if "Status Quo" in df_display_anual["Cenario"].values:
        # Separar Status Quo dos demais cenários
        status_quo_row = df_display_anual[df_display_anual["Cenario"] == "Status Quo"]
        outros_cenarios = df_display_anual[df_display_anual["Cenario"] != "Status Quo"]
        
        # Reorganizar com Status Quo primeiro
        df_display_anual = pd.concat([status_quo_row, outros_cenarios], ignore_index=True)

    # Calcular diferenças em relação ao Status Quo
    if "Status Quo" in df_display_anual["Cenario"].values:
        sq_2025 = df_display_anual[df_display_anual["Cenario"] == "Status Quo"][
            2025
        ].values[0]
        sq_2026 = df_display_anual[df_display_anual["Cenario"] == "Status Quo"][
            2026
        ].values[0]
        sq_2027 = df_display_anual[df_display_anual["Cenario"] == "Status Quo"][
            2027
        ].values[0]
        sq_2028 = df_display_anual[df_display_anual["Cenario"] == "Status Quo"][
            2028
        ].values[0]
        sq_total = df_display_anual[df_display_anual["Cenario"] == "Status Quo"][
            "Total 4 Anos"
        ].values[0]

        # Adicionar colunas de impacto
        df_display_anual["Impacto 2025"] = df_display_anual.apply(
            lambda row: (
                f"{(row[2025] - sq_2025):+,.0f}"
                if row["Cenario"] != "Status Quo"
                else "-"
            ),
            axis=1,
        )
        df_display_anual["Impacto 2026"] = df_display_anual.apply(
            lambda row: (
                f"{(row[2026] - sq_2026):+,.0f}"
                if row["Cenario"] != "Status Quo"
                else "-"
            ),
            axis=1,
        )
        df_display_anual["Impacto 2027"] = df_display_anual.apply(
            lambda row: (
                f"{(row[2027] - sq_2027):+,.0f}"
                if row["Cenario"] != "Status Quo"
                else "-"
            ),
            axis=1,
        )
        df_display_anual["Impacto 2028"] = df_display_anual.apply(
            lambda row: (
                f"{(row[2028] - sq_2028):+,.0f}"
                if row["Cenario"] != "Status Quo"
                else "-"
            ),
            axis=1,
        )
        df_display_anual["Impacto Total"] = df_display_anual.apply(
            lambda row: (
                f"{(row['Total 4 Anos'] - sq_total):+,.0f} ({((row['Total 4 Anos'] - sq_total) / sq_total * 100):+.1f}%)"
                if row["Cenario"] != "Status Quo"
                else "-"
            ),
            axis=1,
        )

    # Formatar valores monetários
    df_display_anual["2025 (R$)"] = df_display_anual[2025].apply(lambda x: f"{x:,.0f}")
    df_display_anual["2026 (R$)"] = df_display_anual[2026].apply(lambda x: f"{x:,.0f}")
    df_display_anual["2027 (R$)"] = df_display_anual[2027].apply(lambda x: f"{x:,.0f}")
    df_display_anual["2028 (R$)"] = df_display_anual[2028].apply(lambda x: f"{x:,.0f}")
    df_display_anual["Total 4 Anos (R$)"] = df_display_anual["Total 4 Anos"].apply(
        lambda x: f"{x:,.0f}"
    )

    # Selecionar colunas para exibição
    colunas_exibir = [
        "Cenario",
        "2025 (R$)",
        "2026 (R$)",
        "2027 (R$)",
        "2028 (R$)",
        "Total 4 Anos (R$)",
    ]
    if "Impacto Total" in df_display_anual.columns:
        colunas_exibir.extend(
            ["Impacto 2025", "Impacto 2026", "Impacto 2027", "Impacto 2028", "Impacto Total"]
        )

    def highlight_impacto_governo(val):
        if isinstance(val, str) and val != "-":
            if val.startswith("+"):
                return "color: red; font-weight: bold"  # Custos adicionais em vermelho
            elif val.startswith("-") and not val.startswith("--"):
                return "color: green; font-weight: bold"  # Economia em verde
        return ""

    styled_df_gov = df_display_anual[colunas_exibir].style.applymap(
        highlight_impacto_governo,
        subset=[
            col
            for col in ["Impacto 2025", "Impacto 2026", "Impacto 2027", "Impacto 2028", "Impacto Total"]
            if col in colunas_exibir
        ],
    )

    st.write("**Valores Nominais (sem desconto)**")
    st.write(styled_df_gov)

    # Adicionar gráfico de barras para os 4 anos
    st.markdown("---")
    st.subheader("Visualização dos Custos - Primeiros 4 Anos")

    # Preparar dados para o gráfico
    df_grafico = custos_4anos[custos_4anos["Ano"].isin([2025, 2026, 2027, 2028])]

    fig_4anos = px.bar(
        df_grafico,
        x="Ano",
        y="Rendimento",
        color="Cenario",
        barmode="group",
        title="Gastos Nominais Anuais (2025-2028)",
        labels={"Rendimento": "Gasto Anual (R$)", "Cenario": "Cenário"},
        color_discrete_map={
            "Status Quo": "#FF6B6B",
            "Regra 5-10-15": "#4ECDC4",
            "Regra 4-8-16": "#95E1D3",
            "Regra 3-6-15": "#C7CEEA",
            "Regra 3-6-16": "#FECA57",
        },
        text="Rendimento",
    )

    fig_4anos.update_traces(texttemplate="R$ %{text:,.0f}", textposition="outside")
    fig_4anos.update_layout(height=500)

    st.plotly_chart(fig_4anos, use_container_width=True)

with tab_temporal:
    st.subheader("Evolução dos Custos Governamentais")

    # Opção para escolher visualização
    tipo_visualizacao = "Gastos Anuais"

    # Definir cores para cada cenário
    cores_cenarios = {
        "Status Quo": "#FF6B6B",
        "Regra 5-10-15": "#4ECDC4",
        "Regra 4-8-16": "#95E1D3",
        "Regra 3-6-15": "#C7CEEA",
        "Regra 3-6-16": "#FECA57",
    }

    if tipo_visualizacao == "Gastos Anuais":
        # Preparar dados anuais
        df_custos_anuais = df_custos_governo.copy()
        df_custos_anuais["Ano"] = pd.to_datetime(df_custos_anuais["Data"]).dt.year

        # Agregar por ano e cenário
        gastos_anuais = (
            df_custos_anuais.groupby(["Ano", "Cenario"])
            .agg({"Rendimento": "sum", "VPL": "sum"})
            .reset_index()
        )

        # Criar gráfico de barras comparativo
        fig_anual = make_subplots(
            rows=2,
            cols=1,
            subplot_titles=(
                "Gastos Anuais - Valor Presente Líquido (VPL)",
                "Gastos Anuais - Valor Nominal",
            ),
            vertical_spacing=0.15,
        )

        # Gráfico de barras VPL
        for cenario in cenarios_selecionados:
            dados_cenario = gastos_anuais[gastos_anuais["Cenario"] == cenario]
            fig_anual.add_trace(
                go.Bar(
                    x=dados_cenario["Ano"],
                    y=dados_cenario["VPL"],
                    name=cenario,
                    marker_color=cores_cenarios.get(cenario, "#888888"),
                    legendgroup=cenario,
                ),
                row=1,
                col=1,
            )

        # Gráfico de barras Nominal
        for cenario in cenarios_selecionados:
            dados_cenario = gastos_anuais[gastos_anuais["Cenario"] == cenario]
            fig_anual.add_trace(
                go.Bar(
                    x=dados_cenario["Ano"],
                    y=dados_cenario["Rendimento"],
                    name=cenario,
                    marker_color=cores_cenarios.get(cenario, "#888888"),
                    legendgroup=cenario,
                    showlegend=False,
                ),
                row=2,
                col=1,
            )

        # Atualizar layout
        fig_anual.update_xaxes(title_text="Ano", row=2, col=1)
        fig_anual.update_yaxes(title_text="Gasto Anual VPL (R$)", row=1, col=1)
        fig_anual.update_yaxes(title_text="Gasto Anual Nominal (R$)", row=2, col=1)

        fig_anual.update_layout(
            height=800,
            title_text=f"Gastos Anuais do Governo com Peritos ({anos} anos)",
            hovermode="x unified",
            barmode="group",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
        )

        st.plotly_chart(fig_anual, use_container_width=True)

        # Tabela resumo anual
        st.subheader("Resumo dos Gastos Anuais")

        # Pivot table para melhor visualização
        tabela_vpl = gastos_anuais.pivot(index="Ano", columns="Cenario", values="VPL")
        tabela_nominal = gastos_anuais.pivot(
            index="Ano", columns="Cenario", values="Rendimento"
        )

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Gastos Anuais - VPL (R$)**")
            st.dataframe(tabela_vpl.style.format("{:,.0f}"), use_container_width=True)

        with col2:
            st.write("**Gastos Anuais - Nominal (R$)**")
            st.dataframe(
                tabela_nominal.style.format("{:,.0f}"), use_container_width=True
            )

with tab_evolucao_carreiras:
    st.subheader("Distribuição Final de Cargos por Carreira")

    # Função para processar evolução de carreiras
    @st.cache_data
    def processar_evolucao_carreiras(peritos, taxa, anos, cenario_nome):
        """
        Processa a evolução das carreiras ao longo do tempo para um cenário específico
        """
        if cenario_nome == "Status Quo":
            df_fluxo, _ = criar_fluxo_caixa(
                df_servidores=peritos,
                anos=anos,
                estrategia="status_quo",
                taxa=taxa,
            )
        else:
            cenario_key = cenario_nome.replace("Regra ", "")
            df_fluxo, _ = criar_fluxo_caixa(
                df_servidores=peritos,
                anos=anos,
                estrategia="cenario",
                cenario=CENARIOS[cenario_key],
                taxa=taxa,
            )

        # Verificar se as colunas necessárias existem
        if "TipoPerito" in df_fluxo.columns and "CargoAtual" in df_fluxo.columns:
            # Converter números de cargo para formato "Cargo X"
            df_fluxo["CargoAtual"] = df_fluxo["CargoAtual"].apply(
                lambda x: f"Cargo {x}"
            )

            # Agrupar por data, tipo de perito e cargo
            evolucao = (
                df_fluxo.groupby(["Data", "TipoPerito", "CargoAtual"])
                .size()
                .reset_index(name="Quantidade")
            )
            evolucao["Cenario"] = cenario_nome
            return evolucao
        else:
            st.error(
                f"Colunas necessárias não encontradas. Colunas disponíveis: {df_fluxo.columns.tolist()}"
            )
            return pd.DataFrame()

    # Seletor de cenário
    cenario_selecionado_carreiras = st.selectbox(
        "Selecione o Cenário para Análise:",
        options=cenarios_selecionados,
        help="Escolha o cenário para visualizar a distribuição final das carreiras",
    )

    # Processar dados
    with st.spinner("🔄 Processando distribuição das carreiras..."):
        df_evolucao = processar_evolucao_carreiras(
            peritos, taxa_desconto / 100, anos, cenario_selecionado_carreiras
        )

    if not df_evolucao.empty:
        # Pegar apenas a última data (distribuição final)
        ultima_data = df_evolucao["Data"].max()
        df_final = df_evolucao[df_evolucao["Data"] == ultima_data].copy()

        # Criar mapeamento de tipos para nomes mais amigáveis
        mapa_tipos = {
            "criminal": "Perito Criminal",
            "bioquimico": "Perito Bioquímico",
            "legista": "Perito Médico-Legista",
            "odonto": "Perito Odonto-Legista",
        }

        # Aplicar mapeamento
        df_final["TipoPerito"] = (
            df_final["TipoPerito"].map(mapa_tipos).fillna(df_final["TipoPerito"])
        )

        # Criar tabela pivot
        tabela_final = df_final.pivot_table(
            index="TipoPerito",
            columns="CargoAtual",
            values="Quantidade",
            aggfunc="sum",
            fill_value=0,
        ).reset_index()

        # Garantir que todas as colunas de cargo existam
        cargos_esperados = ["Cargo 1", "Cargo 2", "Cargo 3", "Cargo 4"]
        for cargo in cargos_esperados:
            if cargo not in tabela_final.columns:
                tabela_final[cargo] = 0

        # Reordenar colunas
        colunas_ordenadas = ["TipoPerito"] + cargos_esperados
        tabela_final = tabela_final[colunas_ordenadas]

        # Calcular total por tipo de perito
        tabela_final["Total"] = tabela_final[cargos_esperados].sum(axis=1)

        # Renomear coluna
        tabela_final = tabela_final.rename(columns={"TipoPerito": "Tipo de Perito"})

        # Exibir tabela
        st.subheader(
            f"Distribuição Final de Cargos - {cenario_selecionado_carreiras} (Ano {ultima_data.year})"
        )

        # Formatar tabela para exibição
        st.dataframe(
            tabela_final,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Tipo de Perito": st.column_config.TextColumn(
                    "Tipo de Perito", width="medium"
                ),
                "Cargo 1": st.column_config.NumberColumn("Cargo 1", format="%d"),
                "Cargo 2": st.column_config.NumberColumn("Cargo 2", format="%d"),
                "Cargo 3": st.column_config.NumberColumn("Cargo 3", format="%d"),
                "Cargo 4": st.column_config.NumberColumn("Cargo 4", format="%d"),
                "Total": st.column_config.NumberColumn("Total", format="%d"),
            },
        )

        # Adicionar linha de totais
        st.subheader("Consolidado")

        # Calcular totais por cargo
        totais_por_cargo = tabela_final[cargos_esperados + ["Total"]].sum()

        # Criar dataframe dos totais
        df_totais = pd.DataFrame(
            {
                "Cargo": cargos_esperados + ["Total Geral"],
                "Quantidade": [totais_por_cargo[cargo] for cargo in cargos_esperados]
                + [totais_por_cargo["Total"]],
            }
        )

        # Exibir totais em colunas
        cols = st.columns(len(cargos_esperados) + 1)

        for i, (cargo, quantidade) in enumerate(
            zip(df_totais["Cargo"], df_totais["Quantidade"])
        ):
            with cols[i]:
                if cargo == "Total Geral":
                    st.metric(
                        "Total Geral",
                        f"{int(quantidade):,}",
                        help="Total de peritos ativos",
                    )
                else:
                    percentual = (
                        (quantidade / totais_por_cargo["Total"] * 100)
                        if totais_por_cargo["Total"] > 0
                        else 0
                    )
                    st.metric(
                        cargo,
                        f"{int(quantidade):,}",
                        f"{percentual:.1f}%",
                        help=f"Percentual do total: {percentual:.1f}%",
                    )

        # Botão para download da tabela
        csv_carreiras = tabela_final.to_csv(index=False)
        st.download_button(
            label="📥 Baixar tabela em CSV",
            data=csv_carreiras,
            file_name=f"distribuicao_carreiras_{cenario_selecionado_carreiras}_{ultima_data.year}.csv",
            mime="text/csv",
        )

    else:
        st.error(
            "Não foi possível processar a evolução das carreiras. Verifique se os dados contêm as informações necessárias."
        )

with tab_detalhes:
    st.subheader("Dados Detalhados dos Custos Governamentais")

    # Permitir download dos dados
    csv = df_custos_governo.to_csv(index=False)
    st.download_button(
        label="📥 Baixar dados em CSV",
        data=csv,
        file_name=f"custos_governo_{anos}anos.csv",
        mime="text/csv",
    )

    # Mostrar tabela de dados
    st.dataframe(
        df_custos_governo,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "Rendimento": st.column_config.NumberColumn(
                "Custo Mensal", format="R$ %.2f"
            ),
            "VPL": st.column_config.NumberColumn("VPL Mensal", format="R$ %.2f"),
            "CustoNominalAcumulado": st.column_config.NumberColumn(
                "Custo Nominal Acumulado", format="R$ %.2f"
            ),
            "CustoVPLAcumulado": st.column_config.NumberColumn(
                "Custo VPL Acumulado", format="R$ %.2f"
            ),
        },
    )

# Separador visual
st.markdown("---")
st.markdown("## 👤 Visão Servidor")

# ===================== SEÇÃO ORIGINAL: VISÃO DO SERVIDOR =====================

# Seletor de servidor
nomes_disponiveis = sorted(peritos["Nome"].unique().tolist())

servidor_selecionado = st.sidebar.selectbox(
    "Selecione o Servidor",
    options=[""] + nomes_disponiveis,
    index=0,
    help="Escolha o servidor para análise individual do fluxo de caixa",
)

# Se nenhum servidor for selecionado, mostrar tela em branco
if not servidor_selecionado:
    st.info(
        "Selecione um servidor na barra lateral para visualizar o fluxo de caixa individual"
    )
    st.stop()


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

    # Reorganizar para que Status Quo apareça primeiro
    if "Status Quo" in df_metricas["Cenário"].values:
        # Separar Status Quo dos demais cenários
        status_quo_row = df_metricas[df_metricas["Cenário"] == "Status Quo"]
        outros_cenarios = df_metricas[df_metricas["Cenário"] != "Status Quo"]
        
        # Reorganizar com Status Quo primeiro
        df_metricas = pd.concat([status_quo_row, outros_cenarios], ignore_index=True)

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
    st.subheader("Resumo Comparativo dos Cenários")

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
    st.markdown("---")
    st.subheader("Comparação Temporal")

    tipo_grafico = st.radio(
        "Escolha o tipo de análise:",
        ["VPL Acumulado", "Valor Nominal Acumulado"],
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

    else:  # Valor Nominal Acumulado
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

    # Customizar o gráfico
    fig.update_layout(
        height=600,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
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
