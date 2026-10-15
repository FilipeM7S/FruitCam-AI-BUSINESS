from datetime import date, datetime

AI_ERRORS = "A inteligência Artificial pode cometer erros."

DECLARATIONS = {
    "honesty": "Protótipo. Linhas e painéis de demonstração usam dados sintéticos e simulação; números de qualidade do modelo aparecem só onde foram medidos, com o conjunto indicado. O desempenho em esteira real ainda não foi avaliado.",
    "confidence": "Confiança é a probabilidade atribuída pelo modelo, não uma acurácia verificada.",
    "limits": "Limite principal: as fotos de treino e de teste são de frutos no pé, não em esteira. O acerto medido (89% de acurácia balanceada) vale para fotos parecidas com essas; com a fruta colada sobre quadros de vídeos reais de linhas de seleção ele cai para 78%, e em esteira real de caju ainda não foi medido. Por isso o sistema conta e mede cada fruta, mas manda para conferência toda fruta classificada pelo modelo. Para ligar a decisão automática é preciso gravar bandejas separadas à mão na sua esteira e medir de novo (veja docs/data/collection.md). “Baixa qualidade” no treino corresponde a frutos imaturos ou ainda verdes. Há poucos exemplos de fruta estragada (662 no treino), e de cada 100 alarmes de “podre” no teste cerca de 45 estavam certos.",
    "dataIssue": "De onde vêm os dados: fotos de cajueiros tiradas de perto por drone em Gana e em Uganda, com cada fruto marcado como imaturo, verde, maduro ou estragado. Os rótulos de Uganda usam duas ordens de classe. A ordem do segundo lote (1.440 fotos) foi confirmada pelas contagens publicadas do lote de Gana, que usa a mesma ordem; essas fotos voltaram para o treino. O primeiro lote (1.589 fotos) ficou de fora: nele o modelo novo responde “baixa qualidade” para quase todo fruto, qualquer que seja o rótulo. Isso pode vir de outro critério de anotação ou de fotos diferentes das demais; ainda não sabemos qual. O modelo atual (belt_v3) foi treinado com 14.033 recortes, metade das vezes com a fruta recortada e colada sobre esteiras sintéticas ou sobre quadros de vídeos reais de linhas de seleção. Nos mesmos recortes de teste, o modelo anterior (belt_v2) teve acurácia balanceada de 56% e o atual, 89%. Um número antigo de 80,9% vinha de uma ordem de classes lida errado: não vale.",
    "verified": [
        "Contagem na esteira simulada: com frutas desenhadas, cada fruta é contada uma única vez, com tamanho medido dentro de poucos por cento (testes automatizados com resposta conhecida). Com recortes de frutas reais, 891 contagens para 891 frutas.",
        "Carta de controle e aceite de lote contra dados sintéticos com uma piora conhecida.",
        "Que a inspeção por foto devolve exatamente a saída do classificador.",
        "Acurácia do modelo em um teste separado por foto, com as limitações descritas acima.",
        "Ordem das classes nos rótulos conferida: o lote de Gana só bate com as contagens publicadas numa ordem, e o segundo lote de Uganda usa a mesma (teste automatizado).",
        "A receita de treino numa esteira industrial real de batatas (dados abertos da Universidade de Pardubice, validação cruzada): 90,6% de acerto, mas só 52,7% das batatas danificadas reconhecidas.",
    ],
    "notVerified": [
        "O desempenho em esteira real, com a câmera, a luz e as frutas da linha.",
        "Qualquer estatística com dados reais de produção: só existem dados sintéticos e simulação.",
        "Classificação de castanha e de melão.",
        "Defeitos além de imaturo e podre.",
        "A separação da fruta pela cor numa esteira real de caju.",
    ],
    "pending": [
        {"title": "Teste em esteira real", "text": "Falta uma amostra rotulada filmada pela câmera instalada na linha, com a luz e as frutas reais."},
        {"title": "Rótulos dos dados públicos", "text": "O primeiro lote de rótulos de Uganda (1.589 fotos) não bate com os outros lotes (critério de anotação ou tipo de foto diferente; não sabemos qual). Ficou fora do treino e do teste até os autores do conjunto confirmarem o que cada classe significa nele."},
        {"title": "Separação por cor em esteira real", "text": "Numa esteira real de batatas, a separação por cor falhou. O caju contrasta muito mais com uma esteira cinza, mas isso ainda não foi testado em esteira real de caju."},
        {"title": "Outros defeitos", "text": "Amassado, rachado e queimado não estão nos dados de treino; hoje só há imaturo e podre."},
        {"title": "Frutas encostadas", "text": "Frutas que só se encostam agora são separadas antes da contagem: num teste simulado com sobreposição de até 25 mm, o erro de contagem caiu de −4,8% para −1,9%. Frutas muito sobrepostas ainda viram uma só (−22% com sobreposição de até 40 mm). Existe uma opção que fecha por completo a linha de corte e leva esse erro a −3,5%, mas na simulação ela cortou frutas reais inteiras em duas (8 contagens duplicadas em 891); por isso fica desligada."},
        {"title": "Fruta da cor da esteira", "text": "Uma fruta podre com uma parte tão escura quanto a esteira vira duas manchas. O rastreador agora conta duas manchas coladas que cruzam a linha juntas como uma fruta só: na esteira simulada, as contagens duplicadas foram de 2 para 0 em 891 frutas reais. A regra não foi testada em esteira real; uma esteira de cor que contraste com a fruta continua sendo o remédio seguro."},
        {"title": "Castanha e melão", "text": "O modelo nunca viu essas frutas no treino; os resultados delas não têm validade."},
    ],
}

