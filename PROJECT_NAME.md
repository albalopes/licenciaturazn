# Identificação do projeto

O nome de referência deste projeto é **licenciaturazn**.

- Projeto/Stack Docker Compose: `licenciaturazn`
- Container da aplicação: `licenciaturazn_web`
- Banco de dados padrão: `licenciaturazn`
- Pacote Python interno: `app` (mantido assim para não quebrar os imports da aplicação)
- Porta interna: `5003`

No Nginx Proxy Manager, use o container `licenciaturazn_web` e a porta `5003` pela `proxy_network`.
