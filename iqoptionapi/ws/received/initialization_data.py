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

    # BootIQ usa correlación estricta por request_id.
    if request_id:
        almacenamiento = getattr(
            api,
            "api_option_init_all_result_v2_by_request",
            None,
        )

        if (
            almacenamiento is not None
            and request_id in almacenamiento
        ):
            almacenamiento[request_id] = respuesta
