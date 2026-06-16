# Annahmen fuer das Nordstern-Archimate-Modell

Dieses Dokument haelt die bei der Modellgenerierung getroffenen Annahmen fest.

- Die Dateien `nordstern_archimate_3_1.xml` und `nordstern_archimate_archi_compatible_3_0.xml` beschreiben dasselbe Modell; sie unterscheiden sich nur im ArchiMate-Namespace fuer Standard- versus Tool-Kompatibilitaet.
- Application 'SAP PP' was modeled as a standalone ApplicationComponent because no CMDB entity matched it.
- BusinessActor elements represent organizational units from process owners, departments, and CMDB owner fields.
- CMDB relation RUNS_ON is represented as Realization from ApplicationComponent to Node.
- CMDB relation USES_INTERFACE is represented as Composition from ApplicationComponent to ApplicationInterface to remain compatible with the current BRIDGR ArchiMate mapping.
- Capabilities are modeled generically per department cluster rather than per individual process.
- Missing process owners fall back to the process department for BusinessActor ownership assignment.
- Servers are modeled uniformly as Node elements to keep the technology layer simple and BRIDGR-friendly.
- The motivation layer is intentionally generic and supplements the test dataset because these concepts are not directly extractable from the source files.
