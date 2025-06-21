import pandas as pd
import numpy as np
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union, Tuple

# Constantes do sistema
SALARIOS = {1: 27737.24, 2: 31699.35, 3: 35661.47, 4: 39623.58}
TAXA = 0.06
CENARIO_A = [5, 10, 15]  # 5-5-5
CENARIO_B = [4, 8, 15]  # 4-4-7

VAGAS_POR_TIPO = {
    "criminal": {1: 100, 2: 80, 3: 115, 4: 50},
    "bioquimico": {1: 13, 2: 11, 3: 15, 4: 6},
    "legista": {1: 55, 2: 45, 3: 60, 4: 25},
    "odonto": {1: 3, 2: 2, 3: 3, 4: 2},
}

MESES_PROMOCAO = [5, 11]  # Maio e Novembro
ANOS_APOSENTADORIA = 30  # Anos de trabalho para aposentadoria


class ProcessadorDados:
    """Classe utilitária para processamento de dados comuns"""

    @staticmethod
    def calcular_valor_acumulado(df_fluxo: pd.DataFrame) -> pd.DataFrame:
        """Calcula o valor acumulado para cada servidor ao longo do tempo"""
        df_fluxo = df_fluxo.sort_values(["Matricula", "Data"])
        df_fluxo["ValorAcumulado"] = df_fluxo.groupby("Matricula")[
            "Rendimento"
        ].cumsum()
        return df_fluxo

    @staticmethod
    def calcular_vpl(
        df_fluxo: pd.DataFrame, data_inicial: datetime = None, taxa: float = TAXA
    ) -> pd.DataFrame:
        """
        Calcula o VPL para cada servidor e adiciona colunas de VPL ao DataFrame

        Args:
            df_fluxo: DataFrame com fluxo de caixa
            data_inicial: Data inicial para cálculo do VPL (padrão: primeira data do fluxo)

        Returns:
            DataFrame com colunas adicionais de VPL
        """
        if data_inicial is None:
            data_inicial = df_fluxo["Data"].min()

        # Calcular número de meses desde a data inicial
        df_fluxo["MesesDesdeInicio"] = df_fluxo["Data"].apply(
            lambda x: (x.year - data_inicial.year) * 12 + (x.month - data_inicial.month)
        )

        # Calcular fator de desconto mensal
        taxa_mensal = taxa / 12
        df_fluxo["FatorDesconto"] = (
            1 / (1 + taxa_mensal) ** df_fluxo["MesesDesdeInicio"]
        )

        # Calcular valor presente de cada fluxo
        df_fluxo["ValorPresente"] = df_fluxo["Rendimento"] * df_fluxo["FatorDesconto"]

        # Calcular VPL acumulado por servidor
        df_fluxo = df_fluxo.sort_values(["Matricula", "Data"])
        df_fluxo["VPL_Acumulado"] = df_fluxo.groupby("Matricula")[
            "ValorPresente"
        ].cumsum()

        return df_fluxo

    @staticmethod
    def criar_resumo_vpl(df_fluxo: pd.DataFrame) -> pd.DataFrame:
        """
        Cria DataFrame resumo com VPL total por servidor (otimizado para gráficos)

        Returns:
            DataFrame com uma linha por servidor contendo VPL total e informações básicas
        """
        # Agrupar por servidor e pegar informações do último registro (mais completo)
        resumo = (
            df_fluxo.groupby("Matricula")
            .agg(
                {
                    "Nome": "first",
                    "CargoOriginal": "first",
                    "CargoAtual": "last",  # Cargo final após todas as promoções
                    "TipoPerito": "first",
                    "VPL_Acumulado": "last",  # VPL total (último valor acumulado)
                    "ValorAcumulado": "last",  # Valor nominal total
                    "ValorPresente": "sum",  # Soma de todos os valores presentes (mesmo que VPL_Acumulado)
                    "MesPromocao": lambda x: x.dropna().nunique(),  # Número de promoções
                    "DataAposentadoria": "first",  # Data de aposentadoria
                }
            )
            .reset_index()
        )

        # Renomear colunas para clareza
        resumo = resumo.rename(
            columns={
                "VPL_Acumulado": "VPL_Total",
                "ValorAcumulado": "ValorNominal_Total",
                "ValorPresente": "VPL_Total_Check",  # Para verificação
                "MesPromocao": "NumeroPromocoes",
            }
        )

        # Calcular diferença entre valor nominal e VPL (impacto do desconto)
        resumo["DiferencaNominal_VPL"] = (
            resumo["ValorNominal_Total"] - resumo["VPL_Total"]
        )
        resumo["PercentualDesconto"] = (
            resumo["DiferencaNominal_VPL"] / resumo["ValorNominal_Total"]
        ) * 100

        # Remover coluna de verificação
        resumo = resumo.drop("VPL_Total_Check", axis=1)

        return resumo

    @staticmethod
    def preparar_servidores(df_servidores: pd.DataFrame) -> pd.DataFrame:
        """Prepara DataFrame de servidores com colunas necessárias"""
        servidores = df_servidores.copy()

        # Inicializar colunas de controle
        servidores["CargoAtual"] = servidores["Cargo"]
        servidores["MesPromocao"] = None
        servidores["Aposentado"] = False
        servidores["DataAposentadoria"] = None

        return servidores