T = {
    "brand": "FruitCam_ai",
    "title": "Certificado de Análise Estatística",
    "subtitle": "Inspeção de frutas por visão computacional",
    "kicker": "CERTIFICADO",
    "keywords": "FruitCam_ai, certificado, estatística, inspeção, caju",
    "number": "Nº {n}",
    "attest": "O sistema FruitCam_ai certifica que este documento reúne todos os gráficos e resultados estatísticos calculados automaticamente a partir dos registros de inspeção armazenados, sem edição manual, no escopo abaixo e no momento da emissão. Os resultados do painel são os mesmos exibidos no Painel estatístico para os mesmos filtros; os da linha usam os cálculos da página Linha, aplicados ao período do escopo.",
    "ai_sub": "Leia as declarações da seção 2 antes de usar estes resultados em qualquer decisão.",
    "demo_cover": "Dados de demonstração: este certificado inclui dados sintéticos e não registra inspeções reais.",
    "watermark": "DADOS DE DEMONSTRAÇÃO",
    "watermark_sub": "sem valor como registro de inspeção",
    "issued_at": "Emitido em",
    "issued_by": "Emitido por",
    "fingerprint": "Impressão digital (SHA-256)",
    "electronic": "Documento emitido eletronicamente pelo sistema FruitCam_ai.",
    "seal": "FRUITCAM_AI · CERTIFICADO DIGITAL · ",
    "seal_center": "ANÁLISE ESTATÍSTICA",
    "header": "Certificado de Análise Estatística",
    "page": "Página {i} de {n}",
    "footer_hash": "Gerado automaticamente · impressão digital {h}",
    "toc": "Sumário",
    "none": "—",
    "na": "n/d",
    "yes": "sim",
    "no": "não",
    "and": " e ",
    "scope": {
        "source": "Origem dos dados",
        "sources": {"real": "Inspeções reais", "demo": "Demonstração (dados sintéticos)", "all": "Reais + demonstração"},
        "sector": "Setor",
        "all_sectors": "Todos os setores",
        "period": "Agregação do painel",
        "periods": {"week": "Semanal", "month": "Mensal"},
        "range": "Intervalo solicitado",
        "range_all": "Todo o histórico",
        "range_from": "A partir de {a}",
        "range_to": "Até {b}",
        "range_both": "{a} a {b}",
        "covered": "Registros do painel entre",
        "covered_v": "{a} e {b}",
        "n": "Frutas nas estatísticas do painel",
        "pending": "Aguardando revisão manual (fora do painel)",
        "cameras": "Câmeras no escopo",
        "cameras_v": "{n} de {total}",
        "line_n": "Frutas registradas pelas câmeras",
        "model": "Modelo do classificador",
        "versions": "Versões de modelo nos registros",
        "unrecorded": "não registrada",
        "tz": "Fuso horário",
    },
    "sections": {
        "scope": "Resumo executivo",
        "declarations": "Declarações",
        "overview": "Visão geral",
        "now": "Qualidade agora",
        "trends": "Tendências",
        "distributions": "Distribuições",
        "forecast": "Previsão por setor",
        "line": "Linha de inspeção (câmeras)",
        "model": "Qualidade medida do modelo",
        "method": "Metodologia e definições",
        "tech": "Ficha técnica",
        "human": "Conferência humana",
        "annex_a": "Anexo A: tabelas completas do painel",
        "annex_b": "Anexo B: janelas da linha de inspeção",
        "auth": "Autenticação do documento",
    },
    "scope_lead": "O essencial do certificado em uma página: os indicadores principais, os destaques encontrados nos dados e o escopo exato dos registros considerados.",
    "scope_table": "Escopo",
    "summary": "Resumo dos resultados",
    "summary_cols": ["Indicador", "Resultado", "Observação"],
    "sum": {
        "n": "Frutas analisadas (painel)",
        "good": "Boas",
        "rotten": "Podres (qualquer defeito)",
        "rate": "Taxa de podres",
        "rate_note": "IC 95% (Wilson): {lo} a {hi}",
        "sectors": "Setores",
        "worst": "Maior taxa de podres: {s} ({v})",
        "top_fruit": "Fruta mais recebida",
        "top_def": "Defeito mais frequente",
        "tie": "empate",
        "forecasts": "Previsões por setor",
        "forecasts_v": "{ok} de {n} com dados suficientes",
        "forecasts_note": "{r} passaram nos critérios mínimos (não é garantia de acerto)",
        "gauss": "Curva normal por setor",
        "gauss_v": "{f} de {n} sinalizados",
        "gauss_note": "Ajuste ruim ou amostra pequena: não trate como curva normal",
        "line": "Linha: frutas registradas",
        "alarms": "Linha: alarmes da carta de controle",
        "lots": "Linha: lotes",
        "lots_v": "aprovados: {a} · reprovados: {r} · inconclusivos: {i}",
        "no_dash": "Sem registros do painel no escopo",
    },
    "decl": {
        "lead": "Estas declarações fazem parte do certificado e valem para todos os resultados nas páginas seguintes.",
        "ai_title": "Sobre a inteligência artificial",
        "nature_title": "Natureza deste documento",
        "nature": "Este certificado documenta resultados estatísticos calculados automaticamente. Não é laudo de qualidade, não garante a qualidade de nenhuma fruta ou lote e não substitui a inspeção humana.",
        "review": "Frutas marcadas para revisão manual não entram nas estatísticas do painel. Neste escopo, {n} registros aguardavam revisão no momento da emissão.",
        "demo": "Este escopo inclui dados de demonstração (sintéticos ou simulados). Os números servem para demonstrar o sistema e não descrevem inspeções reais.",
        "status_title": "Situação do protótipo",
        "data_title": "Dados de treino do modelo",
        "limits_title": "Limite principal",
        "verified": "O que foi verificado",
        "not_verified": "O que ainda não foi validado",
        "pending": "Ainda não avaliado",
    },
    "how_read": "Como ler",
    "chart": "Gráfico",
    "table": "Tabela",
    "no_data": "Sem registros no escopo para este resultado.",
    "badges": {
        "small_latest": "Amostra pequena: a semana mais recente tem só {n} frutas podres.",
        "small_total": "Amostra pequena: só {n} frutas no escopo.",
        "few_periods": "Amostra pequena: só {n} períodos completos; variações podem ser ruído.",
        "partial": "Parciais fora: {n} frutas de períodos incompletos nas pontas ficaram fora do cálculo.",
        "one_type": "1 tipo de defeito: o modelo atual só distingue “podre”; outros tipos exigem retreinar o modelo.",
        "recurring_small": "Amostra pequena: cada barra vem de no máximo {n} período(s); ainda não é um padrão recorrente.",
        "demo": "Dados de demonstração.",
        "clipped": "Escala cortada em {m} para que os demais períodos fiquem legíveis; as barras maiores trazem o valor escrito, e os valores exatos estão nas tabelas.",
    },
    "overview": {
        "title": "Como está a inspeção no geral?",
        "lead": "Volume inspecionado, taxa de podres e comparação entre setores no escopo.",
        "volume": "Volume por período (boas e podres)",
        "rate": "Taxa de podres por período",
        "sectors": "Taxa de podres por setor",
        "how": ["Volume por período: verde = boas, laranja = podres.", "A linha mostra a % de podres em cada período; o tracejado é a média do escopo.", "O setor com a maior taxa de podres fica em destaque."],
        "kpi_cols": ["Indicador", "Valor"],
        "sector_cols": ["Setor", "Frutas", "Podres", "Taxa de podres", "IC 95% (Wilson)"],
        "avg": "média {v}",
    },
    "deformity": {
        "title": "Qual defeito domina cada semana?",
        "lead": "Cada barra soma 100% das frutas podres da semana, dividida por tipo de defeito.",
        "how": ["Cada cor é um tipo de defeito.", "Cada barra é uma semana; as cores somam 100% das frutas podres daquela semana.", "A linha abaixo do gráfico informa o defeito que dominou a semana mais recente."],
        "latest": "Semana de {w}: {t} domina com {s} das podres",
        "latest_tie": "Semana de {w}: empate entre defeitos",
        "cols": ["Tipo de defeito", "Frutas podres", "Participação", "Semanas em que dominou"],
    },
    "fruits": {
        "title": "Qual fruta chega em maior quantidade?",
        "lead": "Número de frutas recebidas por tipo no escopo.",
        "how": ["A barra destacada é a fruta que mais chegou.", "O comprimento da barra é o número de frutas."],
        "winner": "mais recebida",
        "tie": "empate",
        "cols": ["Fruta", "Frutas", "Participação"],
    },
    "growth": {
        "title": "As frutas boas e as podres estão aumentando?",
        "lead": "Barra = variação da contagem em relação ao período anterior; tracejado = variação da proporção. Os dois gráficos usam a mesma escala.",
        "how": ["A linha do zero significa “igual ao período anterior”.", "Barra azul para cima: cresceu; barra laranja para baixo: caiu.", "n/d: o período anterior era zero ou vazio; o crescimento é indefinido, não zero."],
        "good": "Frutas boas",
        "rotten": "Frutas podres",
        "up": "Alta",
        "down": "Queda",
        "prop": "Variação da proporção",
        "cols": ["Período", "Boas", "Var. boas", "Var. % boas", "Podres", "Var. podres", "Var. % podres"],
        "recent": "Últimos {n} períodos completos (tabela completa no Anexo A).",
        "insufficient": "É preciso pelo menos 2 períodos completos para calcular crescimento.",
    },
    "recurring": {
        "title": "Em que época do ano o crescimento se concentra?",
        "lead": "Mediana do crescimento da contagem por semana do ano, mês ou estação; o rótulo marca o pico de cada série.",
        "how": ["Cada grupo é uma semana do ano, um mês ou uma estação.", "Verde = boas, laranja = podres; o rótulo marca o pico.", "Cada barra é a mediana de vários períodos; com poucos períodos, ainda não é um padrão."],
        "views": {"week": "Semana do ano", "month": "Mês", "season": "Estação"},
        "peak": "pico",
        "cols": ["{view}", "Mediana boas", "n boas", "Mediana podres", "n podres"],
        "empty": "Não há períodos completos suficientes nesta escala.",
        "week_annex": "Tabela por semana do ano no Anexo A.",
    },
    "gaussian": {
        "title": "A % de podres de cada setor segue uma curva normal?",
        "lead": "Barras = períodos observados; curva = normal ajustada; faixas = ±1σ e ±2σ. Ao lado, o gráfico Q-Q.",
        "how": ["Cada barra conta quantos períodos tiveram aquela % de podres.", "A linha vertical marca a média; faixa escura = ±1σ e clara = ±2σ.", "No Q-Q, pontos sobre a reta indicam forma normal; curvas nas pontas indicam desvio."],
        "hist": "Períodos observados",
        "pdf": "Curva normal ajustada",
        "qq": "Gráfico Q-Q",
        "qq_line": "reta = normal perfeita",
        "mean": "média {v}",
        "impossible": "impossível",
        "poor": "AJUSTE RUIM",
        "poor_sub": "Shapiro p = {p}",
        "theoretical": "Quantil teórico",
        "observed": "Quantil observado",
        "density": "Densidade",
        "cols": ["Setor", "Períodos", "Média", "Desvio (σ)", "Shapiro W", "Shapiro p", "Massa fora de 0–100%", "Situação"],
        "ok": "sem sinal",
        "flagged": "sinalizado",
        "empty": "{s}: {n} períodos; o histograma precisa de pelo menos 3 com variação.",
        "reasons": {"small_n": "menos de {min} períodos", "no_variance": "sem variação", "not_normal": "teste rejeita normalidade (p < {alpha})", "outside_01": "curva prevê proporções fora de 0–100%"},
        "reasons_title": "Motivos da sinalização",
        "unflagged": "Sem sinal não prova que os dados são normais.",
    },
    "forecast": {
        "title": "Algum setor vai mandar mais podres que boas?",
        "lead": "Linha cheia = histórico (últimos {w} períodos); tracejado e leque = previsão do próximo período com intervalo de 95%.",
        "how": ["A linha cheia mostra a % de podres do setor em cada período.", "Acima da linha de 50%, o setor manda mais podres que boas.", "O leque é o intervalo de 95%: quanto mais largo, mais incerta a previsão; leque hachurado = não confiável."],
        "target": "Período previsto: {p}",
        "pred": "{arrow} {v} previsto",
        "chance": "chance de + podres: {p}",
        "half": "50%",
        "empty": "Dados insuficientes: {n} de {min} períodos mínimos (com ≥ {fruits} frutas cada)",
        "cols": ["Setor", "Períodos", "Frutas", "Tendência por período", "Previsto", "IC 95%", "Chance de + podres", "Erro retroativo", "Erro ingênuo", "Situação"],
        "reliable": "passou nos critérios mínimos",
        "unreliable": "não confiável",
        "insufficient": "dados insuficientes",
        "reasons": {"insufficient_data": "dados insuficientes", "few_periods": "menos de {min} períodos", "no_backtest": "sem teste retroativo possível", "not_better_than_naive": "não supera a previsão ingênua"},
        "reasons_title": "Motivos de “não confiável”",
        "note": "Passar nos critérios mínimos não é garantia de acerto.",
    },
    "line": {
        "lead": "Câmeras fixas sobre a esteira: cada fruta contada, medida e classificada. Os resultados abaixo cobrem o período do escopo; o tamanho das janelas se ajusta à duração do período.",
        "none": "Nenhuma câmera cadastrada corresponde ao escopo.",
        "no_data": "{cam}: sem frutas registradas no escopo.",
        "period": "Período: {a} a {b} · janelas de {w} · {k} janelas completas",
        "kpi_cols": ["Indicador", "Valor", "IC 95% (Wilson)"],
        "throughput": "Frutas por minuto",
        "registered": "Frutas registradas no período",
        "complete": "Frutas em janelas completas",
        "review": "Para revisão (fora das %)",
        "size": "Diâmetro mediano",
        "size_v": "{m} mm (10% a 90%: {lo} a {hi} mm; n = {n})",
        "max": "Máximo de podres da linha",
        "flow": "Fluxo por janela (frutas por classe)",
        "pchart": "Carta de controle: % de podres por janela",
        "center": "mediana",
        "ucl": "limite superior (p′ de Laney, 3σ)",
        "points": "% de podres",
        "alarm": "alarme",
        "alarms": "Alarmes",
        "no_alarms": "Nenhum alarme no período.",
        "alarm_text": {"acima_do_limite": "{time}: % de podres acima do limite superior ({p})", "sequencia_acima_da_mediana": "{time}: 8 janelas seguidas acima da mediana (tendência de piora)"},
        "lots": "Lotes no período",
        "lots_lead": "Aceite pelo IC 95% da % de podres contra o máximo da linha ({max}).",
        "lots_empty": "Nenhum lote registrado no período.",
        "lot_cols": ["Lote", "Início", "Fim", "Frutas", "% podres", "IC 95%", "% baixa qual.", "Situação"],
        "verdicts": {"aprovado": "Aprovado", "reprovado": "Reprovado", "inconclusivo": "Inconclusivo", "sem_dados": "Sem dados", None: "—"},
        "window_cols": ["Início", "Frutas", "Boas", "Baixa qual.", "Podres", "Revisar", "% podres", "Limite sup.", "Alarme"],
        "how": ["Pontos: % de podres por janela; faixa: até o limite superior; losango: alarme.", "Frutas para revisão não entram nas porcentagens de classe."],
    },
    "model": {
        "lead": "Medições do classificador usado pelo sistema, no conjunto indicado. Não são medições de campo.",
        "mismatch": "Atenção: a avaliação registrada é do modelo {a}, mas o sistema está configurado com {b}.",
        "missing": "A avaliação do modelo não está disponível nesta instalação.",
        "cols": ["Medida", "Valor", "Observação"],
        "arch": "Arquitetura",
        "file": "Arquivo do modelo",
        "classes": "Classes",
        "split": "Divisão dos dados",
        "split_v": "por foto de origem, 70/15/15; nenhuma foto em dois conjuntos",
        "test_n": "Teste",
        "test_n_v": "{n} recortes de {p} fotos",
        "acc": "Acurácia",
        "acc_note": "IC 95%: {lo} a {hi} (bootstrap por foto)",
        "bal": "Acurácia balanceada",
        "bal_note": "média da sensibilidade das 3 classes; o acaso dá 33%",
        "base": "Responder sempre a classe mais comum",
        "base_note": "a classe mais comum do teste",
        "recall": "Sensibilidade: {c}",
        "precision": "Precisão: {c}",
        "rg": "Podres classificadas como boas",
        "rg_note": "{k} de {n}; IC 95%: {lo} a {hi}",
        "ece": "Erro de calibração (ECE)",
        "ece_note": "{u} antes da calibração",
        "reject": "Limiar de decisão automática",
        "reject_none": "nenhum ligado: nenhuma fruta é decidida sozinha; todas vão para conferência manual",
        "belt_count": "Esteira simulada: contagem",
        "belt_count_v": "{c} de {x} frutas contadas; {d} duplicadas",
        "belt_acc": "Esteira simulada: acerto ponta a ponta",
        "belt_acc_note": "IC 95%: {lo} a {hi}",
    },
    "method": [
        ("Frutas boas e podres", "No painel, “podres” são todas as frutas não classificadas como boas, de qualquer tipo de defeito (inclusive baixa qualidade). A taxa de podres é podres ÷ total."),
        ("IC 95% de Wilson", "Intervalo de confiança de 95% para uma proporção. Com poucas frutas o intervalo é largo, e o número ainda não é confiável."),
        ("Crescimento", "(período − período anterior) ÷ período anterior. Se o anterior é zero ou vazio, o crescimento é indefinido (n/d), nunca zero. Crescimento e recorrência usam só períodos que os dados cobrem do primeiro ao último dia; frutas de períodos incompletos nas pontas ficam fora e são informadas."),
        ("Recorrência", "Mediana do crescimento da contagem por semana do ano, mês ou estação. A mediana evita que um período atípico domine."),
        ("Defeito dominante", "O tipo de defeito com mais frutas podres na semana; empate quando dois ou mais tipos têm a mesma contagem máxima."),
        ("% de podres por setor e período", "Calculada só em períodos com pelo menos {fruits} frutas no setor; nos demais, fica indefinida."),
        ("Curva normal (gaussiana)", "Média e desvio padrão amostral das % de podres por período de cada setor. Numa curva normal, cerca de 68% dos períodos caem em ±1σ e 95% em ±2σ. O setor é sinalizado com menos de {min} períodos, sem variação, quando o teste de Shapiro-Wilk rejeita a normalidade (p < {alpha}) ou quando mais de {outside} da curva cai fora de 0–100%. Um p alto não prova normalidade."),
        ("Previsão", "Reta ajustada (mínimos quadrados) à % de podres de cada setor por período, estendida um período. O leque é o intervalo de previsão de 95% (t de Student), limitado a 0–100%. A chance de mais podres que boas é a probabilidade, segundo esse modelo, de o próximo valor passar de 50%. São necessários {min_p} períodos para prever."),
        ("Teste retroativo", "A partir do {min_p}º período, o modelo prevê cada período usando só os anteriores, e o erro absoluto médio é comparado ao da previsão ingênua (repetir o último período). A previsão é “não confiável” com menos de {reliable} períodos, sem teste retroativo ou quando não supera a ingênua."),
        ("Carta de controle", "% de podres em cada janela completa, sem as frutas para revisão. A linha central é a mediana do período; o limite superior é o p′ de Laney (3σ), que considera a variação normal entre janelas além do acaso. Alarmes: janela acima do limite; 8 janelas seguidas acima da mediana."),
        ("Aceite de lote", "Aprovado: todo o IC 95% da % de podres do lote está abaixo do máximo da linha. Reprovado: todo o intervalo está acima. Inconclusivo: o intervalo cruza o máximo; precisa de mais frutas ou de inspeção manual."),
        ("Revisão manual", "Frutas que o sistema não decide sozinho ficam “para revisão”: as de confiança abaixo do corte ou, sem corte ligado, todas. Na linha, aparecem como “Revisar” e não entram nas % de classe; no painel, não entram em nenhuma estatística."),
        ("Impressão digital SHA-256", "Resumo criptográfico do escopo e de todos os resultados certificados. Reemitir o certificado com o mesmo escopo e os mesmos dados produz a mesma impressão digital; qualquer mudança nos dados produz outra."),
    ],
    "annex": {
        "lead": "Valores exatos por período, para auditoria. Todas as tabelas usam o escopo da seção 1.",
        "overview": "A.1 Volume e taxa de podres por período",
        "overview_cols": ["Período", "Boas", "Podres", "Total", "Taxa de podres"],
        "deformity": "A.2 Defeitos por semana",
        "deformity_cols": ["Semana", "Podres", "Dominante", "Participação"],
        "growth": "A.3 Crescimento por período completo",
        "recurring": "A.4 Recorrência por semana do ano",
        "props": "A.5 % de podres por setor e período",
        "props_note": "n/d = menos de {fruits} frutas no setor naquele período.",
        "period": "Período",
    },
    "auth": {
        "lead": "Dados para conferir este documento.",
        "number": "Número do certificado",
        "issued": "Data e hora de emissão",
        "user": "Usuário que emitiu",
        "fingerprint": "Impressão digital (SHA-256)",
        "check": "Como conferir: emita de novo o certificado no Painel com os mesmos filtros. Se os dados não mudaram, a impressão digital será idêntica. O número do certificado muda a cada emissão.",
        "rosette": "A roseta é desenhada a partir da impressão digital dos dados: dados iguais produzem exatamente a mesma roseta, e qualquer mudança nos dados produz outra.",
        "qr": "O código QR contém o número, a data de emissão, o escopo e a impressão digital deste certificado, em texto.",
    },
    "section": "SEÇÃO {n}",
    "annex_tab": {"annex_a": "A", "annex_b": "B", "auth": "✓"},
    "figure": "Figura {n}",
    "guide": {
        "title": "Como ler este certificado",
        "classes": "Cores das classes",
        "growth": "Crescimento",
        "notes": "Avisos",
        "marks": "Marcas nos gráficos",
        "warn": "Cautela: amostra pequena, previsão não confiável ou ajuste ruim.",
        "info": "Informação: períodos incompletos fora do cálculo, escala cortada.",
        "hatch": "Hachura: previsão não confiável ou região impossível (abaixo de 0% ou acima de 100%).",
        "na": "n/d: indefinido (por exemplo, crescimento sobre um período vazio). Nunca significa zero.",
        "ci": "IC 95%: intervalo de confiança de 95%. p.p.: pontos percentuais.",
        "tables": "Cada figura é numerada; as tabelas logo abaixo trazem os valores exatos.",
    },
    "kpi": {
        "fruits": "Frutas analisadas",
        "fruits_sub": "no painel, no escopo",
        "rate": "Taxa de podres",
        "rate_sub": "IC 95%: {lo} a {hi}",
        "sectors": "Setores",
        "sectors_sub": "{f} com curva normal sinalizada",
        "forecasts": "Previsões confiáveis",
        "forecasts_sub": "de {n} setores",
        "lots": "Lotes reprovados",
        "lots_sub": "de {n} lotes · {i} inconclusivos",
        "alarms": "Alarmes da linha",
        "alarms_sub": "carta de controle",
        "line": "Frutas nas câmeras",
        "line_sub": "{k} câmeras",
        "pending": "Para revisão",
        "pending_sub": "fora das estatísticas",
    },
    "highlights": "Destaques",
    "find": {
        "rate": "A taxa de podres no escopo é {v} (IC 95%: {lo} a {hi}), sobre {n} frutas.",
        "worst": "Maior taxa de podres: {s} ({v}). Menor: {s2} ({v2}).",
        "fruit": "Fruta mais recebida: {f} ({v} das frutas).",
        "defect": "Na semana mais recente com podres ({w}), {t} domina com {v} das podres.",
        "defect_tie": "Na semana mais recente com podres ({w}), houve empate entre defeitos.",
        "forecast": "{s}: previsão de {v} de podres no próximo período; chance de mais podres que boas {p} ({r}).",
        "gauss": "Curva normal: {ok} sem sinal; {bad} sinalizados ({names}).",
        "growth": "Último período completo ({w}): boas {g}, podres {r} em relação ao anterior.",
        "season": "Por mês, o crescimento das podres se concentra em {m} (mediana {v}).",
        "lot": "{cam}: lote {lot} reprovado, com {v} de podres (IC 95%: {lo} a {hi}) contra o máximo de {max}.",
        "alarms": "{cam}: {n} alarmes na carta de controle ({a} acima do limite, {r} de tendência).",
        "none": "Sem registros suficientes para destaques.",
    },
    "reliable_word": {True: "passou nos critérios mínimos", False: "não confiável"},
    "coverage": {
        "title": "Cobertura dos dados: frutas por setor e período",
        "lead": "Cada célula é um setor em um período; quanto mais escura, mais frutas. Branco: nenhuma fruta. Mostra lacunas, setores novos e a sazonalidade da safra.",
        "legend": "frutas no período",
    },
    "sheets": {
        "title": "Fichas por setor",
        "lead": "Um resumo por setor: volume, taxa de podres com IC 95%, a evolução da % de podres por período e o estado da previsão e da curva normal.",
        "cols": ["Setor", "Frutas", "Taxa de podres", "IC 95%", "% de podres por período", "Último", "Previsão", "Curva normal"],
        "insufficient": "dados insuficientes",
        "ok": "sem sinal",
        "flagged": "sinalizada",
    },
    "line_more": {
        "acceptance": "Aceite dos lotes: % de podres com IC 95% e o máximo da linha",
        "acceptance_lead": "Cada linha é um lote; o traço é o IC 95% e a linha tracejada é o máximo aceito. Aprovado: todo o traço à esquerda; reprovado: todo à direita; inconclusivo: cruza.",
        "max": "máximo {v}",
        "sizes": "Distribuição de tamanho por classe",
        "sizes_axis": "diâmetro (mm)",
        "fruits_axis": "frutas",
    },
    "tech": {
        "lead": "Informações técnicas para auditoria e reprodução deste documento.",
        "software": "Software",
        "params": "Parâmetros estatísticos",
        "model": "Modelo",
        "data": "Dados consultados",
        "doc": "Documento",
        "generator": "Gerador de certificados",
        "generator_v": "FruitCam_ai certificado v{v}",
        "fonts": "Tipografia",
        "fonts_v": "Fraunces, Inter e JetBrains Mono",
        "fonts_fallback": "DejaVu (fontes padrão; as fontes da marca não foram encontradas)",
        "model_file": "Arquivo",
        "model_hash": "SHA-256 do arquivo",
        "model_missing": "arquivo não encontrado",
        "rows": "Registros consultados",
        "rows_v": "{n} no painel + {p} aguardando revisão + {l} das câmeras",
        "period": "Agregação",
        "min_periods": "Períodos mínimos para prever",
        "reliable_periods": "Períodos para previsão confiável",
        "min_fruits": "Frutas mínimas por período e setor",
        "gauss_n": "Períodos mínimos para a curva normal",
        "alpha": "Nível do teste de Shapiro-Wilk",
        "outside": "Massa máxima fora de 0–100%",
        "z": "IC 95% (Wilson)",
        "run": "Regra de tendência da carta",
        "run_v": "{n} janelas seguidas acima da mediana",
        "sigma": "Limite da carta de controle",
        "sigma_v": "p′ de Laney, 3σ",
        "windows": "Janelas da linha no certificado",
        "windows_v": "até {n} janelas; 1, 5, 15 ou 60 min, 4 h, 1 dia ou 1 semana",
    },
    "human": {
        "lead": "A inteligência Artificial pode cometer erros. Recomenda-se que uma pessoa responsável confira os resultados deste certificado antes de qualquer decisão e registre aqui a conferência.",
        "name": "Nome",
        "role": "Função",
        "date": "Data",
        "signature": "Assinatura",
        "notes": "Observações",
    },
}

