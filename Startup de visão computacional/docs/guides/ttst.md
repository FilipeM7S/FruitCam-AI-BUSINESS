# Autotreino em tempo de teste (TTST)

Escrito em 2026-10-12. Este guia explica o módulo `training/ttst.py`, do conceito ao código, e o experimento que o acompanha.

**Estado: desligado e fora do app.** Nenhum arquivo do app importa o módulo. Ele só roda com a variável `FRUITCAM_TTST=1`, e quem a liga hoje é apenas a ferramenta de experimento. **Nada aqui foi validado numa esteira real.**

---

## 1. O problema

O classificador aprendeu com fotos de fruto no pé. Na esteira, a luz, o fundo e o ângulo mudam. Esse desencontro entre os dados de treino e os de uso se chama **mudança de domínio**, e costuma derrubar o acerto.

A saída mais segura é gravar bandejas rotuladas na esteira e treinar com elas ([docs/guides/real_belt_kit.md](real_belt_kit.md)). O TTST é uma ideia complementar: deixar o modelo se ajustar um pouco, na própria linha, usando as frutas que passam.

---

## 2. A ideia em palavras simples

1. O modelo classifica cada fruta que passa.
2. Quando ele está muito seguro, guardamos a fruta com a resposta dele como se fosse o rótulo. Isso é um **pseudo-rótulo**.
3. Quando um operador corrige uma resposta, guardamos a correção. Ela sempre vale mais que o pseudo-rótulo.
4. De tempos em tempos, o modelo treina um pouco com o que foi guardado.
5. Antes de aceitar o resultado, medimos o modelo num conjunto que ele nunca usa para treinar. Se piorou, desfazemos.

O risco do passo 2 é o modelo ensinar a si mesmo os próprios erros. Os passos 3 e 5 existem para conter esse risco.

---

## 3. Como isso se relaciona com outras técnicas

| Técnica | O que faz | Relação com o TTST daqui |
|---|---|---|
| **Autotreino** (self-training, pseudo-rótulos) | Treina com as respostas confiantes do próprio modelo | É o núcleo do TTST: os passos 2 e 4 |
| **Adaptação em tempo de teste** (Tent; AdaBN) | Ajusta o modelo durante o uso, sem rótulos. O Tent reduz a incerteza das respostas; o AdaBN só recalcula as estatísticas de normalização | Mesma família. O TTST daqui usa pseudo-rótulos e correções, e treina em modo que também atualiza as estatísticas de normalização |
| **Treino em tempo de teste** (TTT) | Usa uma tarefa auxiliar sem rótulo, como adivinhar a rotação da imagem, para ajustar o modelo a cada amostra | Parente próximo, com outra fonte de sinal |
| **Treino adversário de domínio** (DANN) | Treina, junto com o classificador, uma segunda rede que tenta adivinhar de que domínio veio cada imagem; o classificador aprende a enganá-la, e suas características ficam parecidas nos dois domínios | Técnica diferente, usada no treino, com dados dos dois domínios ao mesmo tempo. Não está implementada aqui |
| **GAN** | Duas redes: uma **gera** imagens falsas, a outra tenta distingui-las das reais | Não é o que fazemos. Ver abaixo |

### Por que não é uma GAN

Uma GAN é um modelo **gerador**: o produto final é uma rede que fabrica dados novos (imagens). A disputa entre as duas redes serve para as imagens fabricadas ficarem realistas.

O TTST não fabrica nada. Ele tem uma rede só, o classificador, que é ajustado com frutas reais e rótulos (pseudo ou do operador). Não há gerador, não há discriminador, não há disputa.

A confusão é comum porque o DANN também tem "adversário" no nome. No DANN a segunda rede não gera imagens: ela só tenta dizer "esta imagem é do treino ou da esteira?", e serve para alinhar os dois domínios. É treino adversário sem ser GAN. O TTST daqui não é nem um nem outro: é autotreino com travas.

Seria possível usar uma GAN para outra coisa, por exemplo transformar fotos de fruto no pé em imagens com aparência de esteira antes de treinar. É outra linha de trabalho, não testada aqui.

---

## 4. O código

[training/ttst.py](../../training/ttst.py) tem três peças.

### A chave

`enabled()` devolve verdadeiro só quando `FRUITCAM_TTST=1`. Sem isso, `Adapter.step` levanta um erro e não toca em nada.

### O depósito: `Buffer`

| Regra | Como está no código |
|---|---|
| Só entram respostas confiantes | `offer(chave, recorte, probabilidades)` recusa abaixo de `threshold` (padrão 0,9) |
| A correção do operador sempre vale | `correct(chave, recorte, rótulo)` grava por cima de qualquer coisa; um pseudo-rótulo posterior para a mesma fruta é recusado |
| Tamanho limitado | No máximo `per_class` pseudo-rótulos por classe; os mais antigos saem. Correções nunca saem |

### O ajuste: `Adapter.step`

Em ordem:

