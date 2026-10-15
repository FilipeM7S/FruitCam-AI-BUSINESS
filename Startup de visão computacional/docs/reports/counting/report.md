# Erros de contagem na esteira simulada

Gerado a partir de [counting.json](counting.json), que `python tools/count_errors.py` escreve. Explicação em [docs/guides/model_checks.md](../../guides/model_checks.md), seção 3.

**Simulação. Nada aqui foi medido numa esteira real.**

## Como foi medido

- **Frutas reais:** 8 minutos simulados, 2 frutas por segundo, espaçamento normal, com os recortes de teste do `belt_v3` colados pelo contorno. É o mesmo cenário da figura 8. n = 891 frutas cruzando a linha.
- **Frutas desenhadas:** 60 segundos simulados por nível de sobreposição. n por nível: espaçamento normal 108, sobreposição até 10 mm 305, sobreposição até 25 mm 308, sobreposição até 40 mm 339, sobreposição até 40 mm, 10 por segundo 545.
- **Duplicada:** uma fruta verdadeira que recebeu duas contagens.
- As colunas de sobreposição mostram o erro de contagem: (contadas − cruzaram) ÷ cruzaram.

## Resultado

| Variante | Frutas reais: contadas | Duplicadas | Fundidas pelo rastreador | Tamanho medido ÷ real | espaçamento normal | sobreposição até 10 mm | sobreposição até 25 mm | sobreposição até 40 mm | sobreposição até 40 mm, 10 por segundo |
|---|---|---|---|---|---|---|---|---|---|
| atual | 893 de 891 | 2 (IC 95% 0,1% a 0,8%) | 0 | 1,019 | 0,0% | −0,7% | −2,3% | −20,9% | −31,0% |
| ponte no detector | 894 de 891 | 3 (IC 95% 0,1% a 1,0%) | 0 | 1,019 | 0,0% | −0,7% | −2,6% | −21,2% | −31,0% |
| **fusão no rastreador** | 891 de 891 | 0 (IC 95% 0,0% a 0,4%) | 2 | 1,019 | 0,0% | −0,7% | −2,3% | −20,9% | −31,4% |
| corte fechado | 899 de 891 | 8 (IC 95% 0,5% a 1,8%) | 0 | 1,019 | 0,0% | 0,0% | 0,0% | −3,5% | −10,1% |
| corte fechado e fusão | 897 de 891 | 6 (IC 95% 0,3% a 1,5%) | 2 | 1,019 | 0,0% | 0,0% | 0,0% | −3,5% | −10,5% |

### Corte fechado com passagem mais estrita

Rodada à parte, [closed_cut_neck.json](closed_cut_neck.json), com os mesmos cenários.

| Variante | Frutas reais: contadas | Duplicadas | Fundidas pelo rastreador | Tamanho medido ÷ real | espaçamento normal | sobreposição até 10 mm | sobreposição até 25 mm | sobreposição até 40 mm | sobreposição até 40 mm, 10 por segundo |
|---|---|---|---|---|---|---|---|---|---|
| corte fechado, passagem 0,5, fusão | 893 de 891 | 2 (IC 95% 0,1% a 0,8%) | 2 | 1,019 | 0,0% | 0,0% | 0,0% | −10,3% | −20,6% |
| corte fechado, passagem 0,6, fusão | 895 de 891 | 4 (IC 95% 0,2% a 1,1%) | 2 | 1,019 | 0,0% | 0,0% | 0,0% | −8,3% | −15,2% |

## O que cada variante é

| Variante | Mudança |
|---|---|
| atual | O comportamento anterior a este trabalho |
| ponte no detector | Liga duas manchas quando há, entre elas, pixels um pouco diferentes da esteira (60% do limiar) |
| fusão no rastreador | Se duas manchas que o detector não cortou têm caixas com 25% ou mais de sobreposição e cruzam a linha com até 0,05 s de diferença, conta uma só |
| corte fechado | A linha que separa duas frutas encostadas passa a ter 2 pixels, sem vazamento pela diagonal |
