# TBC Knowledge Base V1

Repositorio inicial para construir la base científica del TBC Assistant.

## Estado de esta entrega
- Estructura de carpetas creada.
- `bibliography.csv` y `bibliography.json` creados.
- Primera carga de guías oficiales y artículos científicos verificados.
- Catálogo RAG inicial.
- Semilla de preguntas de pacientes.
- Plantilla de evaluación creada.

## Regla de evidencia
1. Priorizar guías clínicas vigentes (WHO, ATS/CDC/ERS/IDSA, CDC).
2. Después, revisiones sistemáticas/metaanálisis y ensayos clínicos.
3. Utilizar estudios observacionales para cuestiones específicas de seguridad, frecuencia y práctica real.
4. No usar el conocimiento interno del LLM para completar información clínica ausente en las fuentes recuperadas.

## Derechos de autor
Este repositorio NO incluye PDFs sujetos a copyright. Los registros contienen metadatos y enlaces oficiales.
Los textos completos solo deben incorporarse si:
- son de acceso abierto y su licencia permite el uso previsto, o
- se dispone de acceso institucional y el uso local cumple la licencia correspondiente.

## Próximas ampliaciones
- Enriquecer DOI, autores y revista de registros incompletos.
- Añadir bloques de hepatotoxicidad, neuropatía, QT/cardiotoxicidad, toxicidad hematológica e interacciones.
- Añadir artículos de embarazo, pediatría, VIH, insuficiencia renal/hepática y adherencia.
- Deduplicar por PMID, DOI y título normalizado.
- Añadir campos de Scopus/WoS/CINAHL/JCR/SJR únicamente cuando hayan sido comprobados en esas fuentes.


## V2 — Hepatotoxicidad
- Se añadieron 11 referencias verificadas centradas en AT-DILI, isoniazida, rifampicina y pirazinamida.
- Se creó `adverse_effects/hepatotoxicity/hepatotoxicity_rag.json`.
- Se añadieron fichas RAG específicas para isoniazida, rifampicina y pirazinamida.
- Se añadieron preguntas de paciente sobre ictericia, transaminasas, orina oscura, reintroducción tras DILI, alcohol y enfermedad hepática crónica.
- Total actual de registros bibliográficos: 30.


## V3 — Neuropatía / isoniazida / linezolid / cicloserina / piridoxina
- Se añadieron 11 referencias verificadas.
- Se creó `adverse_effects/neuropathy/neuropathy_rag.json`.
- Se añadieron fichas RAG para isoniazida, linezolid, cicloserina/terizidona y piridoxina.
- Se añadieron reglas específicas para diferenciar neuropatía periférica, neuropatía óptica y toxicidad neuropsiquiátrica.
- Se añadieron preguntas de pacientes sobre hormigueo, B6, linezolid, alteraciones visuales y síntomas psiquiátricos.
- Total actual de registros bibliográficos: 41.


## V4 — Toxicidad hematológica por linezolid
- Se añadieron 7 registros verificados: 1 guía/annex WHO y 6 artículos.
- Se creó `adverse_effects/hematologic/linezolid_myelosuppression_rag.json`.
- Se separaron anemia, trombocitopenia y neutropenia en fichas RAG independientes.
- Se actualizó `drugs/linezolid/linezolid_rag.json` con monitorización hematológica.
- Se añadieron 8 preguntas nuevas de pacientes.
- Se añadieron casos de seguridad específicos para hemograma y BPaL/BPaLM.
- Total actual de registros bibliográficos: 48.
- Total actual de preguntas semilla: 29.


## V5 — QT/cardiotoxicidad
- Se añadieron 9 registros verificados: 2 fuentes WHO y 7 artículos.
- Se creó `adverse_effects/QT_cardiotoxicity/qt_cardiotoxicity_rag.json`.
- Se añadieron fichas RAG para bedaquilina, moxifloxacino, clofazimina y delamanid.
- Se añadieron reglas para ECG, QTcF, electrolitos, síncope, palpitaciones y combinaciones de fármacos que prolongan QT.
- Se añadieron 10 preguntas nuevas de pacientes.
- Se añadieron 5 casos de evaluación de seguridad cardíaca.
- Total actual de registros bibliográficos: 57.
- Total actual de preguntas semilla: 39.


## V6 — Toxicidad ocular (integrada en esta versión acumulativa)
- Se añadieron fuentes WHO y artículos sobre etambutol/linezolid.
- Se creó `adverse_effects/optic_toxicity/optic_toxicity_rag.json`.
- Se añadieron reglas para agudeza visual, discriminación rojo-verde y derivación oftalmológica.

## V7 — Interacciones farmacológicas
- Se añadieron fuentes WHO/CDC y artículos sobre rifamicinas, anticoagulantes, anticonceptivos, ART y linezolid-serotonérgicos.
- Se creó `interactions/drug_interactions_rag.json`.
- Se añadieron preguntas de pacientes y casos de seguridad específicos.
- Total actual de registros bibliográficos: 69.
- Total actual de preguntas semilla: 49.


## V8 — Insuficiencia renal y hemodiálisis
- Se añadieron 6 registros: 4 fuentes actuales WHO/CDC, 1 estudio reciente de levofloxacino y 1 estudio PK fundacional de hemodiálisis.
- Se creó `special_populations/renal_failure/renal_failure_rag.json`.
- Se añadieron fichas renales para pirazinamida, etambutol, levofloxacino, cicloserina, amikacina y estreptomicina.
- Se añadieron 9 preguntas de pacientes y 5 casos de evaluación de seguridad.
- Total actual de registros bibliográficos: 75.
- Total actual de preguntas semilla: 58.

Nota metodológica: TB-A055 (1999) queda fuera de la ventana principal 2016–2026, pero se conserva como evidencia farmacocinética fundacional citada por guías; debe etiquetarse como 'legacy/foundational' y no contar para el objetivo de >=500 artículos de los últimos 10 años.


## V9 — Embarazo, lactancia y fertilidad
- Se añadieron 4 registros verificados: 3 fuentes CDC/WHO y 1 artículo clínico 2025 con PMID/PMCID/DOI.
- Se creó `special_populations/pregnancy/pregnancy_lactation_rag.json`.
- Se separaron lactancia y fertilidad/anticoncepción.
- Se añadieron fichas reproductivas para isoniazida, rifampicina, pirazinamida, rifapentina, bedaquilina, pretomanid y linezolid.
- Se incorporó explícitamente la discrepancia de enfoque sobre pirazinamida en embarazo para evitar respuestas falsas de tipo universal.
- Se añadieron 10 preguntas nuevas de pacientes y 6 casos de seguridad.
- Total actual de registros bibliográficos: 79.
- Total actual de preguntas semilla: 68.
