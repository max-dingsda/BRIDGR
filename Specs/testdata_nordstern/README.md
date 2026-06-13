# BRIDGR Testdaten: Nordstern Werke GmbH

Fiktiver Datensatz fuer Last- und Matching-Tests.

## Dateien

- `cmdb_entities.csv`: 140 CMDB-Objekte, darunter Anwendungen, Schnittstellen und Server.
- `cmdb_relations.csv`: technische Beziehungen `RUNS_ON` und `USES_INTERFACE`.
- `process_inventory.csv`: Uebersicht ueber 55 fachliche Prozesse.
- `processes_txt/`: 55 Prozessbeschreibungen als TXT.
- `processes_bpmn/`: 6 BPMN-Beispiele mit Lanes fuer Organisationseinheit und Rolle.

## Bewusste Testfaelle

Einige Prozesse nennen Anwendungen anders als die CMDB, zum Beispiel:

- `SAP FI` -> `SAP S/4HANA FI`
- `SAP CO` -> `SAP S/4HANA CO`
- `CRM` / `Dynamics CRM` -> `Microsoft Dynamics CRM`
- `AD` -> `Active Directory Domain Services`
- `WMS` -> `WarehousePro WMS`
- `MES` -> `MES FactoryLine`
- `PlantView` -> `SCADA PlantView`
- `PowerBI` -> `Power BI Service`

Weitere Testfaelle:

- Prozesse ohne Owner: `PROC-047`, `PROC-049`, `PROC-052`
- Prozesse ohne explizite Anwendungsunterstuetzung: `PROC-044`, `PROC-045`, `PROC-048`
- Technische, fachlich nicht direkt sichtbare Bausteine in der CMDB: AD, Entra ID, Firewall Management, VPN, DNS, SMTP, PKI, Backup, Monitoring, SIEM.

Empfohlene Nutzung: Dateien nach `Input/` kopieren und `cmdb_filename` auf `cmdb_entities.csv` setzen.
