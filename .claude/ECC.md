# Piezas de Everything Claude Code (ECC)

Origen: https://github.com/affaan-m/ECC — commit `ef648e0` (versión 2.2.3), licencia MIT (ver `ECC-LICENSE`).
Solo se copia una selección; no está instalado el plugin completo ni sus hooks.

- Reglas (`rules/ecc/`): common/coding-style, common/patterns, common/security y python/{coding-style, fastapi, patterns, security, testing}.
- Skills (`skills/`): fastapi-patterns, postgres-patterns, python-patterns, python-testing, tdd-workflow, security-review, api-design.
- Agentes (`agents/`): fastapi-reviewer, python-reviewer, database-reviewer, security-reviewer. Se usan solo bajo petición (se quitaron los "MUST BE USED"/"use PROACTIVELY" de sus descripciones).
- Extra (proyecto clínico): agente `healthcare-reviewer` y skill `scientific-thinking-literature-review`.

Se dejaron fuera a propósito: reglas de agents/hooks/development-workflow/testing/code-review/performance de `common`
(obligan a planificación formal, 80% de cobertura y tests E2E, o dependen de agentes del plugin completo).

Para actualizar: volver a copiar estas carpetas desde una versión nueva de ECC y revisar los cambios con `git diff`.
