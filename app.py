import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from peritos import carregar_servidores
from fluxo import criar_fluxo_caixa

st.set_page_config(page_title="Fluxo de Caixa", layout="wide", initial_sidebar_state="expanded")

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
• Os intervalos de tempo entre promoções são configuráveis mas devem ser crescentes

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

# Cenário personalizado
st.sidebar.subheader("Cenário")
st.sidebar.markdown("**Tempo para cada promoção (anos):**")

cargo2_anos = st.sidebar.number_input("Cargo 1 → 2", min_value=1, max_value=20, value=5)
cargo3_anos = st.sidebar.number_input(
    "Cargo 2 → 3", min_value=1, max_value=30, value=10
)
cargo4_anos = st.sidebar.number_input(
    "Cargo 3 → 4", min_value=1, max_value=40, value=15
)

cenario_personalizado = [cargo2_anos, cargo3_anos, cargo4_anos]

# Validação
if cargo2_anos >= cargo3_anos or cargo3_anos >= cargo4_anos:
    st.sidebar.error("Os anos devem ser crescentes!")
    cenario_valido = False
else:
    st.sidebar.success(f"✅ Cenário: {cenario_personalizado}")
    cenario_valido = True

# Anos de projeção
anos = st.sidebar.slider("Anos de Projeção", min_value=5, max_value=35, value=10)


# Função para processar (substitua pela real)
@st.cache_data
def processar_comparacao(peritos, taxa, anos, cenario):
    """
    Processa os dois cenários para o servidor selecionado
    Substitua esta função pela importação real
    """
    # Filtrar apenas o servidor selecionado

    df_status_quo, _ = criar_fluxo_caixa(
        df_servidores=peritos,
        anos=anos,
        estrategia="status_quo",
        taxa=taxa,
    )
    df_cenario, _ = criar_fluxo_caixa(
        df_servidores=peritos,
        anos=anos,
        estrategia="cenario",
        cenario=cenario,
        taxa=taxa,
    )

    # Preparar dados para o gráfico com campos adicionais
    colunas_extras = (
        ["Nome", "CargoAtual", "MesPromocao", "Rendimento"]
        if all(
            col in df_status_quo.columns
            for col in ["Nome", "CargoAtual", "MesPromocao", "Rendimento"]
        )
        else []
    )
    colunas_base = ["Data", "VPL_Acumulado", "ValorAcumulado"]
    colunas_tabela = colunas_base + colunas_extras

    status_quo_data = df_status_quo[colunas_tabela].copy()
    status_quo_data["Cenario"] = "Status Quo"

    cenario_data = df_cenario[colunas_tabela].copy()
    cenario_data["Cenario"] = "Cenário"

    df_comparacao = pd.concat([status_quo_data, cenario_data])

    return df_comparacao


# Processar dados se cenário for válido
if cenario_valido:
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

    with st.spinner("🔄 Calculando fluxo de caixa..."):
        df_comparacao = processar_comparacao(
            peritos,
            taxa_desconto / 100,
            anos,
            cenario_personalizado,
        )

        df_filtrado = df_comparacao[df_comparacao["Nome"] == servidor_info["Nome"]]

        # Calcular métricas finais para VPL
        vpl_final_status_quo = df_filtrado[df_filtrado["Cenario"] == "Status Quo"][
            "VPL_Acumulado"
        ].iloc[-1]
        vpl_final_cenario = df_filtrado[df_filtrado["Cenario"] == "Cenário"][
            "VPL_Acumulado"
        ].iloc[-1]
        diferenca_vpl = vpl_final_cenario - vpl_final_status_quo
        percentual_vpl = (
            (diferenca_vpl / vpl_final_status_quo) * 100
            if vpl_final_status_quo != 0
            else 0
        )

        # Calcular métricas finais para Valor Nominal
        valor_final_status_quo = df_filtrado[df_filtrado["Cenario"] == "Status Quo"][
            "ValorAcumulado"
        ].iloc[-1]
        valor_final_cenario = df_filtrado[df_filtrado["Cenario"] == "Cenário"][
            "ValorAcumulado"
        ].iloc[-1]
        diferenca_valor = valor_final_cenario - valor_final_status_quo
        percentual_valor = (
            (diferenca_valor / valor_final_status_quo) * 100
            if valor_final_status_quo != 0
            else 0
        )

        # Métricas no topo - organizadas em duas seções
        st.subheader("📊 Métricas Financeiras")

        st.markdown("**Valor Presente Líquido (VPL)**")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Status Quo (VPL)",
                f"R$ {vpl_final_status_quo:,.0f}",
                help="Valor presente líquido no sistema atual",
            )

        with col2:
            st.metric(
                "Cenário (VPL)",
                f"R$ {vpl_final_cenario:,.0f}",
                help="Valor presente líquido no cenário configurado",
            )

