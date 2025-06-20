from peritos import carregar_servidores
from fluxo import criar_fluxo_caixa

if __name__ == "__main__":
    servidores = carregar_servidores("peritos.xlsx")
    lucas = servidores[servidores['Nome'] == 'Giorgia Freitas Alves']
    print(lucas)

    # status_quo = criar_fluxo_caixa(servidores, estrategia="status_quo")
    # cenario_a, vpl_a = criar_fluxo_caixa(servidores, estrategia="cenario", cenario=[5, 10, 15])
    # cenario_b, vpl_b = criar_fluxo_caixa(servidores, estrategia="cenario", cenario=[4, 8, 15])
    # cenario_c, vpl_c = criar_fluxo_caixa(servidores, estrategia="cenario", cenario=[3, 6, 15])
