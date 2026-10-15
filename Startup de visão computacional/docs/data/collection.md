# Gravação na esteira: checklist de campo

Uma página para levar no dia. O porquê de cada item e o funcionamento das ferramentas estão em [docs/guides/real_belt_kit.md](../guides/real_belt_kit.md).

**A ideia:** duas pessoas separam as frutas à mão em bandejas (boa, baixa qualidade, podre). Cada bandeja passa sozinha na esteira, e tudo o que a câmera vê nessa passagem recebe o rótulo da bandeja. Ninguém desenha caixas.

## 1. Levar

- [ ] Notebook com o projeto instalado e este checklist impresso
- [ ] Câmera, suporte fixo, cabos e fonte (o suporte não pode mexer entre bandejas)
- [ ] Iluminação própria: painel ou barra de LED sem cintilação
- [ ] Régua de 30 cm e um cartão cinza
- [ ] 12 ou mais bandejas, fita e caneta para etiquetar
- [ ] Duas pessoas que conheçam o padrão de qualidade do comprador
- [ ] Autorização da empresa por escrito para gravar e guardar as imagens

## 2. Fixar a câmera (uma vez por posição)

- [ ] Câmera olhando reto para baixo, esteira ocupando o quadro, ninguém aparecendo
- [ ] Sem sol direto nem reflexo; a luz é a que você trouxe
- [ ] Desligar o automático: exposição, ganho e balanço de branco **fixos à mão**
- [ ] Exposição curta o bastante para a fruta não borrar. Conta de bolso: tempo ≤ 1 mm ÷ velocidade da esteira. Esteira a 250 mm/s pede 1/250 s ou menos
- [ ] Se a imagem ficar escura, aumente a luz. Ganho é o último recurso
- [ ] Balanço de branco acertado no cartão cinza, depois travado
- [ ] A fruta mais clara não pode estourar (ficar branca) na imagem
- [ ] Anotar os três valores: eles entram no comando
- [ ] Régua sobre a esteira: pixels ÷ milímetros = `px/mm` (exemplo: 160 px em 100 mm dá 1,6)
- [ ] Passar 10 frutas de teste com `--preview` e ver se cada uma ganha uma caixa e é contada uma vez

As regras de exposição acima são prática geral de fotografia; nós ainda não as medimos numa esteira.

## 3. Quantas frutas (estimativa para planejar)

Quanto mais frutas, mais estreita a margem de erro da medição. Para um acerto observado de 90%:

| Frutas da classe | Margem de erro (IC 95%) |
|---|---|
| 50 | ± 8,5 pontos |
| 100 | ± 6,0 pontos |
| 200 | ± 4,2 pontos |
| 300 | ± 3,4 pontos |

Para poder afirmar que no máximo 5% das podres passam como boas, é preciso gravar pelo menos 75 podres sem nenhum erro, ou 200 com até 3 erros, ou 300 com até 7.

**Meta:** 300 frutas por classe, em 6 ou mais bandejas por classe, em 3 ou mais dias. **Mínimo para medir alguma coisa:** 2 bandejas por classe. Esses números supõem frutas independentes; frutas da mesma bandeja se parecem, então a margem real é maior. Por isso valem mais bandejas e mais dias do que bandejas cheias.

## 4. Separar e etiquetar as bandejas

| Bandeja | Rótulo | O que entra |
|---|---|---|
| Boa | `boa` | Fruta sã, madura, vendável |
| Baixa qualidade | `baixa_qualidade` | Vendável por menos: imatura, pequena, amassada, rachada, manchada |
| Podre | `podre` | Mofo, podridão, fruta mole ou fermentada |

- [ ] Fruta em que as duas pessoas discordam vai para uma bandeja à parte e **não é gravada**
- [ ] Um nome por bandeja física, escrito na fita: `podre-A`, `boa-B`, `baixa_qualidade-imaturo-A`
- [ ] Anotar o defeito principal de cada bandeja de baixa qualidade no nome
- [ ] Podres e de baixa qualidade são as mais difíceis de juntar: comece por elas

## 5. Gravar (um comando por bandeja)

```powershell
python tools/capture_tray.py --session 2026-10-20-fabrica-a --sector recepcao --tray podre-A --label podre --source 0 --px-per-mm 1.6 --exposure -8 --gain 0 --white-balance 4500 --preview
```

- [ ] Iniciar o comando, despejar a bandeja, parar com `q` ou Ctrl+C quando a última fruta passar
- [ ] Conferir a linha final: quantas frutas e recortes foram gravados
- [ ] No fim do dia: `python tools/capture_tray.py --verify <pasta da sessão>`
- [ ] Copiar a pasta da sessão para um segundo disco antes de sair

O programa recusa a gravação se faltar o rótulo, a sessão, o `px/mm` ou, com câmera ao vivo, a exposição, o ganho e o balanço de branco.

## 6. Não fazer

- Não misturar classes numa bandeja, nem regravar a mesma fruta com outro nome de bandeja
- Não mexer na câmera, na luz ou nos ajustes no meio de uma sessão. Mexeu: sessão nova
- Não deixar exposição, ganho ou balanço de branco no automático
- Não gravar com pessoas no quadro. Apareceu alguém: apague o quadro
- Não escolher só as frutas "fáceis": grave as duvidosas que as duas pessoas classificaram igual
- Não copiar arquivos entre pastas de bandeja, nem editar o `manifest.csv` à mão
- Não publicar nem enviar as imagens: elas são da empresa onde foram gravadas

## 7. Depois, no escritório

```powershell
python tools/eval_real_belt.py <pasta da sessão>
```

Sai o acerto por classe, a matriz de confusão, as podres chamadas de boas e a tabela de corte de confiança, tudo com o número de frutas ao lado. Só depois dessa medição se discute ligar a decisão automática.
