#!/bin/bash

# Script per sincronizzare il fork con l'upstream ogni 2 ore
# Approccio: sync main da upstream, rebase + squash del branch custom su main
#
REPO_DIR="$(dirname "$(realpath "$0")")"  # Directory automatica dello script
LOG_FILE="$REPO_DIR/sync.log"
CUSTOM_BRANCH="custom-can-short-disable"
SQUASH_MSG="Custom changes: NFI_CAN_SHORT env variable, sync scripts, pairlist updates, config"

# Carica variabili dal file .env (stesse usate da docker-compose.yml)
if [ -f "$REPO_DIR/.env" ]; then
    BOT_NAME=$(grep "^FREQTRADE__BOT_NAME=" "$REPO_DIR/.env" | cut -d'=' -f2)
    EXCHANGE_NAME=$(grep "^FREQTRADE__EXCHANGE__NAME=" "$REPO_DIR/.env" | cut -d'=' -f2)
    TRADING_MODE=$(grep "^FREQTRADE__TRADING_MODE=" "$REPO_DIR/.env" | cut -d'=' -f2)
    STRATEGY=$(grep "^FREQTRADE__STRATEGY=" "$REPO_DIR/.env" | cut -d'=' -f2)
    API_PORT=$(grep "^FREQTRADE__API_SERVER__LISTEN_PORT=" "$REPO_DIR/.env" | cut -d'=' -f2)
    API_USER=$(grep "^FREQTRADE__API_SERVER__USERNAME=" "$REPO_DIR/.env" | cut -d'=' -f2)
    API_PASS=$(grep "^FREQTRADE__API_SERVER__PASSWORD=" "$REPO_DIR/.env" | cut -d'=' -f2)
else
    echo "$(date): ERROR - .env file not found, cannot reload bot" >> "$LOG_FILE"
    API_PORT="8080"
    API_USER=""
    API_PASS=""
fi

# Costruisci il nome del container con la stessa logica di docker-compose.yml
CONTAINER_NAME="${BOT_NAME:-Example_Test_Account}_${EXCHANGE_NAME:-binance}_${TRADING_MODE:-futures}-${STRATEGY:-NostalgiaForInfinityX7}"

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

# Fetch di upstream e del remote custom
git fetch upstream >> "$LOG_FILE" 2>&1
git fetch "$CUSTOM_REMOTE" >> "$LOG_FILE" 2>&1

# --- SYNC MAIN ---
git checkout main >> "$LOG_FILE" 2>&1

# Controlla se main ha nuovi commit da upstream
MAIN_BEHIND=$(git rev-list --count main..upstream/main 2>/dev/null)
if [ "$MAIN_BEHIND" -eq 0 ] 2>/dev/null; then
    echo "$(date): Main is already up to date with upstream - no changes" >> "$LOG_FILE"
    MAIN_CHANGED=0
else
    echo "$(date): Main is $MAIN_BEHIND commits behind upstream - syncing..." >> "$LOG_FILE"
    git merge upstream/main --no-edit >> "$LOG_FILE" 2>&1
    git push origin main >> "$LOG_FILE" 2>&1
    MAIN_CHANGED=1
fi

