import weaviate
from app.embed import embed
from weaviate.classes.query import MetadataQuery

def search(text: str, k:int=3) -> list[dict]:
    client = weaviate.connect_to_local()
    try:
        kb = client.collections.get("KBArticle")
        vec=embed(text) #turn the query into 384 numbers
        results = kb.query.near_vector(
            near_vector=vec,
            limit = k,
            return_metadata=MetadataQuery(distance=True)
        )
        out=[]
        for o in results.objects:
            d=dict(o.properties)
            dist = o.metadata.distance or 0.0
            d["score"] = round((1-dist/2)*100,1) #cosine distance to 0..100 relevance conversion
            out.append(d)
        return out

    finally:
        client.close()