class FluxoCaixaStrategy(ABC):
    """Interface para estratégias de criação de fluxo de caixa"""

    def __init__(self):
        self.processador = ProcessadorDados()

    @abstractmethod
    def criar_fluxo(
        self,
        df_servidores: pd.DataFrame,
        anos: int = 35,
        cenario: List[int] = None,
        taxa: float = TAXA,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Método abstrato para criar fluxo de caixa"""
        pass

    def _gerar_dados_fluxo_mensal(
        self, servidores_atual: pd.DataFrame, data: datetime
    ) -> List[Dict]:
        """Gera dados de fluxo de caixa para um mês específico"""
        dados_fluxo = []

        # Filtrar apenas servidores ativos (não aposentados)
        servidores_ativos = servidores_atual[~servidores_atual["Aposentado"]]

        for _, servidor in servidores_ativos.iterrows():
            rendimento_base = SALARIOS.get(servidor["CargoAtual"])

            dados_fluxo.append(
                {
                    "Matricula": servidor["Matrícula"],
                    "Nome": servidor["Nome"],
                    "CargoOriginal": servidor["Cargo"],
                    "CargoAtual": servidor["CargoAtual"],
                    "Data": data,
                    "Ano": data.year,
                    "Mes": data.month,
                    "Rendimento": rendimento_base,
                    "TipoPerito": servidor.get("TipoPerito", "criminal"),
                    "DataPromocaoOriginal": servidor.get("Promoção", None),
                    "MesPromocao": servidor.get("MesPromocao", None),
                    "DataAposentadoria": servidor.get("DataAposentadoria", None),
                }
            )

        return dados_fluxo


class FluxoCaixaStatusQuoStrategy(FluxoCaixaStrategy):
    """Estratégia Status Quo com sistema de promoções padrão baseado em vagas e aposentadoria"""

    def criar_fluxo(
        self,
        df_servidores: pd.DataFrame,
        anos: int = 35,
        cenario: List[int] = None,
        taxa: float = TAXA,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        inicio = datetime(2025, 7, 1)
        datas = pd.date_range(inicio, periods=anos * 12, freq="ME")
        dados_fluxo = []

        # Preparar servidores
        servidores_atual = self.processador.preparar_servidores(df_servidores)

        # Processar datas de promoção
        if "Promoção" in servidores_atual.columns:
            # Ajustar elegibilidade para cargo 1 (adicionar 3 anos)
            mask_cargo1 = servidores_atual["Cargo"] == 1
            servidores_atual.loc[mask_cargo1, "Promoção"] = servidores_atual.loc[
                mask_cargo1, "Promoção"
            ] + pd.DateOffset(years=3)

        # Processar cada mês
        for data in datas:
            # Processar aposentadorias primeiro (para liberar vagas)
            servidores_atual = self._processar_aposentadorias(servidores_atual, data)
            
            # Verificar se é mês de promoção
            if data.month in MESES_PROMOCAO:
                servidores_atual = self._processar_promocoes_por_vagas(
                    servidores_atual, data
                )

            # Gerar fluxo de caixa mensal
            dados_fluxo.extend(self._gerar_dados_fluxo_mensal(servidores_atual, data))

        # Criar e processar DataFrame final
        df_fluxo = pd.DataFrame(dados_fluxo)
        df_fluxo = self.processador.calcular_valor_acumulado(df_fluxo)

        # Calcular VPL
        df_fluxo = self.processador.calcular_vpl(df_fluxo, inicio, taxa)

        # Criar resumo VPL
        resumo_vpl = self.processador.criar_resumo_vpl(df_fluxo)

        return df_fluxo, resumo_vpl

    def _processar_aposentadorias(
        self, df_servidores: pd.DataFrame, data_atual: datetime
    ) -> pd.DataFrame:
        """Processa aposentadorias baseadas em 30 anos de trabalho"""
        df_resultado = df_servidores.copy()
        
        # Verificar se existe a coluna AnoBase
        if "AnoBase" not in df_resultado.columns:
            # Se não existir, usar DataBase se disponível
            if "DataBase" in df_resultado.columns:
                df_resultado["AnoBase"] = pd.to_datetime(df_resultado["DataBase"]).dt.year
            else:
                return df_resultado
        
        # Para cada servidor não aposentado
        mask_ativos = ~df_resultado["Aposentado"]
        
        for idx, servidor in df_resultado[mask_ativos].iterrows():
            # Calcular anos de trabalho
            if pd.notna(servidor.get("AnoBase")):
                anos_trabalho = data_atual.year - servidor["AnoBase"]
                
                # Verificar se completou 30 anos
                if anos_trabalho >= ANOS_APOSENTADORIA:
                    df_resultado.at[idx, "Aposentado"] = True
                    df_resultado.at[idx, "DataAposentadoria"] = data_atual
        
        return df_resultado

    def _processar_promocoes_por_vagas(
        self, df_servidores: pd.DataFrame, data_atual: datetime
    ) -> pd.DataFrame:
        """Processa promoções baseadas em vagas disponíveis por tipo de perito"""
        df_resultado = df_servidores.copy()

        # Criar conjunto para rastrear quem já foi promovido neste mês
        promovidos_neste_mes = set()

        # Processar cada tipo de perito
        for tipo_perito, vagas_tipo in VAGAS_POR_TIPO.items():
            df_resultado = self._promover_tipo_perito(
                df_resultado, tipo_perito, vagas_tipo, data_atual, promovidos_neste_mes
            )

        return df_resultado

    def _promover_tipo_perito(
        self,
        df_servidores: pd.DataFrame,
        tipo_perito: str,
        vagas_tipo: Dict[int, int],
        data_atual: datetime,
        promovidos_neste_mes: set,
    ) -> pd.DataFrame:

        # IMPORTANTE: Processar promoções do cargo 1 ao 3 (não 4)
        # para garantir promoções apenas para o nível imediatamente superior
        for cargo_origem in [1, 2, 3]:
            cargo_destino = cargo_origem + 1

            # Recalcular ocupação atual a cada iteração para refletir mudanças
            # Considerar apenas servidores ATIVOS
            servidores_tipo_ativos = df_servidores[
                (df_servidores.get("TipoPerito", "criminal") == tipo_perito) &
                (~df_servidores["Aposentado"])
            ]

            if len(servidores_tipo_ativos) == 0:
                continue

            # Calcular ocupação atual por cargo (apenas ativos)
            ocupacao_atual = servidores_tipo_ativos["CargoAtual"].value_counts().to_dict()
            for cargo in vagas_tipo.keys():
                ocupacao_atual.setdefault(cargo, 0)

            # Calcular vagas disponíveis
            vagas_disponiveis = (
                vagas_tipo[cargo_destino] - ocupacao_atual[cargo_destino]
            )

            if vagas_disponiveis > 0:
                # Executar promoções e atualizar o DataFrame
                df_servidores, num_promovidos = self._executar_promocoes(
                    df_servidores,
                    tipo_perito,
                    cargo_origem,
                    cargo_destino,
                    vagas_disponiveis,
                    data_atual,
                    promovidos_neste_mes,
                )

        return df_servidores

    def _executar_promocoes(
        self,
        df_servidores: pd.DataFrame,
        tipo_perito: str,
        cargo_origem: int,
        cargo_destino: int,
        vagas_disponiveis: int,
        data_atual: datetime,
        promovidos_neste_mes: set,
    ) -> Tuple[pd.DataFrame, int]:
        """Executa as promoções efetivas e retorna o DataFrame atualizado e número de promoções"""
        # Selecionar candidatos elegíveis que NÃO foram promovidos neste mês e estão ATIVOS
        df_servidores["Promoção"] = pd.to_datetime(
            df_servidores["Promoção"], errors="coerce"
        )
        candidatos = df_servidores[
            (df_servidores["CargoAtual"] == cargo_origem)
            & (df_servidores["Promoção"] <= data_atual)
            & (df_servidores.get("TipoPerito", "criminal") == tipo_perito)
            & (~df_servidores["Matrícula"].isin(promovidos_neste_mes))
            & (~df_servidores["Aposentado"])  # Apenas servidores ativos
        ]

        num_promocoes = min(len(candidatos), vagas_disponiveis)

        if num_promocoes > 0:
            # Ordenar candidatos por critério (data de promoção, depois matrícula)
            candidatos_ordenados = candidatos.sort_values(["Promoção", "Matrícula"])
            indices_promovidos = candidatos_ordenados.head(num_promocoes).index

            # Executar promoções
            df_servidores.loc[indices_promovidos, "CargoAtual"] = cargo_destino
            df_servidores.loc[indices_promovidos, "MesPromocao"] = data_atual

            # Adicionar promovidos ao conjunto para evitar múltiplas promoções no mesmo mês
            for idx in indices_promovidos:
                promovidos_neste_mes.add(df_servidores.loc[idx, "Matrícula"])

        return df_servidores, num_promocoes


class FluxoCaixaCenarioStrategy(FluxoCaixaStrategy):
    """Estratégia baseada em tempo de serviço sem limite de vagas"""

    def criar_fluxo(
        self,
        df_servidores: pd.DataFrame,
        anos: int = 35,
        cenario: List[int] = None,
        taxa: float = TAXA,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        if cenario is None:
            cenario = CENARIO_A

        inicio = datetime(2025, 7, 1)
        datas = pd.date_range(inicio, periods=anos * 12, freq="ME")
        dados_fluxo = []

        # Preparar servidores
        servidores_atual = self.processador.preparar_servidores(df_servidores)

        # Processar cada mês
        for data in datas:
            # Processar aposentadorias primeiro (para ser consistente com Status Quo)
            servidores_atual = self._processar_aposentadorias(servidores_atual, data)
            
            # Processar promoções por tempo
            servidores_atual = self._processar_promocoes_por_tempo(
                servidores_atual, data, cenario
            )
            
            # Gerar fluxo de caixa mensal
            dados_fluxo.extend(self._gerar_dados_fluxo_mensal(servidores_atual, data))

        # Criar e processar DataFrame final
        df_fluxo = pd.DataFrame(dados_fluxo)
        df_fluxo = self.processador.calcular_valor_acumulado(df_fluxo)

        # Calcular VPL
        df_fluxo = self.processador.calcular_vpl(df_fluxo, inicio, taxa)

        # Criar resumo VPL
        resumo_vpl = self.processador.criar_resumo_vpl(df_fluxo)

        return df_fluxo, resumo_vpl

    def _processar_aposentadorias(
        self, df_servidores: pd.DataFrame, data_atual: datetime
    ) -> pd.DataFrame:
        """Processa aposentadorias baseadas em 30 anos de trabalho (mesmo critério do Status Quo)"""
        df_resultado = df_servidores.copy()
        
        # Verificar se existe a coluna AnoBase
        if "AnoBase" not in df_resultado.columns:
            # Se não existir, usar DataBase se disponível
            if "DataBase" in df_resultado.columns:
                df_resultado["AnoBase"] = pd.to_datetime(df_resultado["DataBase"]).dt.year
            else:
                return df_resultado
        
        # Para cada servidor não aposentado
        mask_ativos = ~df_resultado["Aposentado"]
        
        for idx, servidor in df_resultado[mask_ativos].iterrows():
            # Calcular anos de trabalho
            if pd.notna(servidor.get("AnoBase")):
                anos_trabalho = data_atual.year - servidor["AnoBase"]
                
                # Verificar se completou 30 anos
                if anos_trabalho >= ANOS_APOSENTADORIA:
                    df_resultado.at[idx, "Aposentado"] = True
                    df_resultado.at[idx, "DataAposentadoria"] = data_atual
        
        return df_resultado

    def _processar_promocoes_por_tempo(
        self, df_servidores: pd.DataFrame, data_atual: datetime, cenario: List[int]
    ) -> pd.DataFrame:
        """Processa promoções baseadas em tempo de serviço (apenas para servidores ativos)"""

        if data_atual < datetime(2026, 8, 1):
            return df_servidores

        df_resultado = df_servidores.copy()

        # Processar apenas servidores ATIVOS (não aposentados)
        mask_ativos = ~df_resultado["Aposentado"]

        for idx, servidor in df_resultado[mask_ativos].iterrows():
            if pd.isna(servidor.get("DataBase")):
                continue

            # Verificar se é aniversário da data base
            if (
                not self._eh_aniversario_data_base(data_atual, servidor["DataBase"])
                and not servidor.get("promove_novembro", False)
            ):
                continue

            # Calcular anos de serviço e cargo esperado
            anos_servico = (data_atual - servidor["DataBase"]).days / 365.25
            cargo_esperado = self._determinar_cargo_por_tempo(
                anos_servico,
                cenario,
                servidor.get("promove_novembro", False),
                data_atual,
                servidor["CargoAtual"],
            )

            # Promover se necessário
            if cargo_esperado > servidor["CargoAtual"]:
                df_resultado.at[idx, "CargoAtual"] = cargo_esperado
                df_resultado.at[idx, "MesPromocao"] = data_atual

        return df_resultado

    def _eh_aniversario_data_base(
        self, data_atual: datetime, data_base: datetime
    ) -> bool:
        """Verifica se a data atual é aniversário da data base"""
        return data_atual.month == data_base.month and data_atual.year > data_base.year

    def _determinar_cargo_por_tempo(
        self,
        anos_servico: float,
        cenario: List[int],
        promove_novembro,
        data_atual,
        cargo_atual,
    ) -> int:
        """Determina o cargo baseado nos anos de serviço"""

        if anos_servico < cenario[0] and promove_novembro:
            return 2
        elif anos_servico < cenario[0]:
            return 1
        elif anos_servico < cenario[1]:
            return 2
        elif anos_servico < cenario[2]:
            return 3
        else:
            return 4


class FluxoCaixaContext:
    """Context que utiliza as estratégias de fluxo de caixa"""

    def __init__(self, strategy: FluxoCaixaStrategy):
        self._strategy = strategy

    def set_strategy(self, strategy: FluxoCaixaStrategy) -> None:
        """Permite trocar a estratégia em tempo de execução"""
        self._strategy = strategy

    def criar_fluxo_caixa(
        self,
        df_servidores: pd.DataFrame,
        anos: int = 35,
        cenario: List[int] = None,
        taxa: float = TAXA,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Delega a criação do fluxo de caixa para a estratégia atual"""
        return self._strategy.criar_fluxo(df_servidores, anos, cenario, taxa)


def criar_fluxo_caixa(
    df_servidores: pd.DataFrame,
    anos: int = 35,
    estrategia: str = "status_quo",
    cenario: List[int] = None,
    taxa: float = TAXA,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Função de conveniência que mantém a interface original

    Args:
        df_servidores: DataFrame com dados dos servidores
        anos: Número de anos para projeção (padrão: 35)
        estrategia: Tipo de estratégia ("status_quo", "cenario")
        cenario: Lista com anos para promoção por tempo de serviço

    Returns:
        Tuple contendo:
        - DataFrame detalhado com fluxo de caixa e VPL mensal
        - DataFrame resumo com VPL total por servidor (otimizado para gráficos)
    """
    estrategias = {
        "status_quo": FluxoCaixaStatusQuoStrategy(),
        "cenario": FluxoCaixaCenarioStrategy(),
    }

    if estrategia not in estrategias:
        raise ValueError(
            f"Estratégia '{estrategia}' não encontrada. Opções: {list(estrategias.keys())}"
        )

    context = FluxoCaixaContext(estrategias[estrategia])
    return context.criar_fluxo_caixa(df_servidores, anos, cenario, taxa)


def criar_resumo_comparativo(resumos_vpl: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Cria um DataFrame comparativo entre diferentes cenários (útil para gráficos)

    Args:
        resumos_vpl: Dicionário com nome do cenário como chave e DataFrame resumo como valor

    Returns:
        DataFrame com comparação de VPL entre cenários
    """
    comparativo = []

    for nome_cenario, resumo in resumos_vpl.items():
        resumo_cenario = resumo.copy()
        resumo_cenario["Cenario"] = nome_cenario
        comparativo.append(resumo_cenario)

    df_comparativo = pd.concat(comparativo, ignore_index=True)

    # Calcular estatísticas por cenário
    stats_cenario = (
        df_comparativo.groupby("Cenario")
        .agg(
            {
                "VPL_Total": ["mean", "median", "sum", "std"],
                "ValorNominal_Total": ["mean", "median", "sum"],
                "NumeroPromocoes": "mean",
                "PercentualDesconto": "mean",
            }
        )
        .round(2)
    )

    # Achatar os nomes das colunas
    stats_cenario.columns = ["_".join(col).strip() for col in stats_cenario.columns]
    stats_cenario = stats_cenario.reset_index()

    return df_comparativo, stats_cenario


def criar_analise_aposentadorias(df_fluxo: pd.DataFrame) -> pd.DataFrame:
    """
    Cria análise das aposentadorias ao longo do tempo
    
    Args:
        df_fluxo: DataFrame com fluxo de caixa detalhado
        
    Returns:
        DataFrame com estatísticas de aposentadorias por ano
    """
    # Filtrar apenas registros com data de aposentadoria
    aposentados = df_fluxo[df_fluxo["DataAposentadoria"].notna()].copy()
    
    if len(aposentados) == 0:
        return pd.DataFrame()
    
    # Pegar primeira ocorrência de cada aposentado
    aposentados = aposentados.groupby("Matricula").first().reset_index()
    
    # Extrair ano de aposentadoria
    aposentados["AnoAposentadoria"] = pd.to_datetime(aposentados["DataAposentadoria"]).dt.year
    
    # Criar análise por ano e tipo de perito
    analise = (
        aposentados.groupby(["AnoAposentadoria", "TipoPerito", "CargoAtual"])
        .size()
        .reset_index(name="NumeroAposentadorias")
    )
    
    # Adicionar totais por ano
    totais_ano = (
        aposentados.groupby("AnoAposentadoria")
        .size()
        .reset_index(name="TotalAposentadorias")
    )
    
    return analise, totais_ano