# --- SYNC CUSTOM BRANCH ---
if git checkout "$CUSTOM_BRANCH" >> "$LOG_FILE" 2>&1; then

    # Salta il rebase se main non è cambiato
    if [ "$MAIN_CHANGED" -eq 0 ]; then
        echo "$(date): ⏭️  No upstream changes - skipping rebase of $CUSTOM_BRANCH" >> "$LOG_FILE"
    else
        # Controlla se ci sono modifiche locali
        if ! git diff-index --quiet HEAD --; then
            echo "$(date): Found local changes, stashing them" >> "$LOG_FILE"
            git stash push -m "Auto-stash before sync rebase $(date)" >> "$LOG_FILE" 2>&1
            STASHED=1
        else
            STASHED=0
        fi

        # Salva il diff corrente rispetto a main (per verifica post-rebase)
        DIFF_BEFORE=$(git diff main --stat 2>/dev/null | tail -1)

        # Primo tentativo: rebase normale
        if git rebase main >> "$LOG_FILE" 2>&1; then
            echo "$(date): ✅ Custom branch rebased successfully" >> "$LOG_FILE"
        else
            echo "$(date): ⚠️  Normal rebase failed, retrying with auto-resolve (keep custom changes)..." >> "$LOG_FILE"
            git rebase --abort >> "$LOG_FILE" 2>&1

            # Secondo tentativo: rebase con auto-resolve (privilegia le modifiche custom)
            if git rebase -X theirs main >> "$LOG_FILE" 2>&1; then
                echo "$(date): ✅ Custom branch rebased with auto-resolved conflicts" >> "$LOG_FILE"
            else
                echo "$(date): ❌ Rebase failed even with auto-resolve - manual intervention needed" >> "$LOG_FILE"
                git rebase --abort >> "$LOG_FILE" 2>&1

                if [ "$STASHED" -eq 1 ]; then
                    echo "$(date): Restoring stashed changes after failed rebase" >> "$LOG_FILE"
                    git stash pop >> "$LOG_FILE" 2>&1
                fi

                echo "SYNC CONFLICT: Manual merge required for $CUSTOM_BRANCH branch" | mail -s "NFI Sync Alert" tuo-email@example.com 2>/dev/null || true

                git checkout main >> "$LOG_FILE" 2>&1
                echo "$(date): Returned to main branch after failure" >> "$LOG_FILE"
                echo "$(date): Sync completed with errors" >> "$LOG_FILE"
                exit 1
            fi
        fi

        # --- SQUASH: comprimi tutti i commit custom in uno singolo ---
        # Questo previene l'accumulo di commit duplicati ad ogni ciclo di rebase
        CUSTOM_COMMITS=$(git rev-list --count main.."$CUSTOM_BRANCH" 2>/dev/null)
        if [ "$CUSTOM_COMMITS" -gt 1 ]; then
            echo "$(date): Squashing $CUSTOM_COMMITS custom commits into one..." >> "$LOG_FILE"
            git reset --soft main >> "$LOG_FILE" 2>&1
            git commit -m "$SQUASH_MSG" >> "$LOG_FILE" 2>&1
            echo "$(date): ✅ Squashed into single commit" >> "$LOG_FILE"
        fi

        # Verifica che le modifiche custom siano ancora presenti
        DIFF_AFTER=$(git diff main --stat 2>/dev/null | tail -1)
        if [ -z "$(git diff main --name-only 2>/dev/null)" ]; then
            echo "$(date): ❌ WARNING: Custom branch has no differences from main after rebase!" >> "$LOG_FILE"
            echo "$(date): This means custom changes may have been lost" >> "$LOG_FILE"
        else
            echo "$(date): ✅ Custom changes verified (diff: $DIFF_AFTER)" >> "$LOG_FILE"
        fi

        # Push del branch custom
        if git push "$CUSTOM_REMOTE" "$CUSTOM_BRANCH" --force >> "$LOG_FILE" 2>&1; then
            echo "$(date): ✅ Custom branch pushed to $CUSTOM_REMOTE" >> "$LOG_FILE"
        else
            echo "$(date): ❌ Push failed on $CUSTOM_REMOTE" >> "$LOG_FILE"
        fi

        # Ripristina le modifiche locali se erano state salvate
        if [ "$STASHED" -eq 1 ]; then
            echo "$(date): Restoring stashed changes" >> "$LOG_FILE"
            git stash pop >> "$LOG_FILE" 2>&1
        fi
    fi
fi

echo "$(date): Sync completed" >> "$LOG_FILE"

# Reload strategia se il bot Freqtrade è in esecuzione (solo se c'erano cambiamenti)
echo "$(date): Checking for running Freqtrade container..." >> "$LOG_FILE"

if [ "$MAIN_CHANGED" -eq 0 ]; then
    echo "$(date): No changes to reload - skipping container restart" >> "$LOG_FILE"
elif docker ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$" 2>/dev/null; then
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
