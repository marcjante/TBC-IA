import json

faq = json.load(open('evaluation_faq_2026-08-16_2240.json'))
banco = json.load(open('evaluation_patient_bank_2026-08-16_2240.json'))

print('=== GUIAS - Categoria 2. Contagio (11 sin cobertura) ===')
for r in faq:
    if r.get('classification_auto') == 'sin_cobertura' and r.get('categoria') == '2. Contagio':
        print(' -', r.get('pregunta'))

print()
print('=== GUIAS - 22. Preguntas frecuentes sobre la medicacion (8 sin cobertura) ===')
for r in faq:
    if r.get('classification_auto') == 'sin_cobertura' and r.get('categoria') == '22. Preguntas frecuentes sobre la medicacion':
        print(' -', r.get('pregunta'))

print()
print('=== PACIENTES - 3. Medicacion (22 sin cobertura) ===')
for r in banco:
    if r.get('classification_auto') == 'sin_cobertura' and r.get('categoria') == '3. Medicación':
        print(' -', r.get('pregunta'))
