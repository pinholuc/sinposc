import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta


def carregar_servidores(arquivo):
    """
    Limpa os dados dos servidores aplicando as seguintes regras:
    - Remove linhas onde a primeira coluna é NaN
    - Remove linhas onde a primeira coluna não é um número
    - Remove linhas onde a primeira coluna é igual a 355
    - Limpa a coluna 'Cargo' removendo 'Perito Criminal - Nível '

    Args:
        arquivo (str): Caminho para o arquivo Excel
        sheet_name (str): Nome da planilha (padrão: 'PC expectativa')

    Returns:
        pd.DataFrame: DataFrame limpo
    """

    def romano_para_numero(romano):
        valores = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}
        return valores.get(romano, romano)

    # Ler o arquivo
    a = pd.read_excel(arquivo, sheet_name="PeritoCriminalBioquímico")
    b = pd.read_excel(arquivo, sheet_name="PeritoCriminal")
    c = pd.read_excel(arquivo, sheet_name="PeritoMédicoLegista")
    d = pd.read_excel(arquivo, sheet_name="PeritoOdontolegista")

    a["TipoPerito"] = "bioquimico"
    b["TipoPerito"] = "criminal"
    c["TipoPerito"] = "legista"
    d["TipoPerito"] = "odonto"

    servidores = pd.concat([a, b, c, d], ignore_index=True)

    # Obter primeira coluna
    primeira_coluna = servidores.columns[0]

    # Aplicar filtros de limpeza
    servidores = servidores[
        servidores[primeira_coluna].notna()
        & pd.to_numeric(servidores[primeira_coluna], errors="coerce").notna()
        & (pd.to_numeric(servidores[primeira_coluna], errors="coerce") != 355)
        & (servidores[primeira_coluna] != "Pos.Geral")
        & (~servidores["Nome"].str.startswith("Dalton Lucio", na=False))
    ].reset_index(drop=True)

    # Limpar coluna Cargo
    servidores["Cargo"] = servidores["Cargo"].str.replace(
        "Perito Criminal – Nível ", "", regex=False
    )
    servidores["Cargo"] = servidores["Cargo"].str.replace(
        "Perito Criminal Bioquímico – Nível ", "", regex=False
    )
    servidores["Cargo"] = servidores["Cargo"].str.replace(
        "Perito Médico-Legista – Nível ", "", regex=False
    )
    servidores["Cargo"] = servidores["Cargo"].str.replace(
        "Perito Odontolegista – Nível ", "", regex=False
    )
    servidores["Cargo"] = servidores["Cargo"].map(romano_para_numero)
    servidores = servidores.drop("Publicação", axis=1)

    datas_convertidas = []

    mapeamento_datas = {
        "nov/2016?": datetime(2016, 11, 1),
        "nov/2018?": datetime(2018, 11, 1),
        "nov/2017?": datetime(2017, 11, 1),
        "nov/2016?": datetime(2016, 11, 1),
        "nov/2015?": datetime(2015, 11, 1),
        "nov/2018": datetime(2018, 11, 1),
        "nov/2017": datetime(2017, 11, 1),
        "mai/2016": datetime(2016, 5, 1),
        "maio/2016": datetime(2016, 5, 1),
        "nov/2016": datetime(2016, 11, 1),
        "nov/2015": datetime(2015, 11, 1),
        "maio/2015": datetime(2015, 5, 1),
        "mai/2015": datetime(2015, 5, 1),
        "nov/2014": datetime(2014, 11, 1),
        "maio/2014": datetime(2014, 5, 1),
        "mai/2014": datetime(2014, 5, 1),
        "?": datetime(2015, 5, 1)
    }

    for data in servidores["Promoção"]:
        try:

            # Verificar se é nulo ou vazio
            if pd.isna(data) or data == "" or data is None:
                datas_convertidas.append(pd.NaT)  # Usar NaT em vez de data fictícia
                continue

            # Se já é datetime, manter
            if isinstance(data, (pd.Timestamp, datetime)):
                datas_convertidas.append(pd.to_datetime(data))
                continue

            # Se é string, processar
            if isinstance(data, str):
                if data.strip() == "?":
                    datas_convertidas.append(datetime(2015, 5, 1))
                    continue
                data_limpa = data.strip().replace("?", "").replace("*", "").lower()

                # Se string vazia após limpeza
                if not data_limpa:
                    datas_convertidas.append(pd.NaT)
                    continue

                # Verificar mapeamento direto para formatos especiais
                data_encontrada = None
                for padrao, data_convertida in mapeamento_datas.items():
                    if padrao.lower() in data_limpa:
                        data_encontrada = data_convertida
                        break

                if data_encontrada:
                    datas_convertidas.append(data_encontrada)
                else:
                    # Tentar conversão automática com diferentes formatos
                    formatos_comuns = [
                        "%Y-%m-%d %H:%M:%S",  # 2019-11-13 00:00:00
                        "%Y-%m-%d",  # 2019-11-13
                        "%d/%m/%Y",  # 13/11/2019
                        "%d-%m-%Y",  # 13-11-2019
                        "%m/%d/%Y",  # 11/13/2019
                        "%Y/%m/%d",  # 2019/11/13
                    ]

                    data_convertida = None

                    # Primeiro, tentar pd.to_datetime (mais flexível)
                    try:
                        data_convertida = pd.to_datetime(data.strip(), errors="raise")
                        datas_convertidas.append(data_convertida)
                        continue
                    except:
                        pass

                    # Se falhou, tentar formatos específicos
                    for formato in formatos_comuns:
                        try:
                            data_convertida = datetime.strptime(data.strip(), formato)
                            datas_convertidas.append(pd.to_datetime(data_convertida))
                            break
                        except:
                            continue

                    # Se nenhum formato funcionou
                    if data_convertida is None:
                        print(
                            f"Aviso: Não foi possível converter '{data}'. Usando NaT."
                        )
                        datas_convertidas.append(pd.NaT)
            else:
                # Para outros tipos, tentar conversão direta
                datas_convertidas.append(pd.to_datetime(data))

        except Exception as e:
            print(f"Erro ao converter data '{data}': {e}. Usando NaT.")
            datas_convertidas.append(pd.NaT)

    servidores["Promoção"] = datas_convertidas
    faltando_data = servidores[pd.isna(servidores["Promoção"])]
    print("Servidores excluídos por Promoção NaT:")
    print(faltando_data[["Nome", "Promoção"]])
    servidores = servidores[servidores["Promoção"].notna()].reset_index(drop=True)
    servidores["promove_novembro"] = (
        servidores["Pos.Geral"].between(150, 177).astype(int)
    )
    # First, ensure all date columns are datetime objects
    date_columns = [
        "DataBase",
        "Data_Admissao",
        "Promoção",
    ]  # Add all relevant date columns

    for col in date_columns:
        if col in servidores.columns:
            # Convert to datetime, handling errors gracefully
            servidores[col] = pd.to_datetime(servidores[col], errors="coerce")

    mask = servidores["Cargo"] != 1
    servidores.loc[mask, "DataBase"] = servidores.loc[mask, "Promoção"] - pd.DateOffset(
        years=4
    )
    servidores.loc[~mask, "DataBase"] = servidores.loc[~mask, "Promoção"]  # or pd.NaT

    print(
        f"Total de servidores após remover linhas com Promoção nula: {len(servidores)}"
    )


    return servidores


if __name__ == "__main__":
    servidores = carregar_servidores("peritos.xlsx")
