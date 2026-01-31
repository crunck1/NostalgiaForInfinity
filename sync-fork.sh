#!/bin/bash

# Script per sincronizzare il fork con l'upstream ogni 2 ore
REPO_DIR="$(dirname "$(realpath "$0")")"  # Directory automatica dello script
LOG_FILE="$REPO_DIR/sync.log"

cd "$REPO_DIR" || exit 1

echo "$(date): Starting sync..." >> "$LOG_FILE"

# Aggiungi upstream se non esiste
if ! git remote | grep -q "upstream"; then
    git remote add upstream https://github.com/iterativv/NostalgiaForInfinity.git
    echo "$(date): Added upstream remote" >> "$LOG_FILE"
fi

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
        git push origin custom-can-short-disable --force-with-lease >> "$LOG_FILE" 2>&1

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
