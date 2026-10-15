# Verificações do modelo e da contagem

Escrito em 2026-10-12. Três verificações feitas depois da entrega do `belt_v3`: a calibração e o alarme de podre, o lote de Uganda que ficou de fora, e os erros de contagem. Cada uma tem um relatório com os números em `docs/reports/`.

**Tudo aqui foi medido em fotos de fruto no pé ou na esteira simulada. Nada foi medido numa esteira real.**

---

## 1. Calibração e alarme de podre

Relatório: [docs/reports/calibration/report.md](../reports/calibration/report.md). Ferramenta: `python tools/calibration_v3.py`.

### Conceitos

- **Calibração**: um modelo está calibrado quando, das respostas dadas com 80% de confiança, cerca de 80% estão certas.
- **ECE** (erro de calibração esperado): a distância média entre a confiança e o acerto, em faixas de confiança. Zero é o ideal.
- **Temperatura**: um único número que divide as saídas do modelo antes de virarem probabilidades. Acima de 1, deixa o modelo menos confiante. Não muda qual classe ganha, só a confiança.
- **Precisão de podre**: dos alarmes de podre, quantos eram podres.
- **Sensibilidade de podre**: das frutas podres, quantas o modelo apontou.
- **Podres chamadas de boas**: o erro mais caro para o produto.

### O que foi feito

1. A temperatura foi ajustada **só na validação** (3.335 recortes de 451 fotos) e o resultado foi lido **só no teste** (3.016 recortes de 417 fotos). Nenhuma foto está nos dois.
2. Para cada classe, traçamos a curva de precisão contra sensibilidade.
3. Testamos uma regra para reduzir alarmes falsos: responder "podre" só quando a probabilidade de podre passa de um corte. O corte foi escolhido na validação, como o mais alto que mantinha as podres chamadas de boas em até 5%, e depois lido no teste.
4. Procuramos cópias quase iguais entre treino e teste.

### O que saiu

| Medida no teste (n = 3.016) | Valor |
|---|---|
| Temperatura ajustada na validação | 1,403 (a do modelo é 1,402) |
| ECE antes e depois | 0,040 → 0,012 (redução: IC 95% de 0,014 a 0,033) |
| Recortes de teste com cópia quase igual no treino | 31 (até 4 bits de diferença); sem eles a acurácia balanceada vai de 89,2% para 89,1% |

**A calibração geral está boa, mas a da classe podre não.** Quando o modelo dá de 90% a 100% de probabilidade de podre, 74% das frutas eram podres (n = 157); de 80% a 90%, metade (n = 78). O motivo provável é a proporção: o treino sorteou as três classes em partes iguais, e no teste as podres são 7%.

**O corte para podre não passou.**

| Regra | Precisão de podre | Sensibilidade de podre | Podres chamadas de boas |
|---|---|---|---|
| Atual (classe mais provável) | 45,3% (182 de 402) | 87,9% (182 de 207) | 3,9% (8 de 207; IC 95% de 2,0% a 7,4%) |
| Corte de 0,80, escolhido na validação | 66,0% (155 de 235) | 74,9% (155 de 207) | **5,8%** (12 de 207; IC 95% de 3,3% a 9,9%) |

Na validação o corte de 0,80 ficava em 4,9%. No teste foi a 5,8%, acima do limite. **Resultado negativo: a regra do app não mudou.**

Duas observações honestas:

- Com 207 frutas podres no teste, nem a regra atual pode ser garantida abaixo de 5%: o intervalo dela vai até 7,4%.
- Olhando o teste depois, cortes entre 0,50 e 0,75 ficam dentro do limite e têm precisão maior (46,6% a 62,4%). Escolher um deles agora seria escolher olhando a resposta, então não é uma proposta. É uma hipótese para conferir com as bandejas da esteira.

A figura 9 da página **Como funciona** mostra os três resultados, e o texto da página diz que a tentativa falhou.

### Testes

