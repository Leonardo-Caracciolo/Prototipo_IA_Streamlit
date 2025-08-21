# core/graph_agent.py
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, ToolMessage, SystemMessage
from typing import TypedDict, Annotated, Sequence, List
import operator
from datetime import datetime
import json
from pathlib import Path
from langgraph.graph import StateGraph, END
# Importamos las tools con nombre explícito para poder whitelistear
from core.tools import (
    listar_facturas_por_cuit_receptor,
    listar_facturas_por_email_remitente,
    buscar_por_numero_factura,
    contar_duplicados_por_clave_natural,
    buscar_por_cae,
    total_facturado_por_emisor_y_mes,
    kpis_resumen,
    top_emisores_por_monto,
    facturas_por_condicion_venta,
    facturas_vencen_entre,
    facturas_por_moneda,
    buscar_facturas_por_texto_libre,
    ultimas_facturas,
    detalle_factura,
    resumen_percepciones_iibb,
    resumen_iva_por_alicuota,
    listar_facturas_recibidas,
    listar_facturas_emitidas,
    items_de_factura,
    info_factura_min,
    # Controles
    listar_apocrifas,
    listar_cae,
    listar_no_en_mis_comprobantes,
    listar_en_mis_comprobantes,
    listar_no_en_mis_comprobantes_por_cuit,
    listar_en_mis_comprobantes_por_cuit,
    # resumen_validaciones,
    # Controles CAE
    listar_no_en_padron_cae,
    listar_autorizacion_cae,
    # Controles CAE
    buscar_en_documentos_de_conocimiento,  # RAG por-workspace
    # RAG leyes (nuevas)
    buscar_fragmentos_de_leyes,
    contar_articulos_por_archivo,
    listar_articulos_de_ley,
    obtener_articulo_completo,
    generar_documento_word,
    generar_reporte_excel,
)


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    workspace: str
    ws_type: str

model = ChatOpenAI(temperature=0, model="gpt-4o", streaming=True)

def _allowed_tools_for(ws_type: str):
    ws = (ws_type or "").lower()
    if ws.startswith("analisis"):  # Análisis de facturas
        return [
            listar_facturas_por_cuit_receptor,
            listar_facturas_por_email_remitente,
            buscar_por_numero_factura,
            contar_duplicados_por_clave_natural,
            listar_facturas_recibidas,
            buscar_por_cae,
            total_facturado_por_emisor_y_mes,
            kpis_resumen,
            top_emisores_por_monto,
            facturas_por_condicion_venta,
            facturas_vencen_entre,
            facturas_por_moneda,
            buscar_facturas_por_texto_libre,
            listar_facturas_emitidas,
            ultimas_facturas,
            detalle_factura,
            resumen_percepciones_iibb,
            resumen_iva_por_alicuota,
            items_de_factura,
            info_factura_min,
            buscar_en_documentos_de_conocimiento,
            listar_apocrifas,
            listar_cae,
            listar_no_en_mis_comprobantes,
            # resumen_validaciones,
            listar_en_mis_comprobantes,
            listar_no_en_mis_comprobantes_por_cuit,
            listar_en_mis_comprobantes_por_cuit,
            listar_no_en_padron_cae,
            listar_autorizacion_cae,
        ]
    else:  # Conocimiento de leyes
        return [
            buscar_fragmentos_de_leyes,
            contar_articulos_por_archivo,
            listar_articulos_de_ley,
            obtener_articulo_completo,
            generar_documento_word,
            generar_reporte_excel,
        ]

