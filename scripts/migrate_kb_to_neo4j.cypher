// =============================================================
// BRIDGR — kb.json → Neo4j Migration
// Stand: 2026-06-11
// Generiert aus knowledge_base/kb.json
//
// Ausführen über Neo4j Desktop oder cypher-shell.
// Jedes Statement einzeln ausführen oder alle auf einmal.
// =============================================================


// -------------------------------------------------------------
// 1. DIENT-Kanten: raw_name + source setzen (confirmed)
//    Kritisch: get_confirmed_links_from_neo4j() filtert auf
//    r.raw_name IS NOT NULL — ohne diese Properties werden die
//    bestätigten Links beim nächsten Import nicht erkannt.
// -------------------------------------------------------------

MERGE (p:Prozess {name: 'Angebotserstellung'})
MERGE (a:Anwendung {cmdb_id: 'app-006'})
ON CREATE SET a.name = 'SAP SRM', a.id = 'app-006'
MERGE (a)-[r:DIENT]->(p)
SET r.konfidenz = 'stark', r.raw_name = 'SAP CRM', r.source = 'manuell_bestaetigt';

MERGE (p:Prozess {name: 'Auftragserfassung'})
MERGE (a:Anwendung {cmdb_id: 'app-006'})
ON CREATE SET a.name = 'SAP SRM', a.id = 'app-006'
MERGE (a)-[r:DIENT]->(p)
SET r.konfidenz = 'stark', r.raw_name = 'SAP CRM', r.source = 'manuell_bestaetigt';

MERGE (p:Prozess {name: 'Reklamationsbearbeitung'})
MERGE (a:Anwendung {cmdb_id: 'app-006'})
ON CREATE SET a.name = 'SAP SRM', a.id = 'app-006'
MERGE (a)-[r:DIENT]->(p)
SET r.konfidenz = 'stark', r.raw_name = 'SAP CRM', r.source = 'manuell_bestaetigt';

MERGE (p:Prozess {name: 'Kundenanlage und -pflege'})
MERGE (a:Anwendung {cmdb_id: 'app-006'})
ON CREATE SET a.name = 'SAP SRM', a.id = 'app-006'
MERGE (a)-[r:DIENT]->(p)
SET r.konfidenz = 'stark', r.raw_name = 'SAP CRM', r.source = 'manuell_bestaetigt';

MERGE (p:Prozess {name: 'Berichtswesen'})
MERGE (a:Anwendung {cmdb_id: '7104519e-2f7d-4a6e-a54f-6fb6b76ed5c2'})
ON CREATE SET a.name = 'SAP WM', a.id = '7104519e-2f7d-4a6e-a54f-6fb6b76ed5c2'
MERGE (a)-[r:DIENT]->(p)
SET r.konfidenz = 'stark', r.raw_name = 'SAP BW', r.source = 'manuell_bestaetigt';

MERGE (p:Prozess {name: 'IT-Support'})
MERGE (a:Anwendung {cmdb_id: 'app-004'})
ON CREATE SET a.name = 'Jira Service Management', a.id = 'app-004'
MERGE (a)-[r:DIENT]->(p)
SET r.konfidenz = 'stark', r.raw_name = 'JIRA', r.source = 'manuell_bestaetigt';

MERGE (p:Prozess {name: 'Softwarefreigabe'})
MERGE (a:Anwendung {cmdb_id: 'app-004'})
ON CREATE SET a.name = 'Jira Service Management', a.id = 'app-004'
MERGE (a)-[r:DIENT]->(p)
SET r.konfidenz = 'stark', r.raw_name = 'JIRA', r.source = 'manuell_bestaetigt';

MERGE (p:Prozess {name: 'Jahresabschluss'})
MERGE (a:Anwendung {cmdb_id: '7104519e-2f7d-4a6e-a54f-6fb6b76ed5c2'})
ON CREATE SET a.name = 'SAP WM', a.id = '7104519e-2f7d-4a6e-a54f-6fb6b76ed5c2'
MERGE (a)-[r:DIENT]->(p)
SET r.konfidenz = 'stark', r.raw_name = 'SAP BW', r.source = 'manuell_bestaetigt';

MERGE (p:Prozess {name: 'Budgetplanung'})
MERGE (a:Anwendung {cmdb_id: '7104519e-2f7d-4a6e-a54f-6fb6b76ed5c2'})
ON CREATE SET a.name = 'SAP WM', a.id = '7104519e-2f7d-4a6e-a54f-6fb6b76ed5c2'
MERGE (a)-[r:DIENT]->(p)
SET r.konfidenz = 'stark', r.raw_name = 'SAP BW', r.source = 'manuell_bestaetigt';

MERGE (p:Prozess {name: 'Änderungsmanagement'})
MERGE (a:Anwendung {cmdb_id: 'app-004'})
ON CREATE SET a.name = 'Jira Service Management', a.id = 'app-004'
MERGE (a)-[r:DIENT]->(p)
SET r.konfidenz = 'stark', r.raw_name = 'JIRA', r.source = 'manuell_bestaetigt';

MERGE (p:Prozess {name: 'Auftragserfassung (Detail)'})
MERGE (a:Anwendung {cmdb_id: 'app-006'})
ON CREATE SET a.name = 'SAP SRM', a.id = 'app-006'
MERGE (a)-[r:DIENT]->(p)
SET r.konfidenz = 'stark', r.raw_name = 'SAP CRM', r.source = 'manuell_bestaetigt';


// -------------------------------------------------------------
// 2. Ablehnungen (rejected — aktuell leer in kb.json)
//    Keine Statements nötig.
// -------------------------------------------------------------


// -------------------------------------------------------------
// 3. Verifikation: zeigt alle DIENT-Kanten mit raw_name
//    (sollten nach der Migration 11 Einträge sein)
// -------------------------------------------------------------

MATCH (a:Anwendung)-[r:DIENT]->(p:Prozess)
WHERE r.raw_name IS NOT NULL
RETURN p.name AS prozess, r.raw_name AS anwendung_roh, a.name AS anwendung_cmdb,
       a.cmdb_id AS cmdb_id, r.source AS quelle
ORDER BY p.name;