1. Confere a chave. Desligado: erro.
2. Confere que nenhum item do conjunto de controle está no depósito. Se estiver: erro. O controle nunca é usado para treinar.
3. Confere o **mínimo por classe** (`min_per_class`). Se faltar, pula a atualização e registra.
4. Mede o modelo no controle: acurácia balanceada e sensibilidade de podre.
5. Guarda uma cópia dos pesos.
6. Treina `steps` passos com lotes equilibrados por classe. Correções do operador pesam mais (`operator_weight`).
7. **Limita o tamanho da mudança.** Calcula quanto os pesos mudaram em relação ao tamanho deles. Se passou de `max_update`, encolhe a mudança até o limite.
8. Mede de novo no controle.
9. **Reverte** se a acurácia balanceada ou a sensibilidade de podre caiu mais que `tolerance`. Os pesos voltam exatamente aos guardados.
10. **Registra** uma linha em arquivo: hora, conteúdo do depósito, medidas antes e depois, tamanho da mudança, decisão e motivo.

`Adapter.save` grava o modelo ajustado com `reject_below = None`. O módulo nunca liga corte de confiança.

---

## 5. O experimento

`python tools/ttst_experiment.py`. Resultado em [docs/reports/ttst/ttst.json](../reports/ttst/ttst.json) e o registro das nove atualizações em [docs/reports/ttst/updates.jsonl](../reports/ttst/updates.jsonl).

### A mudança de domínio simulada

Não temos esteira. Simulamos a mudança assim: o modelo foi treinado com fotos de fruto no pé; o alvo é o mesmo tipo de fruto, recortado e colado sobre quadros de vídeo real de linhas de seleção (os clipes de cítricos e de maçã, que nunca entraram no treino).

| Conjunto | Papel | Recortes | Fotos | podre |
|---|---|---|---|---|
| Fluxo | O que "passa na linha"; o modelo não vê os rótulos | 1.284 | 221 | 84 |
| Controle | Nunca treinado; decide aceitar ou reverter | 705 | 204 | 99 |
| Teste do alvo | Só para relatar, antes e depois | 2.568 | 416 | 207 |

Nenhuma foto aparece em dois conjuntos. Os fundos também são separados: 29 quadros para fluxo e controle, outros 29 para o teste.

Ajustes, fixados antes de rodar: confiança mínima 0,9; 60 passos; taxa de aprendizado 0,0001; mudança máxima de 5% dos pesos; tolerância de 0,5 ponto no controle. Três repetições com sementes diferentes.

Ponto de partida no teste do alvo: acurácia balanceada de **77,0%** (IC 95% de 74,3% a 79,7%), sensibilidade de podre 171 de 207.

### Caso 1: só pseudo-rótulos

Dos 1.284 recortes do fluxo, 454 entraram no depósito e 830 foram recusados por confiança baixa. 25 dos 454 pseudo-rótulos estavam errados (5,5%).

| Semente | Decisão | Controle | Teste do alvo | Ganho (IC 95% pareado por foto) | Fotos de campo |
|---|---|---|---|---|---|
| 0 | aceita | 75,2% → 77,1% | 77,0% → 78,0% | −0,4 a +2,4 pontos | 88,9% → 88,3% |
| 1 | aceita | 75,2% → 77,1% | 77,0% → 78,3% | −0,2 a +2,8 pontos | 88,9% → 88,1% |
| 2 | aceita | 75,2% → 77,5% | 77,0% → 77,7% | −0,8 a +2,2 pontos | 88,9% → 88,5% |

**Leitura: mantém.** O ganho é pequeno e o intervalo inclui zero nas três vezes. No domínio original o modelo perde cerca de meio ponto.

### Caso 2: pseudo-rótulos mais correções do operador

10% do fluxo (128 recortes sorteados) recebeu o rótulo verdadeiro, como se um operador tivesse conferido.

| Semente | Decisão | Controle: acurácia balanceada | Controle: sensibilidade de podre |
|---|---|---|---|
| 0 | **revertida** | 75,2% → 80,6% | 75,8% → 68,7% |
| 1 | **revertida** | 75,2% → 79,9% | 75,8% → 67,7% |
| 2 | **revertida** | 75,2% → 78,5% | 75,8% → 68,7% |

A acurácia balanceada subiu, mas a sensibilidade de podre caiu, e a trava reverteu as três. Para saber se ela acertou, medimos no teste o que teria acontecido:

| Semente | Teste do alvo, se mantida | Ganho (IC 95%) | Sensibilidade de podre | Podres chamadas de boas |
|---|---|---|---|---|
| partida | 77,0% | | 171 de 207 | 8 |
| 0 | 79,4% | +0,6 a +4,4 pontos | 149 de 207 | 15 |
| 1 | 79,5% | +0,6 a +4,4 pontos | 141 de 207 | 21 |
| 2 | 80,4% | +1,5 a +5,1 pontos | 160 de 207 | 13 |

**Leitura: melhoraria a média e pioraria o que mais importa.** As correções ensinam o modelo a dar menos alarmes de podre, porque muitos alarmes confiantes dele estão errados. A acurácia balanceada sobe, mas de 11 a 30 frutas podres a mais passariam sem alarme, e as podres chamadas de boas iriam de 8 para 13 a 21. A trava de sensibilidade de podre barrou isso. Foi a decisão certa para o produto, ao custo de recusar um ganho real na média.

