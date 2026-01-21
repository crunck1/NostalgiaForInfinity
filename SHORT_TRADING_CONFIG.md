## Configurazione per disabilitare il Short Trading in NostalgiaForInfinityX7

Ho implementato una soluzione per controllare la funzionalità di short trading tramite variabile d'ambiente.

### Cosa ho modificato:

1. **File `.env`**: Aggiunta della variabile `NFI_CAN_SHORT=false`
2. **File `NostalgiaForInfinityX7.py`**: Modificata la logica di inizializzazione per supportare il controllo tramite variabile d'ambiente

### Come funziona:

La strategia controlla la variabile d'ambiente `NFI_CAN_SHORT` durante l'inizializzazione:
- `false`, `0`, `no`, `off`: Disabilita il short trading
- `true`, `1`, `yes`, `on`: Abilita il short trading
- Se non impostata: Utilizza il comportamento predefinito (abilita short se in modalità futures/margin)

### Utilizzo:

#### Con Docker (come configurato ora):
Il file `.env` contiene già:
```bash
NFI_CAN_SHORT=false
```

Basta eseguire:
```bash
docker compose up
```

#### Per abilitare/disabilitare lo shorting:

**Disabilitare:**
```bash
NFI_CAN_SHORT=false
```

**Abilitare:**
```bash
NFI_CAN_SHORT=true
```

#### Controllo tramite parametri di configurazione:
È possibile anche controllare tramite il parametro `can_short_override` nella configurazione:
```json
{
  "nfi_parameters": {
    "can_short_override": false
  }
}
```

### Log di conferma:
Quando la strategia viene avviata, vedrai nei log uno di questi messaggi:
- `"Short functionality disabled via NFI_CAN_SHORT environment variable."`
- `"Short functionality enabled via NFI_CAN_SHORT environment variable."`
- `"Short functionality set to {value} via can_short_override parameter."`

### Note:
- La variabile d'ambiente ha precedenza sul comportamento predefinito
- Il parametro `can_short_override` ha precedenza sulla variabile d'ambiente
- Quando `can_short = False`, tutte le condizioni di short entry vengono ignorate
- Il cambio richiede un riavvio del container Docker per essere applicato