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
        if almacenamiento is None:
            return

        if request_id in almacenamiento:
            almacenamiento[request_id] = respuesta
            return

    # Some IQ responses arrive after their original wait has expired.
    # Since the response payload is the same initialization snapshot, accept
    # a delayed/missing ID only when exactly one request is currently pending.
    # Never guess when concurrent requests make the response ambiguous.
    if almacenamiento is None:
        return

    pendientes = [
        pendiente_id
        for pendiente_id, resultado in almacenamiento.items()
        if resultado is None
    ]

    if len(pendientes) == 1:
        almacenamiento[pendientes[0]] = respuesta
