import os
from typing import List, Dict, Any
from dataclasses import dataclass

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger

from pymilvus import MilvusClient, AnnSearchRequest, WeightedRanker, DataType
from llama_index.embeddings.dashscope import DashScopeEmbedding

@dataclass 
class SearchResultItem: 
    rank: int 
    id: Any 
    score: float 
    text: str 
    entity: dict 

class MilvusHybridSearcher: 
    """ 
    Milvus Hybrid Search: 
    - dense_vector: 语义向量召回 
    - sparse_vector: BM25 / sparse 召回 
    - WeightedRanker: 按权重融合，例如 0.5 dense + 0.5 sparse 
    """ 

    def __init__( 
        self, 
        uri: str, 
        collection_name: str, 
        embed_fn, 
        dense_field: str = "dense_vector", 
        sparse_field: str = "sparse_vector", 
        text_field: str = "text", 
        id_field: str = "id", 
        dense_weight: float = 0.5, 
        sparse_weight: float = 0.5, 
    ): 
        self.client = MilvusClient(uri=uri) 
        self.collection_name = collection_name 
        self.embed_fn = embed_fn 

        self.dense_field = dense_field 
        self.sparse_field = sparse_field 
        self.text_field = text_field 
        self.id_field = id_field 

        self.ranker = WeightedRanker(dense_weight, sparse_weight) 

    def search_offset(
        self, 
        query: str, 
        top_k: int = 15, 
        offset: int = 0, 
        expr: str | None = None, 
        output_fields: list[str] | None = None, 
    ) -> list[SearchResultItem]: 
        assert offset >= 0
        assert top_k >= 1

        end = offset + top_k

        if output_fields is None: 
            output_fields = [self.id_field, self.text_field] 

        query_dense_vector = self.embed_fn(query) 

        branch_limit = max(end * 2, 50) 

        dense_req = AnnSearchRequest( 
            data=[query_dense_vector], 
            anns_field=self.dense_field, 
            param={ 
                "metric_type": "COSINE", 
                "params": { 
                    "ef": 64, 
                }, 
            }, 
            limit=branch_limit, 
            expr=expr, 
        ) 

        sparse_req = AnnSearchRequest(
            data=[query], 
            anns_field=self.sparse_field, 
            param={
                "metric_type": "BM25",
                "params": {"drop_ratio_search": 0.2},
            },
            limit=branch_limit, 
            expr=expr, 
        ) 
        
        try:
            raw_results = self.client.hybrid_search( 
                collection_name=self.collection_name, 
                reqs=[dense_req, sparse_req], 
                ranker=self.ranker, 
                limit=end, 
                output_fields=output_fields, 
            ) 
        except Exception as e:
            logger.error(f"phase=hybrid_search | error={e}")
            return []

        if not raw_results:
            return []
            
        hits = raw_results[0] 
        page_hits = hits[offset:end]

        results: list[SearchResultItem] = [] 
        for i, hit in enumerate(page_hits, start=offset + 1): 
            if isinstance(hit, dict): 
                entity = hit.get("entity", {}) or {} 
                score = hit.get("distance", 0.0) 
            else: 
                entity = dict(hit.entity) if getattr(hit, "entity", None) is not None else {} 
                score = getattr(hit, "score", None) 
                if score is None: 
                    score = getattr(hit, "distance", 0.0) 

            item = SearchResultItem( 
                rank=i, 
                id=entity.get(self.id_field), 
                score=float(score or 0.0), 
                text=entity.get(self.text_field, ""), 
                entity=entity, 
            ) 
            results.append(item) 

        return results 

