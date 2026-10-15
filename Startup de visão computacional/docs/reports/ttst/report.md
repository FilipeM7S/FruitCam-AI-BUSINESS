# Experimento de autotreino em tempo de teste (TTST)

Gerado a partir de [ttst.json](ttst.json), que `python tools/ttst_experiment.py` escreve. O registro de cada atualização está em [updates.jsonl](updates.jsonl). Explicação em [docs/guides/ttst.md](../../guides/ttst.md).

**Mudança de domínio simulada: fruto recortado e colado sobre quadros de vídeo real. Não é esteira. O módulo está desligado e fora do app.**

## Dados

| Conjunto | Recortes | Fotos | boa | baixa qualidade | podre |
|---|---|---|---|---|---|
| Fluxo (o modelo não vê os rótulos) | 1284 | 221 | 400 | 800 | 84 |
| Controle (nunca treinado) | 705 | 204 | 206 | 400 | 99 |
| Teste do alvo (só relato) | 2568 | 416 | 775 | 1586 | 207 |

Fotos em dois conjuntos: fluxo e controle 0, fluxo e teste 0, controle e teste 0. Fundos: 29 quadros para fluxo e controle, outros 29 para o teste.

Ajustes fixados antes de rodar: confiança mínima 0.9; 60 passos; taxa 0.0001; mudança máxima 5% dos pesos; tolerância 0.005 no controle; correções em 10% do fluxo; rótulos trocados em 30% do depósito.

Ponto de partida no teste do alvo (n = 2568, 416 fotos): acurácia balanceada 77,0% (IC 95% 74,3% a 79,7%); sensibilidade de podre 171 de 207; podres chamadas de boas 8 de 207.

## Resultados

| Caso | Semente | Depósito (errados) | Decisão | Controle: acurácia balanceada | Controle: sensibilidade de podre | Teste do alvo | Mudança no teste (IC 95% pareado por foto) | Teste em fotos de campo |
|---|---|---|---|---|---|---|---|---|
| Só pseudo-rótulos | 0 | 454 (25) | aceita | 75,2% → 77,1% | 75,8% → 79,8% (n = 99) | 77,0% → 78,0% | −0,4 a +2,4 pontos | 88,9% → 88,3% |
| Com correções do operador | 0 | 538 (23) | revertida | 75,2% → 80,6% | 75,8% → 68,7% (n = 99) | 77,0% → 77,0% | +0,0 a +0,0 pontos | 88,9% → 88,9% |
| 30% dos rótulos trocados de propósito | 0 | 454 (152) | revertida | 75,2% → 66,2% | 75,8% → 76,8% (n = 99) | 77,0% → 77,0% | +0,0 a +0,0 pontos | 88,9% → 88,9% |
| Só pseudo-rótulos | 1 | 454 (25) | aceita | 75,2% → 77,1% | 75,8% → 79,8% (n = 99) | 77,0% → 78,3% | −0,2 a +2,8 pontos | 88,9% → 88,1% |
| Com correções do operador | 1 | 533 (23) | revertida | 75,2% → 79,9% | 75,8% → 67,7% (n = 99) | 77,0% → 77,0% | +0,0 a +0,0 pontos | 88,9% → 88,9% |
| 30% dos rótulos trocados de propósito | 1 | 454 (154) | revertida | 75,2% → 61,9% | 75,8% → 78,8% (n = 99) | 77,0% → 77,0% | +0,0 a +0,0 pontos | 88,9% → 88,9% |
| Só pseudo-rótulos | 2 | 454 (25) | aceita | 75,2% → 77,5% | 75,8% → 80,8% (n = 99) | 77,0% → 77,7% | −0,8 a +2,2 pontos | 88,9% → 88,5% |
| Com correções do operador | 2 | 537 (20) | revertida | 75,2% → 78,5% | 75,8% → 68,7% (n = 99) | 77,0% → 77,0% | +0,0 a +0,0 pontos | 88,9% → 88,9% |
| 30% dos rótulos trocados de propósito | 2 | 454 (154) | revertida | 75,2% → 64,2% | 75,8% → 74,7% (n = 99) | 77,0% → 77,0% | +0,0 a +0,0 pontos | 88,9% → 88,9% |

## O que teria acontecido com as atualizações revertidas

Medido no teste do alvo com os pesos que a trava recusou. Serve para conferir se a trava decidiu bem.

| Caso | Semente | Acurácia balanceada se mantida | Mudança (IC 95% pareado por foto) | Sensibilidade de podre | Podres chamadas de boas |
|---|---|---|---|---|---|
| Ponto de partida | | 77,0% | | 171 de 207 | 8 |
| Com correções do operador | 0 | 79,4% | +0,6 a +4,4 pontos | 149 de 207 | 15 |
| 30% dos rótulos trocados de propósito | 0 | 67,0% | −11,8 a −8,2 pontos | 170 de 207 | 13 |
| Com correções do operador | 1 | 79,5% | +0,6 a +4,4 pontos | 141 de 207 | 21 |
| 30% dos rótulos trocados de propósito | 1 | 64,6% | −14,4 a −10,5 pontos | 180 de 207 | 11 |
| Com correções do operador | 2 | 80,4% | +1,5 a +5,1 pontos | 160 de 207 | 13 |
| 30% dos rótulos trocados de propósito | 2 | 66,7% | −12,2 a −8,2 pontos | 169 de 207 | 15 |

## Leitura

- **Só pseudo-rótulos: mantém.** As três atualizações foram aceitas; o ganho no teste do alvo é pequeno e o intervalo inclui zero. No domínio original há perda de cerca de meio ponto.
- **Com correções: a média subiria, a sensibilidade de podre cairia.** A trava reverteu as três por causa da queda de sensibilidade de podre no controle. No teste, a queda se confirma: mais podres passariam sem alarme e mais seriam chamadas de boas.
- **Rótulos errados de propósito: a reversão dispara** nas três repetições. Mantidas, as atualizações derrubariam o teste do alvo em cerca de 10 a 12 pontos.

## Não verificado

Esteira real; atualizações em sequência; outros ajustes; operador de verdade; calibração depois da atualização. O controle tem 99 frutas podres, então a trava de sensibilidade é sensível a uma fruta.
