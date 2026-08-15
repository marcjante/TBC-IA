path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old1 = '''    return {
        "response": final_response,
        "sources": sources_used,
    }'''

new1 = '''    result = {
        "response": final_response,
        "sources": sources_used,
    }
    if request.debug:
        result["debug_info"] = {
            "model": CHAT_MODEL,
            "top_k": request.top_k,
            "top1_distance": distances[0] if distances else None,
            "has_keyword": has_keyword,
            "fragments_retrieved": len(fragments),
        }
    return result'''

assert content.count(old1) == 1, "El bloque de /api/chat no es unico o no se encontro"
content = content.replace(old1, new1)

old2 = '    return {"response": final_response}'
new2 = '''    result = {"response": final_response}
    if request.debug:
        result["debug_info"] = {
            "model": CHAT_MODEL,
            "top_k": 8,
            "top1_distance": distances[0] if distances else None,
            "has_keyword": has_keyword,
        }
    return result'''

assert content.count(old2) == 1, "El bloque de /api/patient-chat no es unico o no se encontro"
content = content.replace(old2, new2)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("debug_info anadido a ambos endpoints")
