import weaviate
from app.embed import embed
from weaviate.classes.query import MetadataQuery

# ponytail: floor only catches genuinely off-topic hits. Same-band junk (KB has no good
# article, everything scores ~82-85) is a content gap a score floor cannot fix.
RELEVANCE_FLOOR = 60

def search(text: str, k:int=5) -> list[dict]:
    client = weaviate.connect_to_local()
    try:
        kb = client.collections.get("Knowledge")
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
        return [h for h in out if h["score"] >= RELEVANCE_FLOOR]

    finally:
        client.close()

def index_resolved(title: str, content: str) -> None:
    client = weaviate.connect_to_local()
    try:
        kb = client.collections.get("knowledge")
        kb.data.insert(
            properties = {"title": title, "content": content, "source": "ticket"},
            vector = embed(title + ". " + content ),
        )

    finally:
        client.close()