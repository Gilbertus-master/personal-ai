Zadanie: M6 — Secrets scanning gitleaks pre-commit hook.

REPO: /home/sebastian/personal-ai

IMPLEMENTACJA:
1. Sprawdź czy gitleaks jest zainstalowany:
   which gitleaks || echo "NOT INSTALLED"

   Jeśli nie ma: pomiń instalację binarki, stwórz skrypt który używa Dockera:

2. Utwórz .gitleaks.toml:

[extend]
useDefault = true

[[rules]]
description = "Anthropic API Key"
regex = '''sk-ant-[a-zA-Z0-9\-_]{93}'''
id = "anthropic-api-key"

[[rules]]
description = "Polish Phone Number"
regex = '''\+48\d{9}'''
id = "polish-phone"
[rules.allowlist]
regexes = ["WA_TARGET", "AUTHORIZED_WA_SENDERS", "# example", "# Config"]

[allowlist]
paths = [".env.example", "*.md", "logs/", "data/"]

3. Utwórz .git/hooks/pre-commit:

#!/bin/bash
# Gitleaks secret scanner pre-commit hook

REPO_ROOT=$(git rev-parse --show-toplevel)

if command -v gitleaks &>/dev/null; then
    gitleaks detect --source="$REPO_ROOT" --config="$REPO_ROOT/.gitleaks.toml" \
        --redact --no-git --quiet 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "❌ gitleaks: potencjalne sekrety wykryte! Sprawdź output powyżej."
        echo "  Użyj 'git diff --cached' żeby zobaczyć co committujesz."
        exit 1
    fi
elif command -v docker &>/dev/null; then
    docker run --rm -v "$REPO_ROOT:/repo" \
        zricethezav/gitleaks:latest detect \
        --source="/repo" --config="/repo/.gitleaks.toml" \
        --redact --no-git --quiet 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "❌ gitleaks (docker): potencjalne sekrety wykryte!"
        exit 1
    fi
else
    echo "⚠️ gitleaks nie zainstalowany — skanowanie pominięte"
fi

exit 0

4. chmod +x .git/hooks/pre-commit

WERYFIKACJA:
bash .git/hooks/pre-commit && echo "pre-commit hook OK"