LABELS = {
    "fruits": {"caju": "Caju", "castanha": "Castanha", "melao": "Melão"},
    "deformities": {"podre": "Podre", "baixa_qualidade": "Baixa qualidade", "queimada": "Queimada", "quebrada": "Quebrada"},
    "classes": {"boa": "Boa", "baixa_qualidade": "Baixa qualidade", "podre": "Podre", "revisar": "Revisar"},
    "seasons": {"summer": "Verão", "autumn": "Outono", "winter": "Inverno", "spring": "Primavera", "rainy": "Chuvosa", "dry": "Seca"},
    "months": ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"],
}


def fill(text, **values):
    return text.format(**values)


def num(x, digits=0):
    if x is None:
        return T["none"]
    s = f"{x:,.{digits}f}"
    return s.replace(",", "\0").replace(".", ",").replace("\0", ".")


def pct(x, digits=1):
    return T["na"] if x is None else f"{num(x * 100, digits)}%"


def signed_pct(x, digits=1):
    return T["na"] if x is None else f"{'+' if x > 0 else ''}{pct(x, digits)}"


def prob(p):
    if p is None:
        return T["none"]
    if p > 0.99:
        return "> 99%"
    if p < 0.01:
        return "< 1%"
    return pct(p, 0)


def pp(x, digits=2, signed=True):
    if x is None:
        return T["na"]
    return f"{'+' if signed and x > 0 else ''}{num(x * 100, digits)} p.p."


