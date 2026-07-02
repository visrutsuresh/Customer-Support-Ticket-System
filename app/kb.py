import weaviate
from app.embed import embed

def search(text: str, k:int=3) -> list[dict]:
    client = weaviate.connect_to_local()
    try:
        kb = client.collections.get("KBArticle")
        vec=embed(text) #turn the query into 384 numbers
        results = kb.query.near_vector(
            near_vector=vec,
            limit = k,
        )
        return [o.properties for o in results.objects]
    finally:
        client.close()