def call_model(state: AgentState):
    messages = list(state["messages"])
    tools = _allowed_tools_for(state["ws_type"])
    model_with_tools = model.bind_tools(tools)

    if (state["ws_type"] or "").lower().startswith("analisis"):
        print("✔ [AGENT] Análisis de facturas")
        system_hint = SystemMessage(content=(
            "Eres un asistente de ANÁLISIS DE FACTURAS. "
            "Usa EXCLUSIVAMENTE las herramientas de base de datos (Postgres) provistas. "
            "NO consultes documentos vectorizados ni otras fuentes.\n\n"
            "Contexto de datos: esquema normalizado AFIP en Postgres. Usa la vista 'afip.facturas_flat' para consultas generales "
            "y las tools disponibles para agregados, búsqueda y detalle.\n\n"
            "Idioma: responde SIEMPRE en español, breve y directo. "
            "Zona horaria: America/Argentina/Buenos_Aires. Al interpretar 'hoy', 'ayer', etc., usa esa zona.\n\n"
            "Formato de respuesta: nunca muestres IDs internos. Muestra columnas amigables: "
            "emisor, comprobante (tipo/letra), PV-Número (con ceros), fechas (YYYY-MM-DD), total con moneda, remitente (emisor_mail) y file_name cuando aporte contexto. "
            "Formato de respuesta:\n"
            "- Comienza con un resumen de 1 línea (qué mostraste y filtros clave).\n"
            "- Si vas a mostrar 2+ filas, DEVUELVE LA TABLA usando obligatoriamente uno de estos fences (preferencia por JSON):\n"
            "  ```table:json\n"
            "  [{\"col1\":\"...\"}]\n"
            "  ```\n"
            "  También se aceptan:\n"
            "  ```table:markdown\n"
            "  | c1 | c2 |\n"
            "  |----|----|\n"
            "  | .. | .. |\n"
            "  ```\n"
            "  ```table:csv\n"
            "  c1,c2\\n..,..\n"
            "  ```\n"
            "- NO incluyas ningún texto ni comentarios dentro del bloque de tabla.\n"
            "- Para 1 sola fila o detalles puntuales, puedes listar en viñetas o una mini tabla (mismo esquema de fences si es tabla).\n"
            "- Nunca muestres IDs internos. Muestra columnas amigables: emisor, comprobante (tipo/letra), PV-Número (con ceros), "
            "  fechas (YYYY-MM-DD), total con moneda, remitente (emisor_mail) y file_name cuando aporte contexto.\n"
            "- Abrevia números y usa 2 decimales en importes.\n\n"
            "Moneda: entiende sinónimos del usuario (USD/US$/U$S/dólar/es; ARS/PESOS/AR$; EUR/€). "
            "Cuando se consulte por moneda, usa la tool preparada para variantes. "
            "Si no hay resultados, sugiere consultar 'monedas_disponibles'.\n\n"
            "Fechas: acepta 'YYYY-MM-DD' preferentemente. Si el usuario da otra forma, intenta inferir. "
            "Al mostrar, usa siempre 'YYYY-MM-DD'.\n\n"
            "Duplicados: el sistema permite guardar duplicados. Si el usuario pregunta por duplicados, usa la tool dedicada. "
            "No asumas deduplicación implícita.\n\n"
            "Errores: si una tool devuelve {'ok': False, 'error': '...'}, muestra un mensaje claro al usuario con el error resumido "
            "y sugiere 'ping_db' o una consulta de diagnóstico (por ejemplo, 'monedas_disponibles'). No inventes resultados.\n\n"
            "Límites y rendimiento: por defecto muestra hasta 20 filas (o el límite indicado por la tool). "
            "Si el resultado sugiere más filas, ofrece continuar ('¿Querés que traiga más?'). "
            "Evita consultas extremadamente amplias sin filtros.\n\n"
            "Privacidad: no reveles columnas internas (IDs, claves técnicas). "
            "Muestra 'emisor_mail' si es relevante para el usuario final (es el remitente del correo). "
            "No expongas datos sensibles que no hayan sido consultados explícitamente.\n\n"
            "Estilo: primero responde con un breve resumen (1 línea), luego la tabla/ítems. "
            "Recorda que estamos en el dia 21 de Agosto del 2025. "
            "Si una consulta es ambigua, elige un criterio razonable y explícalo en una línea (sin repreguntar salvo imprescindible)."
        ))
    else:
        # ✅ MODO ESTRICTO + Proceso guiado (todo en un solo prompt)
        system_hint = SystemMessage(content=(
            "Eres un asistente experto en legislación argentina.\n"
            "MODO ESTRICTO-CITADO:\n"
            "- Responde SOLO con información devuelta por las herramientas (sin conocimiento general).\n"
            "- Si las herramientas no devuelven nada, di: "
            "\"No encontré evidencia en los archivos indexados para esta consulta.\" "
            "y sugiere afinar (ley, provincia, artículo, palabra clave exacta).\n"
            "- Siempre cierra con una línea de fuente: \"Fuente: <file_name> — <artículo si aplica>\".\n"
            "\n"
            "Proceso obligado (3 pasos):\n"
            "1) BÚSQUEDA INICIAL → usa SOLO `buscar_fragmentos_de_leyes` (k≈8). "
            "   Si la consulta menciona IIBB/GANANCIAS/IVA, pásalo como `root`. "
            "   Si menciona una provincia (p.ej., 'Santiago del Estero'), pásala como `province`.\n"
            "2) PROFUNDIZACIÓN (opcional):\n"
            "   - Si el usuario pide 'Artículo N', llama `obtener_articulo_completo` con la `ley` (del paso 1) y `articulo_num`.\n"
            "   - Si pide 'listar todos los artículos/índice', llama `listar_articulos_de_ley` con esa `ley`.\n"
            "   - Si hay múltiples leyes/provincias en resultados, prioriza la que coincide con la provincia del usuario; "
            "     si no hay provincia, elige la ley más repetida en los fragmentos.\n"
            "3) SÍNTESIS → Responde claro y breve, sin inventar nada que no aparezca en las herramientas, y cita la fuente.\n"
        ))

    response = model_with_tools.invoke([system_hint] + messages)
    return {"messages": [response]}