[core/tests/test_model_checks.py](../../core/tests/test_model_checks.py), classes `CalibrationToolTests` (4) e `CalibrationReportTests` (4): a temperatura é recuperada de dados com resposta conhecida; a regra de corte só tira respostas de "podre"; a curva bate com um caso feito à mão; a busca de cópias acha a cópia plantada; o relatório não mistura validação e teste; a regra atual do relatório é a guardada no treino; um corte que estoura o limite não é proposto e o site diz isso; o app continua respondendo a classe mais provável e mandando tudo para conferência.

---

## 2. O lote excluído de Uganda

Relatório, com as folhas de contato: [docs/reports/uganda_diagnosis/report.md](../reports/uganda_diagnosis/report.md). Ferramenta: `python tools/diagnose_uganda.py`.

A pergunta era por que o modelo responde "baixa qualidade" para quase todo fruto desse lote. Só diagnóstico; nada foi retreinado.

| Hipótese | Veredito | Evidência principal |
|---|---|---|
| Os números de classe estão em outra ordem | Não sustentada | Nas fotos originais, a classe 1 são flores e a 2 são frutos claros imaturos, como diz o artigo |
| As fotos são diferentes | Sustentada | As caixas dos frutos são cerca de 2,5 vezes menores; só de 1% a 7% chegam aos 24 px do treino |
| O critério de anotação é outro | Sustentada | "Estragado" é a classe mais comum do lote (15 por foto, contra 1,1 e 0,1 nos lotes confiáveis); só 7 de 149 recortes "maduros" têm cor de fruto maduro, contra 72% nos lotes confiáveis |

As duas últimas se somam e não deu para separar o peso de cada uma. **O lote continua fora.**

Um achado à parte: a tabela de contagens publicada no artigo do conjunto é a soma dos números de classe nos dois lotes, sem distinguir a ordem. Ela não serve para conferir o significado das classes.

A pergunta aos autores ficou mais precisa (o que as classes 4 e 5 significavam nesse lote) e está em [docs/data/requests.md](../data/requests.md). Não foi enviada.

Testes: `UgandaDiagnosisTests` (2) em [core/tests/test_model_checks.py](../../core/tests/test_model_checks.py).

---

## 3. Erros de contagem

Relatório: [docs/reports/counting/report.md](../reports/counting/report.md). Ferramenta: `python tools/count_errors.py`.

### Conceitos

- **Segmentação por cor**: o detector marca como fruta todo pixel cuja cor difere bastante da cor da esteira. Cada mancha de pixels marcados vira uma detecção.
- **Contagem dupla**: uma fruta que vira duas manchas e recebe duas contagens.
- **Sobreposição**: duas frutas que se encostam ou se cobrem viram uma mancha só e recebem uma contagem.

Os dois erros puxam para lados opostos, e os remédios também: o que junta manchas arrisca juntar duas frutas, e o que corta manchas arrisca cortar uma fruta.

### Como foi medido

- **Frutas reais em espaçamento normal:** 8 minutos simulados com os recortes de teste colados pelo contorno, 891 frutas cruzando a linha. É o cenário da figura 8.
- **Frutas desenhadas, por nível de sobreposição:** 60 segundos simulados por nível (de 108 a 545 frutas).

### Contagem dupla

As duas frutas contadas em dobro eram podres, com uma parte tão escura quanto a esteira. Três mudanças foram medidas:

| Mudança | Onde | Duplicadas em 891 | Decisão |
|---|---|---|---|
| Nenhuma (antes) | | 2 | |
| Ponte: ligar duas manchas quando há entre elas pixels um pouco diferentes da esteira | detector | **3** | Recusada: piorou |
| Fusão: duas manchas que o detector não cortou, com caixas 25% sobrepostas e cruzando a linha com até 0,05 s de diferença, contam como uma fruta | rastreador | **0** | **Adotada** |

