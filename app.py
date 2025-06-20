import streamlit as st
import pandas as pd
import plotly.express as px
from peritos import carregar_servidores
from fluxo import criar_fluxo_caixa

st.set_page_config(page_title="Fluxo de Caixa", layout="wide")

st.title("💰 Fluxo de Caixa - Peritos PCI")
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
    colunas_base = ["Data", "VPL_Acumulado"]
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

        # Calcular métricas finais
        vpl_final_status_quo = df_filtrado[df_filtrado["Cenario"] == "Status Quo"][
            "VPL_Acumulado"
        ].iloc[-1]
        vpl_final_cenario = df_filtrado[df_filtrado["Cenario"] == "Cenário"][
            "VPL_Acumulado"
        ].iloc[-1]
        diferenca = vpl_final_cenario - vpl_final_status_quo
        percentual = (
            (diferenca / vpl_final_status_quo) * 100 if vpl_final_status_quo != 0 else 0
        )

        # Métricas no topo
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Status Quo (VPL Final)",
                f"R$ {vpl_final_status_quo:,.0f}",
                help="Valor presente líquido no sistema atual",
            )

        with col2:
            st.metric(
                "Cenário (VPL Final)",
                f"R$ {vpl_final_cenario:,.0f}",
                help="Valor presente líquido no cenário configurado",
            )

        with col3:
            st.metric(
                "Diferença Percentual",
                f"{percentual:+.1f}%",
                help="Variação percentual entre os cenários",
            )

        # Gráfico principal
        st.subheader("Comparação do VPL Acumulado")

        fig = px.line(
            df_filtrado,
            x="Data",
            y="VPL_Acumulado",
            color="Cenario",
            title=f"Evolução do VPL - {servidor_selecionado} ({anos} anos)",
            labels={
                "VPL_Acumulado": "VPL Acumulado (R$)",
                "Data": "Data",
                "Cenario": "Cenário",
            },
        )

        # Customizar o gráfico
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
        st.subheader("Resumo da Análise")

        if diferenca > 0:
            st.success(
                f"🎉 **Vantagem do Cenário**: R$ {diferenca:,.0f} (+{percentual:.1f}%)"
            )
            st.write(
                f"Com o cenário configurado ({cenario_personalizado} anos), **{servidor_selecionado}** teria **R$ {diferenca:,.0f} a mais** em VPL comparado ao status quo."
            )
        elif diferenca < 0:
            st.error(
                f"📉 **Desvantagem do Cenário **: R$ {abs(diferenca):,.0f} ({percentual:.1f}%)"
            )
            st.write(
                f"O status quo seria **R$ {abs(diferenca):,.0f} melhor** que o cenário configurado para **{servidor_selecionado}**."
            )
        else:
            st.info("⚖️ **Cenários Equivalentes**: Ambos resultam no mesmo VPL final.")

        # Mostrar dataframes que servem de base para o gráfico
        st.subheader("Dados")

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
