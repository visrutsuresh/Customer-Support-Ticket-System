import os

import weaviate
from weaviate.classes.init import Auth
from weaviate.classes.query import MetadataQuery

from app.embed import embed

# ponytail: floor only catches genuinely off-topic hits. Same-band junk (KB has no good
# article, everything scores ~82-85) is a content gap a score floor cannot fix.
RELEVANCE_FLOOR = 60


def connect() -> weaviate.WeaviateClient:
    """Local Docker by default. WEAVIATE_URL + WEAVIATE_API_KEY switch to
    Weaviate Cloud (the deployed path). WEAVIATE_HOST covers compose networking."""
    url = os.getenv("WEAVIATE_URL")
    if url:
        return weaviate.connect_to_weaviate_cloud(
            cluster_url=url, auth_credentials=Auth.api_key(os.getenv("WEAVIATE_API_KEY", ""))
        )
    return weaviate.connect_to_local(host=os.getenv("WEAVIATE_HOST", "localhost"))


def search(text: str, k: int = 5) -> list[dict]:
    # Weaviate down = "no articles found", never a dead ticket: the pipeline
    # sees an empty retrieval and escalates to a human, which is the right degrade
    try:
        client = connect()
    except Exception as e:
        print(f"kb.search degraded, weaviate unreachable: {e}")
        return []
    try:
        kb = client.collections.get("Knowledge")
        vec = embed(text)  # turn the query into 384 numbers
        results = kb.query.near_vector(near_vector=vec, limit=k, return_metadata=MetadataQuery(distance=True))
        out = []
        for o in results.objects:
            d = dict(o.properties)
            dist = o.metadata.distance or 0.0
            d["score"] = round((1 - dist / 2) * 100, 1)  # cosine distance to 0..100 relevance conversion
            out.append(d)
        return [h for h in out if h["score"] >= RELEVANCE_FLOOR]
    except Exception as e:
        print(f"kb.search degraded mid-query: {e}")
        return []
    finally:
        client.close()


def index_resolved(title: str, content: str) -> None:
    # best-effort: losing one KB write must not fail the customer's resolve click
    try:
        client = connect()
    except Exception as e:
        print(f"kb.index_resolved skipped, weaviate unreachable: {e}")
        return
    try:
        kb = client.collections.get("knowledge")
        kb.data.insert(
            properties={"title": title, "content": content, "source": "ticket"},
            vector=embed(title + ". " + content),
        )
    except Exception as e:
        print(f"kb.index_resolved failed: {e}")
    finally:
        client.close()
