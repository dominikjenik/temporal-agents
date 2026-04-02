# opencode konfigurácia pre temporal-agentic-workflow

## Start/Stop
- `./start.sh` a `./stop.sh` blokujú CLI - vždy spúšťať s `nohup ./start.sh &` alebo v samostatnom termináli

## .env
- `TEMPORAL_RUNNER=opencode` - nahradzuje platený claude CLI

## API
- Jeden endpoint `/request` pre chat, query aj dispatch
