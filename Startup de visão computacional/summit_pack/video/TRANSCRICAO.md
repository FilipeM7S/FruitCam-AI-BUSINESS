# Transcrição do vídeo de demonstração

`demo.mp4` / `demo.webm`: 1280×720 px, 40.2 s, sem áudio. Legendas em `demo.vtt` (pt-BR).

Gravação do app real em execução (40 s, sem áudio). A câmera e os dados da linha são simulados e sintéticos; a foto da inspeção é real (CC0) e o resultado é a saída real do modelo.

- **00:00.000** Login do FruitCam_ai. Ao fundo, vídeo ilustrativo de uma esteira de seleção (USDA, domínio público).
- **00:06.250** Página Linha: a câmera fixa sobre a esteira conta e classifica cada fruta. Ao fundo, a simulação processada pelo mesmo código.
- **00:09.232** Linha ao vivo: quadro da câmera simulada, frutas por minuto e porcentagem de cada classe com intervalo de confiança. Dados sintéticos.
- **00:15.445** Carta de controle da % de podres, alarmes e aceite de cada lote pelo intervalo de confiança.
- **00:21.054** Como a câmera funciona: separa a fruta da esteira, segue a fruta entre quadros, classifica com IA e conta uma vez na linha tracejada.
- **00:26.843** O botão ? abre o guia do usuário em qualquer página.
- **00:30.045** Inspeção por foto: uma foto real de caju (Wilfredor, CC0) passa pelo mesmo classificador de três classes.
- **00:35.927** Saída real do modelo: boa, confiança 69,4%, sem confiança suficiente para decidir sozinho: vai para revisão manual. A foto tem folhas ao fundo, diferente da esteira.

`pipeline.mp4` / `pipeline.gif`: animação das 7 etapas do caminho de uma foto, gravada da página Como funciona (sem dados).