A fusão não mudou a contagem das frutas desenhadas em espaçamento normal nem com sobreposição de até 40 mm a 6 frutas por segundo. No caso mais extremo (até 40 mm, 10 por segundo) ela fundiu 2 frutas distintas em 545, e o erro foi de −31,0% para −31,4%. É o custo conhecido da regra.

A regra só olha manchas que o detector **não** cortou. Duas frutas encostadas que o detector separou com uma linha de corte nunca são fundidas.

Com a regra ligada, a simulação da figura 8 passou a dar 891 contagens para 891 frutas.

### Sobreposição pesada

Ao escrever um teste para a marcação das manchas cortadas, apareceu um defeito: a linha de corte entre duas frutas tinha 1 pixel de espessura e deixava passagem pela diagonal. Muitas frutas "cortadas" continuavam ligadas e eram contadas como uma. A melhoria testada foi fechar a linha (2 pixels).

| Sobreposição | Antes | Com o corte fechado |
|---|---|---|
| Espaçamento normal, frutas desenhadas | 0,0% | 0,0% |
| Até 10 mm | −0,7% | 0,0% |
| Até 25 mm | −2,3% | 0,0% |
| Até 40 mm | −20,9% | −3,5% |
| Até 40 mm, 10 por segundo | −31,0% | −10,1% |
| **Frutas reais em espaçamento normal: duplicadas em 891** | **2** | **8** |

**Decisão: fica desligado.** O corte fechado é muito melhor quando as frutas chegam sobrepostas, mas com frutas reais em espaçamento normal ele passou a cortar frutas inteiras em duas: o caju com a castanha tem uma cintura que o programa confunde com o encontro de duas frutas. A regra combinada era manter o comportamento antigo se o novo fosse pior em algum caso, e ele é pior neste.

Uma passagem mais estrita junto com o corte fechado reduz o problema sem resolver: com o limite de cintura em 0,5 ficam 2 duplicadas em 891 e −10,3% a 40 mm; com 0,6, 4 duplicadas e −8,3%.

A opção existe no código (`BeltDetector(seal=True)`) para uma linha onde as frutas chegam amontoadas. Qual lado do compromisso vale depende de como a fruta chega na esteira de verdade, e isso só se decide com a gravação.

### O que não foi verificado

- Tudo é simulação. As duas regras foram ajustadas e medidas no mesmo simulador, sem um conjunto separado para conferir.
- Numa esteira real, sombras, brilho e sujeira mudam o que o detector vê.
- A fusão foi medida com frutas espaçadas e com frutas desenhadas sobrepostas, não com frutas reais sobrepostas.

### Testes

`CountingOptionTests` (2) em [core/tests/test_model_checks.py](../../core/tests/test_model_checks.py): duas manchas coladas que cruzam a linha juntas contam uma vez, e duas vezes quando o detector as cortou ou a regra está desligada; a linha de corte fechada separa de fato dois discos encostados, e a aberta não. Os testes de contagem exata que já existiam em [core/tests/test_belt.py](../../core/tests/test_belt.py) continuam passando com a fusão ligada.

---

## 4. Suíte completa

Rodada em 2026-10-13, nesta máquina, com os dados presentes.

| Momento | Testes | Passaram | Falharam | Pulados | Duração |
|---|---|---|---|---|---|
| Antes de qualquer mudança | 163 | 163 | 0 | 0 | 15,9 min |
| Depois de tudo, primeira rodada | 193 | 192 | 1 | 0 | 16,7 min |
| Depois de tudo, segunda rodada | 193 | 193 | 0 | 0 | 16,2 min |

A falha da primeira rodada foi uma regra que já existia: toda figura marcada como teste precisa dizer na legenda "desempenho em esteira real não avaliado". A legenda da figura 9 dizia a mesma coisa com outras palavras. Foi corrigida e a suíte rodou de novo.

Saída real da segunda rodada: [docs/reports/tests/kit_checks_ttst_test_output.txt](../reports/tests/kit_checks_ttst_test_output.txt).
