from fastembed import TextEmbedding

_model = TextEmbedding()  # bge-small-en-v1.5 384-number model


def embed(text: str) -> list[float]:
    return list(_model.embed([text]))[0].tolist()