def dec(x, digits=3):
    return T["none"] if x is None else num(x, digits)


def pvalue(p):
    if p is None:
        return T["none"]
    return "< 0,001" if p < 0.001 else num(p, 3)


def ci(lo_hi):
    lo, hi = lo_hi
    return T["none"] if lo is None else f"{pct(lo)} a {pct(hi)}"


def period_label(label, period):
    if period == "month":
        y, m = label.split("-")[:2]
        return f"{LABELS['months'][int(m) - 1]}/{y[2:]}"
    y, m, d = label[:10].split("-")
    return f"{d}/{m}/{y[2:]}"


def date_br(value):
    if value is None:
        return T["none"]
    d = value if isinstance(value, (date, datetime)) else datetime.fromisoformat(value)
    return d.strftime("%d/%m/%Y")


def datetime_br(value):
    if value is None:
        return T["none"]
    d = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    return d.strftime("%d/%m/%Y %H:%M")


def clock(value):
    return datetime.fromisoformat(value).strftime("%H:%M")


def bucket_label(view, b):
    if view == "month":
        return LABELS["months"][int(b) - 1]
    if view == "season":
        return LABELS["seasons"].get(b, b)
    return f"S{b}"


def name(kind, key):
    return LABELS[kind].get(key, key)


def minutes_label(m):
    if m % 10080 == 0:
        return "1 semana" if m == 10080 else f"{m // 10080} semanas"
    if m % 1440 == 0:
        return "1 dia" if m == 1440 else f"{m // 1440} dias"
    if m % 60 == 0:
        return "1 h" if m == 60 else f"{m // 60} h"
    return f"{m} min"