class SearchIndexer:
    _instance = None

    def __init__(self):
        self.config = get_config()
        self.milvus_uri = getattr(self.config, "MILVUS_URI", "http://milvus:19530")
        self.dim = 1024
        
        api_key = getattr(self.config.qwen, "API_KEY", os.getenv("DASHSCOPE_API_KEY"))
        self.embed_model = DashScopeEmbedding(
            model_name="text-embedding-v4",
            api_key=api_key
        )
        
        self.category_docs = {}
        # Dictionary to store embedding futures to track background embedding tasks
        self.embedding_futures = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _prepare_text(self, item: dict) -> str:
        name = item.get("name", "")
        intro = item.get("description", "") or item.get("intro", "")
        
        features = item.get("features", "")
        if isinstance(features, list):
            features = " ".join(features)
            
        tags = item.get("experience_tag", "")
        if isinstance(tags, list):
            tags = " ".join(tags)
            
        # --- 新增：将关键指标映射为文本，提升检索命中率 ---
        groups = item.get("suitable_groups", [])
        groups_str = " ".join(groups) if isinstance(groups, list) else str(groups)
        
        child_facilities = item.get("child_facility_tags", [])
        child_facilities_str = " ".join(child_facilities) if isinstance(child_facilities, list) else str(child_facilities)
        
        age_range = item.get("age_range", [])
        age_range_str = "适合年龄: " + " ".join(age_range) if isinstance(age_range, list) and age_range else ""
        
        kid_menu_str = "提供儿童餐" if item.get("kid_menu_status") in ("explicit", "possible") else ""
        stroller_str = "婴儿推车友好" if item.get("stroller_friendly_status") in ("yes", "likely") else ""
        
        gift_type = item.get("gift_type", "")
        
        parts = [name, intro, features, tags, groups_str, child_facilities_str, age_range_str, kid_menu_str, stroller_str, gift_type]
        return " ".join([p for p in parts if p]).strip()

    def build_index(self, category: str, items: List[Dict[str, Any]], session_id: str = "default"):
        if not items:
            return
            
        import time
        start_time = time.time()
        
        logger.info(f"phase=search_indexer | msg=building_index | category={category} | count={len(items)} | session_id={session_id}")
        
        if session_id not in self.category_docs:
            self.category_docs[session_id] = {}
        self.category_docs[session_id][category] = items
        
        # Replace hyphens in session_id to avoid Milvus collection name issues (Milvus only allows [a-zA-Z0-9_])
        safe_session_id = session_id.replace("-", "_")
        collection_name = f"closedloop_{category}_{safe_session_id}"
        try:
            client = MilvusClient(uri=self.milvus_uri)
            if client.has_collection(collection_name):
                client.drop_collection(collection_name)
                
            # Create schema for BM25 and dense
            # Due to a bug in PyMilvus milvus-lite on Windows where os.rename fails, we can't reliably use
            # create_index with SPARSE_INVERTED_INDEX if it triggers the manifest save bug.
            # However, if we skip index creation, milvus-lite might not support BM25 hybrid search properly.
            # Wait, the error actually comes from creating ANY index because it saves manifest.
            # Let's try not creating any explicit index and rely on autoindex. Wait, the code below:
            # We can use standard PyMilvus API and just catch the manifest error. The collection might still work!
            
            from pymilvus import Function, FunctionType
            schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=True)
            schema.add_field(field_name="id", datatype=DataType.VARCHAR, max_length=256, is_primary=True)
            schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535, enable_analyzer=True)
            schema.add_field(field_name="dense_vector", datatype=DataType.FLOAT_VECTOR, dim=self.dim)
            schema.add_field(field_name="sparse_vector", datatype=DataType.SPARSE_FLOAT_VECTOR)
            
            # Add BM25 function
            bm25_function = Function(
                name="text_bm25_emb",
                function_type=FunctionType.BM25,
                input_field_names=["text"],
                output_field_names=["sparse_vector"],
            )
            schema.add_function(bm25_function)
            
            index_params = client.prepare_index_params()
            index_params.add_index(field_name="dense_vector", index_type="AUTOINDEX", metric_type="COSINE")
            index_params.add_index(field_name="sparse_vector", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25", params={"bm25_cg": "zh"})
            
            try:
                client.create_collection(
                    collection_name=collection_name,
                    schema=schema,
                    index_params=index_params
                )
            except Exception as e:
                logger.error(f"phase=search_indexer | msg=create_collection_failed | collection={collection_name} | error={e}")
                raise
            
            # Insert data (Use DashScope to get dense embeddings in batches if possible, but here we do it sequentially or via bulk API)
            # To speed up building, we use get_text_embedding_batch
            data = []
            texts = []
            item_ids = []
            
            for item in items:
                item_id = str(item.get("combo_id") or item.get("package_id") or item.get("gift_id") or item.get("id"))
                text = self._prepare_text(item)
                # Ensure text is not empty, DashScope embedding might fail or return None for empty strings
                if not text.strip():
                    text = item.get("name", "Unknown Item")
                item_ids.append(item_id)
                texts.append(text)
                
            # Call DashScope batch API to save time!
            # The DashScope API expects a list of non-empty strings.
            # If some strings are empty or too long, it might cause Pydantic validation errors inside LlamaIndex.
            # DashScope API batch size limit is strictly 10.
            dense_vecs = []
            batch_size = 10
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                batch_ids = item_ids[i:i + batch_size]
                
                batch_vecs = None
                for attempt in range(3):
                    try:
                        batch_vecs = self.embed_model.get_text_embedding_batch(batch_texts)
                        break
                    except Exception as e:
                        if attempt == 2:
                            logger.warning(f"phase=search_indexer | msg=batch_embedding_failed | batch_start={i} | error={e} | failed_ids={batch_ids}")
                        else:
                            time.sleep(1.5 ** attempt)
                            
                if batch_vecs:
                    dense_vecs.extend(batch_vecs)
                else:
                    # Fallback to sequential if batch fails
                    for t, tid in zip(batch_texts, batch_ids):
                        v = None
                        for attempt in range(3):
                            try:
                                v = self.embed_model.get_text_embedding(t)
                                break
                            except Exception as inner_e:
                                if attempt == 2:
                                    logger.error(f"phase=search_indexer | msg=single_embedding_failed | id={tid} | error={inner_e}")
                                else:
                                    time.sleep(1.5 ** attempt)
                                    
                        if not v:
                            logger.error(f"phase=search_indexer | msg=single_embedding_returned_empty_or_failed | id={tid} | text={t[:50]}...")
                            v = [0.0] * self.dim
                        dense_vecs.append(v)
            
            # 防御：避免 embedding 数量和 item 数量不一致 
            if len(dense_vecs) != len(item_ids): 
                logger.error( 
                    f"phase=search_indexer | msg=embedding_count_mismatch | " 
                    f"items={len(item_ids)} | embeddings={len(dense_vecs)}" 
                ) 
                min_len = min(len(item_ids), len(dense_vecs)) 
                item_ids = item_ids[:min_len] 
                texts = texts[:min_len] 
                dense_vecs = dense_vecs[:min_len] 

            for item_id, text, dense_vec in zip(item_ids, texts, dense_vecs):
                data.append({
                    "id": item_id,
                    "text": text,
                    "dense_vector": dense_vec,
                })
                
            if data:
                client.insert(collection_name=collection_name, data=data)
            
            client.flush(collection_name) 
            client.load_collection(collection_name)
            
            elapsed = time.time() - start_time
            logger.info(f"phase=search_indexer | msg=index_built_successfully | category={category} | count={len(items)} | session_id={session_id} | elapsed_sec={elapsed:.2f}")
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"phase=search_indexer | msg=milvus_build_failed | error={e} | session_id={session_id} | elapsed_sec={elapsed:.2f}")

    def _safe_embed(self, query: str) -> list[float]:
        import time
        for attempt in range(3):
            try:
                vec = self.embed_model.get_text_embedding(query)
                if not vec:
                    if attempt == 2:
                        return [0.0] * self.dim
                    continue
                return vec
            except Exception as e:
                if attempt == 2:
                    logger.error(f"phase=search_indexer | msg=query_embedding_failed | error={e}")
                    return [0.0] * self.dim
                time.sleep(1.5 ** attempt)
        return [0.0] * self.dim

    def search(self, category: str, query: str, top_k: int = 15, offset: int = 0, session_id: str = "default") -> List[Dict[str, Any]]:
        safe_session_id = session_id.replace("-", "_")
        collection_name = f"closedloop_{category}_{safe_session_id}"
        page = (offset // top_k) + 1
        page_size = top_k
        
        session_docs = self.category_docs.get(session_id, {})
        
        try:
            client = MilvusClient(uri=self.milvus_uri)
            if not client.has_collection(collection_name):
                logger.warning(f"phase=search_indexer | msg=collection_not_found_fallback | collection={collection_name}")
                items = session_docs.get(category, [])
                return items[offset:offset+top_k]
                
            client.load_collection(collection_name)
            
            searcher = MilvusHybridSearcher(
                uri=self.milvus_uri,
                collection_name=collection_name,
                embed_fn=self._safe_embed
            )
            
            results = searcher.search_offset(query=query, top_k=top_k, offset=offset)
            
            # Match with original items
            found_items = []
            for res in results:
                for item in session_docs.get(category, []):
                    item_id = str(item.get("combo_id") or item.get("package_id") or item.get("gift_id") or item.get("id"))
                    if item_id == res.id:
                        found_items.append(item)
                        break
            
            if found_items:
                return found_items
                
        except Exception as e:
            logger.warning(f"phase=search_indexer | msg=hybrid_search_failed_fallback_to_default | error={e}")
            
        # Fallback default: return top_k from category_docs directly
        items = session_docs.get(category, [])
        return items[offset:offset+top_k]

    def get_item(self, item_id: str, session_id: str = "default") -> Dict[str, Any]:
        """从内存缓存中获取完整的 item 数据"""
        session_docs = self.category_docs.get(session_id, {})
        for category, items in session_docs.items():
            for item in items:
                cand_id = str(item.get("combo_id") or item.get("package_id") or item.get("gift_id") or item.get("id"))
                if cand_id == item_id:
                    return item
        return {}
