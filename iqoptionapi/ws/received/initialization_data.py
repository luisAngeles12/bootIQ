"""Module for IQ option websocket."""


def initialization_data(api, message):
    if message.get("name") != "initialization-data":
        return

    respuesta = message.get("msg")
    request_id = str(
        message.get("request_id", "") or ""
    )

    # Mantener el slot histórico por compatibilidad con
    # cualquier consumidor externo de iqoptionapi.
    api.api_option_init_all_result_v2 = respuesta

    almacenamiento = getattr(
        api,
        "api_option_init_all_result_v2_by_request",
        None,
    )

    if request_id:
        if (
            almacenamiento is not None
            and request_id in almacenamiento
        ):
            almacenamiento[request_id] = respuesta
        return

    # Some IQ sessions omit request_id from initialization-data.
    # Accept an untagged response only when exactly one request is pending;
    # never guess when concurrent requests make the response ambiguous.
    if almacenamiento is None:
        return

    pendientes = [
        pendiente_id
        for pendiente_id, resultado in almacenamiento.items()
        if resultado is None
    ]

    if len(pendientes) == 1:
        almacenamiento[pendientes[0]] = respuesta
