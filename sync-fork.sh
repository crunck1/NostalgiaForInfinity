#!/bin/bash

# Script per sincronizzare il fork con l'upstream ogni 2 ore
REPO_DIR="$(dirname "$(realpath "$0")")"  # Directory automatica dello script
LOG_FILE="$REPO_DIR/sync.log"
CONTAINER_NAME="Example_live_bybit_futures-NostalgiaForInfinityX7"  # Nome del container Docker

# Carica credenziali API dal file .env
if [ -f "$REPO_DIR/.env" ]; then
    API_PORT=$(grep "^FREQTRADE__API_SERVER__LISTEN_PORT=" "$REPO_DIR/.env" | cut -d'=' -f2)
    API_USER=$(grep "^FREQTRADE__API_SERVER__USERNAME=" "$REPO_DIR/.env" | cut -d'=' -f2)
    API_PASS=$(grep "^FREQTRADE__API_SERVER__PASSWORD=" "$REPO_DIR/.env" | cut -d'=' -f2)
else
    echo "$(date): ERROR - .env file not found, cannot reload bot" >> "$LOG_FILE"
    API_PORT="8080"
    API_USER=""
    API_PASS=""
fi

cd "$REPO_DIR" || exit 1

echo "$(date): Starting sync..." >> "$LOG_FILE"

# Aggiungi upstream se non esiste
if ! git remote | grep -q "upstream"; then
    git remote add upstream https://github.com/iterativv/NostalgiaForInfinity.git
    echo "$(date): Added upstream remote" >> "$LOG_FILE"
fi

# Scegli il remote per il push del branch custom
CUSTOM_REMOTE="origin"
if git remote | grep -q "^myfork$"; then
    CUSTOM_REMOTE="myfork"
fi
echo "$(date): Using remote '$CUSTOM_REMOTE' for custom branch push" >> "$LOG_FILE"

# Fetch delle modifiche upstream
git fetch upstream >> "$LOG_FILE" 2>&1

# Torna al main branch
git checkout main >> "$LOG_FILE" 2>&1

# Merge delle modifiche upstream
git merge upstream/main --no-edit >> "$LOG_FILE" 2>&1

# Push al tuo fork
git push origin main >> "$LOG_FILE" 2>&1

# Prova a fare rebase del branch personalizzato
if git checkout custom-can-short-disable >> "$LOG_FILE" 2>&1; then
    # Controlla se ci sono modifiche locali
    if ! git diff-index --quiet HEAD --; then
        echo "$(date): Found local changes, stashing them" >> "$LOG_FILE"
        git stash push -m "Auto-stash before sync rebase $(date)" >> "$LOG_FILE" 2>&1
        STASHED=1
    else
        STASHED=0
    fi

    if git rebase main >> "$LOG_FILE" 2>&1; then
        echo "$(date): ✅ Custom branch rebased successfully" >> "$LOG_FILE"
        git fetch "$CUSTOM_REMOTE" >> "$LOG_FILE" 2>&1  # Aggiorna riferimenti prima del push
        if git push "$CUSTOM_REMOTE" custom-can-short-disable --force-with-lease >> "$LOG_FILE" 2>&1; then
            echo "$(date): ✅ Custom branch pushed to $CUSTOM_REMOTE" >> "$LOG_FILE"
        else
            echo "$(date): ⚠️  Push failed on $CUSTOM_REMOTE" >> "$LOG_FILE"
        fi

        # Ripristina le modifiche locali se erano state salvate
        if [ "$STASHED" -eq 1 ]; then
            echo "$(date): Restoring stashed changes" >> "$LOG_FILE"
            git stash pop >> "$LOG_FILE" 2>&1
        fi
    else
        echo "$(date): ❌ Rebase failed - manual intervention needed" >> "$LOG_FILE"
        git rebase --abort >> "$LOG_FILE" 2>&1

        # Ripristina le modifiche locali se erano state salvate
        if [ "$STASHED" -eq 1 ]; then
            echo "$(date): Restoring stashed changes after failed rebase" >> "$LOG_FILE"
            git stash pop >> "$LOG_FILE" 2>&1
        fi

        # Manda una notifica via email o telegram se configurato
        echo "SYNC CONFLICT: Manual merge required for custom-can-short-disable branch" | mail -s "NFI Sync Alert" tuo-email@example.com 2>/dev/null || true
    fi
fi

echo "$(date): Sync completed" >> "$LOG_FILE"

# Reload strategia se il bot Freqtrade è in esecuzione
echo "$(date): Checking for running Freqtrade container..." >> "$LOG_FILE"

if docker ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$" 2>/dev/null; then
    echo "$(date): Found running Docker container: $CONTAINER_NAME" >> "$LOG_FILE"
    echo "$(date): Sending reload_config via REST API..." >> "$LOG_FILE"

    RELOAD_RESPONSE=$(docker exec "$CONTAINER_NAME" curl -s -X POST "http://localhost:${API_PORT}/api/v1/reload_config" -u "${API_USER}:${API_PASS}" 2>&1)

    if [ $? -eq 0 ]; then
        echo "$(date): ✅ Strategy reload successful: $RELOAD_RESPONSE" >> "$LOG_FILE"
    else
        echo "$(date): ⚠️  REST API reload failed: $RELOAD_RESPONSE" >> "$LOG_FILE"
        echo "$(date): Attempting docker restart as fallback..." >> "$LOG_FILE"
        docker restart "$CONTAINER_NAME" >> "$LOG_FILE" 2>&1
        echo "$(date): ✅ Container restarted" >> "$LOG_FILE"
    fi
else
    echo "$(date): Container $CONTAINER_NAME not running - skipping reload" >> "$LOG_FILE"
fi

echo "$(date): Sync and reload completed" >> "$LOG_FILE"