def execute_tools_node(state: AgentState) -> dict:
    """
    Ejecuta SOLO herramientas permitidas según ws_type; inyecta el workspace REAL
    y guarda la salida de cada tool (si es JSON, la persiste como JSON).
    """
    last_message = state['messages'][-1]
    tool_calls = getattr(last_message, "tool_calls", []) or []

    # 🔐 Sólo herramientas permitidas para este tipo de chat
    allowed_tools = _allowed_tools_for(state["ws_type"])
    tool_map = {t.name: t for t in allowed_tools}

    # Opcional: log de tools habilitadas
    try:
        allowed_names = ", ".join(sorted(tool_map.keys()))
        print(f"[TOOLS] Habilitadas para '{state['ws_type']}': {allowed_names}")
    except Exception:
        pass

    workspace_real = state.get("workspace") or "default"

    debug_dir = Path("storage") / "debug" / str(workspace_real).replace(" ", "_")
    debug_dir.mkdir(parents=True, exist_ok=True)

    tool_messages: List[ToolMessage] = []

    for call in tool_calls:
        tool_name = call.get("name")
        tool_args = dict(call.get("args") or {})
        tool_id   = call.get("id")

        if tool_name not in tool_map:
            tool_messages.append(
                ToolMessage(
                    content=f"La herramienta '{tool_name}' no está permitida en este chat ({state.get('ws_type')}). "
                            f"Permitidas: {', '.join(sorted(tool_map.keys()))}.",
                    tool_call_id=tool_id,
                )
            )
            continue

        # Inyectar workspace real (aunque el tool no lo use, no molesta)
        tool_args["workspace"] = workspace_real

        try:
            output = tool_map[tool_name].invoke(tool_args)
        except Exception as e:
            ts = datetime.now()
            record = {
                "tool": tool_name,
                "called_at": ts.isoformat(timespec="seconds"),
                "workspace": workspace_real,
                "ws_type": state.get("ws_type"),
                "args": tool_args,
                "error": str(e),
            }
            fname = f"{ts.strftime('%Y%m%d_%H%M%S')}_{tool_name}_error.json"
            try:
                (debug_dir / fname).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

            tool_messages.append(
                ToolMessage(content=f"Error al ejecutar la herramienta {tool_name}: {e}", tool_call_id=tool_id)
            )
            continue

        # ── Persistencia de la salida de la tool ─────────────────────────────
        ts = datetime.now()
        fname = f"{ts.strftime('%Y%m%d_%H%M%S')}_{tool_name}.json"
        envelope = {
            "tool": tool_name,
            "called_at": ts.isoformat(timespec="seconds"),
            "workspace": workspace_real,
            "ws_type": state.get("ws_type"),
            "args": tool_args,
            "output_is_json": False,
            "output": None,
        }
        try:
            parsed = json.loads(output) if isinstance(output, str) else output
            if isinstance(parsed, (dict, list)):
                envelope["output_is_json"] = True
                envelope["output"] = parsed
            else:
                envelope["output"] = str(output)
        except Exception:
            envelope["output"] = str(output)

        try:
            (debug_dir / fname).write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        # ─────────────────────────────────────────────────────────────────────

        tool_messages.append(ToolMessage(content=str(output), tool_call_id=tool_id))

    return {"messages": tool_messages}


def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    return "continue" if last_message.tool_calls else "end"

def crear_grafo_agente():
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("action", execute_tools_node)

    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"continue": "action", "end": END})
    workflow.add_edge("action", "agent")
    return workflow.compile()

app = crear_grafo_agente()
