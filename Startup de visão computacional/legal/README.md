# legal/: a fonte única de licenças e créditos

Tudo o que o projeto sabe sobre licenças, créditos e direitos autorais mora aqui. O documento para ler é o [LICENSES.md](../LICENSES.md), na raiz, gerado a partir desta pasta. No site, o mesmo conteúdo é a página **Créditos e licenças**.

Nenhum outro arquivo do projeto repete licença, autor ou crédito. Páginas, guias, fichas de dados e ferramentas apontam para cá.

## O que há aqui

| Arquivo | O que é | Quem escreve |
|---|---|---|
| `registry.json` | O registro: material próprio, fotos e vídeos de terceiros, conjuntos de dados (usados e avaliados e não usados), fontes, bibliotecas de software e as regras de aceitação | Você, à mão. `tools/fetch_media.py` preenche as fotos da Wikimedia Commons |
| `usage.json` | Onde cada item aparece no site e quais arquivos publicados vêm dele | `tools/build_media.py` |
| `site.json` | A versão enxuta que a página Créditos do site carrega | `tools/build_legal.py` |
| `texts/` | Texto completo das licenças que precisam acompanhar o material (fontes) | `tools/build_fonts.py` |
| `reports/` | Relatórios sobre licenças, como a busca de conjuntos de dados e o motivo de cada recusa | À mão |

## Como manter

1. Entrou algo novo de terceiros (foto, vídeo, conjunto de dados, fonte, biblioteca)? Registre em `registry.json`.
2. Se a mídia mudou, rode `python tools/build_media.py`.
3. Rode `python tools/build_legal.py`. Ele reescreve `LICENSES.md` e `site.json`.
4. Rode `python manage.py test core.tests.test_legal`.
5. Reconstrua a interface: `cd frontend; npm run build; cd ..`.

`python tools/build_legal.py --check` não escreve nada: só avisa se os arquivos gerados estão desatualizados ou se alguma biblioteca de `requirements.txt` ou `frontend/package.json` está sem registro.

## O que os testes garantem

`core/tests/test_legal.py`:

- `LICENSES.md` e `site.json` são exatamente o que o gerador produz a partir do registro.
- Toda entrada está completa e a licença de cada mídia e de cada conjunto de dados está na lista aceita.
- Toda biblioteca das listas de dependências tem registro.
- Nenhum arquivo de código, interface, guia, ficha de dados ou legenda cita licença, crédito ou direito autoral fora deste lugar.

`core/tests/test_media.py`:

- Todo arquivo publicado tem registro, e nenhum registro aponta para arquivo que não existe.
- No navegador, nenhuma página além de Créditos mostra texto de licença, e todo selo "Imagem ilustrativa" leva à página Créditos.

## Exceções, e por quê

- **Kit do Summit** (`deliverables/summit_pack/`): o kit sai do repositório sozinho, então leva o próprio `LICENCAS.md` e o crédito no nome das fotos. O arquivo é gerado a partir deste registro por `tools/build_summit_pack.py`.
- **Registros de execuções passadas** (`docs/reports/`, `docs/plans/`, `models/*.json`): são saídas e planos datados, guardados como foram escritos.
- **Dados de terceiros** (`data/`, `datasets/`): o conteúdo baixado não é alterado. As fichas `SOURCE.md` apontam para o `LICENSES.md`.
- **`frontend/package-lock.json`**: arquivo gerado pelo npm.

## Limite honesto

Este registro organiza o que as fontes declaram. Autores e licenças vêm dos metadados publicados por cada fonte; os direitos de quem enviou cada foto não foram verificados de forma independente, e não houve revisão por advogado. A licença do código do próprio FruitCam ainda não foi escolhida pela equipe: até lá o registro diz "todos os direitos reservados", que é a regra padrão.