with col3:
            st.metric(
                "Diferença VPL",
                f"R$ {diferenca_vpl:,.2f}",  # REMOVIDO O PERCENTUAL AQUI
                delta_color="normal" if diferenca_vpl >= 0 else "inverse",
                help="Diferença absoluta entre os cenários",
            )

        # Segunda linha - Valor Nominal
        st.markdown("**Valor Nominal Acumulado (sem desconto)**")
        col4, col5, col6 = st.columns(3)

        with col4:
            st.metric(
                "Status Quo (Nominal)",
                f"R$ {valor_final_status_quo:,.0f}",
                help="Valor nominal acumulado no sistema atual",
            )

        with col5:
            st.metric(
                "Cenário (Nominal)",
                f"R$ {valor_final_cenario:,.0f}",
                help="Valor nominal acumulado no cenário configurado",
            )

        with col6:
            st.metric(
                "Diferença Nominal",
                f"R$ {diferenca_valor:,.2f}",  # REMOVIDO O PERCENTUAL AQUI
                delta_color="normal" if diferenca_valor >= 0 else "inverse",
                help="Diferença absoluta entre os cenários (valor nominal)",
            )

        # Selector para tipo de gráfico
        st.subheader("📈 Comparação Temporal")

        tipo_grafico = st.radio(
            "Escolha o tipo de análise:",
            ["VPL Acumulado", "Valor Nominal Acumulado", "Ambos"],
            horizontal=True,
            help="VPL considera o valor do dinheiro no tempo, Valor Nominal não aplica desconto",
        )

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

            # Dados separados por cenário
            df_status_quo = df_filtrado[df_filtrado["Cenario"] == "Status Quo"]
            df_cenario_data = df_filtrado[df_filtrado["Cenario"] == "Cenário"]

            # Gráfico VPL (superior)
            fig.add_trace(
                go.Scatter(
                    x=df_status_quo["Data"],
                    y=df_status_quo["VPL_Acumulado"],
                    name="Status Quo (VPL)",
                    line=dict(color="#FF6B6B", width=3),
                ),
                row=1,
                col=1,
            )

            fig.add_trace(
                go.Scatter(
                    x=df_cenario_data["Data"],
                    y=df_cenario_data["VPL_Acumulado"],
                    name="Cenário (VPL)",
                    line=dict(color="#4ECDC4", width=3),
                ),
                row=1,
                col=1,
            )

            # Gráfico Valor Nominal (inferior)
            fig.add_trace(
                go.Scatter(
                    x=df_status_quo["Data"],
                    y=df_status_quo["ValorAcumulado"],
                    name="Status Quo (Nominal)",
                    line=dict(color="#FF6B6B", width=3, dash="dash"),
                ),
                row=2,
                col=1,
            )

            fig.add_trace(
                go.Scatter(
                    x=df_cenario_data["Data"],
                    y=df_cenario_data["ValorAcumulado"],
                    name="Cenário (Nominal)",
                    line=dict(color="#4ECDC4", width=3, dash="dash"),
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

            # Cores customizadas
            colors = [
                "#FF6B6B",
                "#4ECDC4",
            ]  # Vermelho para Status Quo, Verde-azulado para Cenário
            for i, trace in enumerate(fig.data):
                trace.line.color = colors[i]
                trace.line.width = 3

        st.plotly_chart(fig, use_container_width=True)

        # Resumo da análise
        st.subheader("📝 Resumo da Análise")

        # Análise do VPL
        col_vpl, col_nominal = st.columns(2)

        with col_vpl:
            st.markdown("**Análise VPL (Valor Presente)**")
            if diferenca_vpl > 0:
                st.success(
                    f"🎉 **Vantagem do Cenário**: R$ {diferenca_vpl:,.0f} (+{percentual_vpl:.1f}%)"
                )
            elif diferenca_vpl < 0:
                st.error(
                    f"📉 **Desvantagem do Cenário**: R$ {abs(diferenca_vpl):,.0f} ({percentual_vpl:.1f}%)"
                )
            else:
                st.info("⚖️ **Cenários Equivalentes em VPL**")

        with col_nominal:
            st.markdown("**Análise Valor Nominal**")
            if diferenca_valor > 0:
                st.success(
                    f"💰 **Vantagem do Cenário**: R$ {diferenca_valor:,.0f} (+{percentual_valor:.1f}%)"
                )
            elif diferenca_valor < 0:
                st.error(
                    f"💸 **Desvantagem do Cenário**: R$ {abs(diferenca_valor):,.0f} ({percentual_valor:.1f}%)"
                )
            else:
                st.info("⚖️ **Cenários Equivalentes em Valor Nominal**")

        # Explicação das diferenças
        st.info(
            """
            **💡 Entendendo as métricas:**
            
            - **VPL (Valor Presente Líquido)**: Considera que R$ 1 hoje vale mais que R$ 1 no futuro devido à taxa de desconto aplicada
            - **Valor Nominal**: Soma simples dos valores futuros, sem considerar o valor do dinheiro no tempo
            - **Diferença**: O VPL sempre será menor que o valor nominal para fluxos futuros
            """
        )

        # Mostrar dataframes que servem de base para o gráfico
        st.subheader("📋 Dados Detalhados")

        # Separar os dados por cenário
        df_status_quo_display = df_filtrado[
            df_filtrado["Cenario"] == "Status Quo"
        ].copy()
        df_cenario_display = df_filtrado[df_filtrado["Cenario"] == "Cenário"].copy()

        # Criar abas para melhor organização
        tab1, tab2 = st.tabs(["Status Quo", "Cenário"])

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
            "MesPromocao": st.column_config.DateColumn(
                "Mês Promoção", format="MM/YYYY"
            ),
        }

        with tab1:
            st.write("**Dados Status Quo:**")
            st.dataframe(
                df_status_quo_display,
                use_container_width=True,
                hide_index=True,
                column_config=column_config,
            )

        with tab2:
            st.write("**Dados do Cenário:**")
            st.dataframe(
                df_cenario_display,
                use_container_width=True,
                hide_index=True,
                column_config=column_config,
            )

else:
    st.warning("Configure um cenário válido na barra lateral (anos crescentes)")

# Rodapé
st.markdown("---")
st.caption("💡 Dashboard de Análise de Fluxo de Caixa - Peritos PCI")