### Caso 3: 30% dos rótulos trocados de propósito

30% dos itens do depósito tiveram o rótulo trocado por um errado, como correções erradas de operador.

| Semente | Rótulos errados no depósito | Decisão | Controle | Teste do alvo, se mantida (IC 95% da mudança) |
|---|---|---|---|---|
| 0 | 152 de 454 | **revertida** | 75,2% → 66,2% | 67,0% (−11,8 a −8,2 pontos) |
| 1 | 154 de 454 | **revertida** | 75,2% → 61,9% | 64,6% (−14,4 a −10,5 pontos) |
| 2 | 154 de 454 | **revertida** | 75,2% → 64,2% | 66,7% (−12,2 a −8,2 pontos) |

**Leitura: a reversão dispara.** Nas três vezes o controle acusou a queda e os pesos voltaram ao ponto de partida.

### Resumo

| Pergunta | Resposta medida |
|---|---|
| A adaptação melhora, mantém ou piora? | Só com pseudo-rótulos: mantém (ganho de 0,7 a 1,3 ponto, não distinguível de zero). Com correções: subiria a média em 2,4 a 3,4 pontos, mas derrubaria a sensibilidade de podre |
| A reversão dispara com rótulos errados? | Sim, 3 de 3 |
| A trava erra para o lado seguro? | Sim: recusou 3 atualizações que melhorariam a média, porque custavam frutas podres |

---

## 6. Limites e o que não foi verificado

- **Não é esteira.** O alvo é uma colagem sobre quadros de vídeo. Luz, sombra, movimento e ângulo reais são outra coisa.
- **Uma atualização por caso.** O uso real teria muitas, em sequência. Erros pequenos podem se acumular de um jeito que este experimento não mostra.
- **Um conjunto de ajustes.** Limiar, passos, taxa e limites foram fixados antes e não foram explorados.
- **Controle pequeno.** São 99 frutas podres; uma fruta a mais ou a menos muda a sensibilidade em 1 ponto. Com tolerância de 0,5 ponto, a trava é sensível a ruído.
- **Controle e fluxo usam os mesmos 29 fundos.** O teste usa outros.
- **O controle precisa de rótulos confiáveis.** Numa linha real, isso quer dizer bandejas separadas à mão, guardadas só para esse fim.
- **Operador simulado.** As "correções" são rótulos do conjunto de dados, não de uma pessoa na linha.
- **A calibração não foi refeita** depois da atualização. A confiança do modelo ajustado não foi conferida.
- **O módulo não está ligado a câmera nenhuma.** Não há código que alimente o depósito a partir da linha.

**Recomendação:** não usar em piloto antes de ter um conjunto de controle gravado na esteira real e de repetir este experimento com ele.

---

## 7. Testes

[core/tests/test_ttst.py](../../core/tests/test_ttst.py), 6 testes, com o modelo real e frutas desenhadas:

| Teste | O que prova |
|---|---|
| `..._only_confident_answers_enter_and_the_operator_always_wins` | O limiar de confiança, a prioridade da correção e o limite por classe |
| `..._nothing_runs_while_the_flag_is_off` | Sem a variável, nada roda, nada é gravado, os pesos não mudam; nenhum arquivo do app menciona o módulo |
| `..._control_items_can_never_be_trained_on` | Item de controle no depósito é erro |
| `..._a_thin_buffer_is_skipped_and_logged` | Abaixo do mínimo por classe, a atualização é pulada e registrada |
| `..._correct_labels_are_accepted_within_the_update_limit` | A mudança aplicada fica dentro do limite (pedido 1,58%, limite 1%, medido 1,00%) |
| `..._wrong_labels_are_rolled_back_to_the_exact_starting_weights` | Com todos os rótulos errados, o controle cai de 100% para 0% e os pesos voltam idênticos |

---

## 8. Leituras

Referências conferidas com uma ferramenta de verificação bibliográfica (título, autores e identificador no arXiv):

- Wang, Shelhamer, Liu, Olshausen, Darrell. *Tent: Fully Test-time Adaptation by Entropy Minimization*. arXiv:2006.10726.
- Li, Wang, Shi, Liu, Hou. *Revisiting Batch Normalization For Practical Domain Adaptation* (AdaBN). arXiv:1603.04779.
- Sun, Wang, Liu, Miller, Efros, Hardt. *Test-Time Training with Self-Supervision for Generalization under Distribution Shifts*. arXiv:1909.13231.
- Ganin, Ustinova, Ajakan, Germain, Larochelle, Laviolette, Marchand, Lempitsky. *Domain-Adversarial Training of Neural Networks* (DANN). arXiv:1505.07818.
- Goodfellow, Pouget-Abadie, Mirza, Xu, Warde-Farley, Ozair, Courville, Bengio. *Generative Adversarial Networks*. arXiv:1406.2661.

A referência clássica de pseudo-rótulos (Lee, 2013, numa oficina de conferência) não foi encontrada pela ferramenta de verificação e por isso não entra na lista.
