import os
import re
import threading
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

    def search(
        self, 
        query: str, 
        limit: int = 5, 
        expr: str | None = None, 
        output_fields: list[str] | None = None, 
    ) -> list[SearchResultItem]: 
        if output_fields is None: 
            output_fields = [self.id_field, self.text_field] 
        
        # 内部 _safe_embed 已经做好了超时管理，超时会返回 dummy 极小值向量
        query_dense_vector = self.embed_fn(query) 

        dense_req = AnnSearchRequest( 
            data=[query_dense_vector], 
            anns_field=self.dense_field, 
            param={ 
                "metric_type": "COSINE", 
                "params": { 
                    "ef": 64, 
                }, 
            }, 
            limit=limit, 
            expr=expr, 
        ) 

        sparse_req = AnnSearchRequest(
            data=[query], 
            anns_field=self.sparse_field, 
            param={
                "metric_type": "BM25",
                "params": {"drop_ratio_search": 0.2},
            },
            limit=limit, 
            expr=expr, 
        ) 
        
        try:
            # 无论 embedding 是否超时，都统一使用 hybrid_search，保证代码纯粹
            raw_results = self.client.hybrid_search( 
                collection_name=self.collection_name, 
                reqs=[sparse_req, dense_req], 
                ranker=self.ranker, 
                limit=limit, 
                output_fields=output_fields, 
            ) 
        except Exception as e:
            logger.error(f"phase=hybrid_search | error={e}")
            return []

        if not raw_results:
            return []
            
        hits = raw_results[0] 

        results: list[SearchResultItem] = [] 
        for i, hit in enumerate(hits): 
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
    _collection_locks: dict[str, threading.RLock] = {}
    _collection_locks_guard = threading.Lock()

    def __init__(self):
        self.config = get_config()
        self.milvus_uri = getattr(self.config, "MILVUS_URI", "http://milvus:19530")
        self.dim = 1536
        
        # 使用 DashScope 的 text-embedding-v2 模型
        self.embed_model = DashScopeEmbedding(
            model_name="text-embedding-v2",
            api_key=self.config.qwen.API_KEY
        )
        
        self.category_docs = {}
        # Dictionary to store embedding futures to track background embedding tasks
        self.embedding_futures = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def _get_collection_lock(cls, collection_name: str) -> threading.RLock:
        """为单个 collection 提供进程内互斥，避免并发 drop/create/flush 互相踩踏。"""
        with cls._collection_locks_guard:
            if collection_name not in cls._collection_locks:
                cls._collection_locks[collection_name] = threading.RLock()
            return cls._collection_locks[collection_name]

    def _normalize_collection_suffix(self, value: str) -> str:
        """将 session_id 归一化为 Milvus collection 名允许的 ASCII 后缀。"""
        safe_value = re.sub(r"[^A-Za-z0-9_]", "_", str(value or "default")).strip("_")
        return safe_value or "default"

    def _is_collection_not_found_error(self, error: Exception) -> bool:
        """识别 Milvus 元数据短暂不一致导致的 collection missing 错误。"""
        message = str(error).lower()
        return "collection not found" in message or "not found[collection" in message

    def _flush_collection_best_effort(
        self,
        client: MilvusClient,
        collection_name: str,
        *,
        category: str,
        session_id: str,
        max_retries: int = 3,
    ) -> bool:
        """尽力 flush collection；失败时交给内存候选缓存兜底。"""
        import time

        for attempt in range(1, max_retries + 1):
            try:
                if not client.has_collection(collection_name):
                    logger.warning(
                        f"phase=search_indexer | msg=flush_skipped_collection_missing | collection={collection_name} | category={category} | session_id={session_id}"
                    )
                    return False
                client.flush(collection_name)
                return True
            except Exception as e:
                if attempt < max_retries and self._is_collection_not_found_error(e):
                    logger.warning(
                        f"phase=search_indexer | msg=flush_retrying_after_collection_not_found | collection={collection_name} | category={category} | session_id={session_id} | attempt={attempt} | error={e}"
                    )
                    time.sleep(0.5 * attempt)
                    continue
                logger.warning(
                    f"phase=search_indexer | msg=flush_failed_fallback_cache_active | collection={collection_name} | category={category} | session_id={session_id} | error={e}"
                )
                return False
        return False

    def _load_collection_best_effort(
        self,
        client: MilvusClient,
        collection_name: str,
        *,
        category: str,
        session_id: str,
        max_retries: int = 3,
    ) -> bool:
        """尽力 load collection；失败不阻断主链路，search 会使用缓存兜底。"""
        import time

        for attempt in range(1, max_retries + 1):
            try:
                if not client.has_collection(collection_name):
                    logger.warning(
                        f"phase=search_indexer | msg=load_skipped_collection_missing | collection={collection_name} | category={category} | session_id={session_id}"
                    )
                    return False
                try:
                    client.describe_collection(collection_name)
                except Exception as e:
                    logger.warning(
                        f"phase=search_indexer | msg=describe_collection_failed_ignored | collection={collection_name} | category={category} | session_id={session_id} | error={e}"
                    )
                if attempt > 1:
                    time.sleep(1.0 * attempt)
                client.load_collection(collection_name)
                return True
            except Exception as e:
                if attempt == max_retries:
                    logger.warning(
                        f"phase=search_indexer | msg=load_collection_failed_fallback_cache_active | collection={collection_name} | category={category} | session_id={session_id} | error={e}"
                    )
                    return False
                logger.warning(
                    f"phase=search_indexer | msg=load_collection_failed_retrying | collection={collection_name} | category={category} | session_id={session_id} | attempt={attempt} | error={e}"
                )
        return False

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

    def _fallback_dense_vector(self) -> list[float]:
        """Return a tiny non-zero dense vector for timeout fallback."""
        return [1e-5] * self.dim

    def _is_zero_dense_vector(self, dense_vec: list[float]) -> bool:
        """Check whether a dense vector is the all-zero timeout placeholder."""
        return dense_vec == [0.0] * self.dim

    def build_global_vectors(self, force_rebuild: bool = False):
        """Build the global vector collection for all items from mock db."""
        import time
        from closedloop.utils.mock_db import load_mock_data

        collection_name = "closedloop_global_vectors"
        collection_lock = self._get_collection_lock(collection_name)
        collection_lock.acquire()
        try:
            client = MilvusClient(uri=self.milvus_uri)
            if client.has_collection(collection_name):
                if not force_rebuild:
                    logger.info(f"phase=search_indexer | msg=global_vectors_already_exist | collection={collection_name}")
                    return
                logger.info(f"phase=search_indexer | msg=rebuilding_global_vectors | collection={collection_name}")
                client.drop_collection(collection_name)
                time.sleep(2.0)  # Wait for proxy cache invalidation

            from pymilvus import DataType
            schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=True)
            schema.add_field(field_name="id", datatype=DataType.VARCHAR, max_length=256, is_primary=True)
            schema.add_field(field_name="dense_vector", datatype=DataType.FLOAT_VECTOR, dim=self.dim)

            index_params = client.prepare_index_params()
            index_params.add_index(field_name="dense_vector", index_type="AUTOINDEX", metric_type="COSINE")

            try:
                client.create_collection(
                    collection_name=collection_name,
                    schema=schema,
                    index_params=index_params
                )
            except Exception as e:
                logger.error(f"phase=search_indexer | msg=create_global_collection_failed_retrying | error={e}")
                time.sleep(2.0)
                client.create_collection(
                    collection_name=collection_name,
                    schema=schema,
                    index_params=index_params
                )

            # Load all items from Mock DB
            items = []
            try:
                restaurants = load_mock_data("restaurants.json")
                for r in restaurants:
                    for c in r.get("combos", []):
                        items.append(dict(c, **{"suitable_groups": r.get("suitable_groups", []), "child_facility_tags": r.get("child_facility_tags", []), "kid_menu_status": r.get("kid_menu_status"), "stroller_friendly_status": r.get("stroller_friendly_status"), "restaurant_name": r.get("name")}))
            except Exception as e:
                logger.error(f"phase=search_indexer | msg=load_restaurants_failed | error={e}")

            try:
                activities = load_mock_data("activities.json")
                for a in activities:
                    for p in a.get("packages", []):
                        items.append(dict(p, **{"suitable_groups": a.get("suitable_groups", []), "age_range": a.get("age_range", []), "venue_name": a.get("name")}))
            except Exception as e:
                logger.error(f"phase=search_indexer | msg=load_activities_failed | error={e}")

            try:
                add_ons = load_mock_data("add_ons.json")
                for g in add_ons:
                    for gift in g.get("gifts", []):
                        items.append(dict(gift, **{"suitable_groups": g.get("suitable_groups", []), "gift_type": g.get("gift_type"), "shop_name": g.get("name")}))
            except Exception as e:
                logger.error(f"phase=search_indexer | msg=load_add_ons_failed | error={e}")

            if not items:
                logger.warning("phase=search_indexer | msg=no_items_for_global_vectors")
                return

            texts = []
            item_ids = []
            for item in items:
                item_id = str(item.get("combo_id") or item.get("package_id") or item.get("gift_id") or item.get("id"))
                text = self._prepare_text(item)
                if not text.strip():
                    text = item.get("name", "Unknown Item")
                if item_id not in item_ids:  # Avoid duplicate ids
                    item_ids.append(item_id)
                    texts.append(text)

            dense_vecs = []
            batch_size = 25
            import concurrent.futures

            embedding_start_time = time.time()
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]

                # Global timeout check: For global build, we can allow more time, e.g., 60s
                if time.time() - embedding_start_time > 60.0:
                    logger.warning(f"phase=search_indexer | msg=global_build_embedding_timeout_reached | padding_zeros")
                    dense_vecs.extend([self._fallback_dense_vector() for _ in range(len(texts) - i)])
                    break

                max_retries = 3
                for attempt in range(max_retries + 1):
                    try:
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                            future = executor.submit(self.embed_model.get_text_embedding_batch, batch_texts)
                            batch_vecs = future.result(timeout=5.0)
                        dense_vecs.extend(batch_vecs)
                        break
                    except concurrent.futures.TimeoutError:
                        if attempt >= max_retries:
                            dense_vecs.extend([self._fallback_dense_vector() for _ in batch_texts])
                    except Exception as e:
                        if attempt < max_retries:
                            time.sleep(1.0)
                        else:
                            dense_vecs.extend([self._fallback_dense_vector() for _ in batch_texts])
                time.sleep(0.05)

            min_len = min(len(item_ids), len(dense_vecs))
            item_ids = item_ids[:min_len]
            dense_vecs = dense_vecs[:min_len]

            valid_data = []
            for item_id, dense_vec in zip(item_ids, dense_vecs):
                if self._is_zero_dense_vector(dense_vec):
                    dense_vec = self._fallback_dense_vector()
                valid_data.append({
                    "id": item_id,
                    "dense_vector": dense_vec,
                })

            if valid_data:
                # Insert in batches if too large, Milvus Lite handles it fine usually but better safe
                insert_batch_size = 1000
                for i in range(0, len(valid_data), insert_batch_size):
                    client.insert(collection_name=collection_name, data=valid_data[i:i+insert_batch_size])

            if not self._flush_collection_best_effort(
                client,
                collection_name,
                category="global",
                session_id="global",
            ):
                logger.warning(
                    f"phase=search_indexer | msg=global_vectors_build_degraded | collection={collection_name} | fallback=per_item_embedding"
                )
                return
            self._load_collection_best_effort(
                client,
                collection_name,
                category="global",
                session_id="global",
            )
            logger.info(f"phase=search_indexer | msg=global_vectors_built | count={len(valid_data)} | elapsed_sec={time.time() - embedding_start_time:.2f}")
        except Exception as e:
            logger.error(f"phase=search_indexer | msg=build_global_vectors_failed | error={e}")
        finally:
            collection_lock.release()

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
        safe_session_id = self._normalize_collection_suffix(session_id)
        collection_name = f"closedloop_{category}_{safe_session_id}"
        collection_lock = self._get_collection_lock(collection_name)
        collection_lock.acquire()
        try:
            client = MilvusClient(uri=self.milvus_uri)
            if client.has_collection(collection_name):
                client.drop_collection(collection_name)
                # Adding 2.0s sleep is crucial for Milvus to clear MetaCache before re-creating
                time.sleep(2.0)
                
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
                logger.error(f"phase=search_indexer | msg=create_collection_failed_retrying | collection={collection_name} | error={e}")
                time.sleep(2.0)
                client.create_collection(
                    collection_name=collection_name,
                    schema=schema,
                    index_params=index_params
                )
            
            # Fetch dense vectors from global cache
            data = []
            texts = []
            item_ids = []
            
            for item in items:
                item_id = str(item.get("combo_id") or item.get("package_id") or item.get("gift_id") or item.get("id"))
                text = self._prepare_text(item)
                if not text.strip():
                    text = item.get("name", "Unknown Item")
                item_ids.append(item_id)
                texts.append(text)
                
            # Query global vectors
            global_vectors = {}
            try:
                if client.has_collection("closedloop_global_vectors"):
                    # split item_ids into chunks of 100 to avoid overly long query string
                    chunk_size = 100
                    for i in range(0, len(item_ids), chunk_size):
                        chunk_ids = item_ids[i:i+chunk_size]
                        ids_str = ", ".join([f"'{str(x)}'" for x in chunk_ids])
                        res = client.query(
                            collection_name="closedloop_global_vectors",
                            filter=f"id in [{ids_str}]",
                            output_fields=["id", "dense_vector"]
                        )
                        for r in res:
                            global_vectors[r["id"]] = r["dense_vector"]
            except Exception as e:
                logger.error(f"phase=search_indexer | msg=query_global_vectors_failed | error={e}")

            valid_data = []
            for item_id, text in zip(item_ids, texts):
                dense_vec = global_vectors.get(item_id)
                if not dense_vec:
                    # Fallback for missing items
                    logger.warning(f"phase=search_indexer | msg=global_vector_miss | id={item_id}")
                    dense_vec = self._safe_embed(text)

                if self._is_zero_dense_vector(dense_vec):
                    dense_vec = self._fallback_dense_vector()

                valid_data.append({
                    "id": item_id,
                    "text": text,
                    "dense_vector": dense_vec,
                })

            if valid_data:
                # Insert in batches if too large, Milvus Lite handles it fine usually but better safe
                insert_batch_size = 1000
                for i in range(0, len(valid_data), insert_batch_size):
                    client.insert(collection_name=collection_name, data=valid_data[i:i+insert_batch_size])

            if not self._flush_collection_best_effort(
                client,
                collection_name,
                category=category,
                session_id=session_id,
            ):
                logger.warning(
                    f"phase=search_indexer | msg=session_index_build_degraded_cache_only | category={category} | session_id={session_id} | collection={collection_name}"
                )
                logger.info(f"phase=search_indexer | msg=index_cached_after_flush_failure | category={category} | count={len(items)} | session_id={session_id} | elapsed_sec={time.time() - start_time:.2f}")
                return

            # Explicitly create index again to ensure it exists before loading, bypassing some cache issues
            try:
                # Need to wait a bit after flush to make sure Milvus is ready
                import time
                time.sleep(1.0)

                # In Milvus Lite, calling flush right before create_index on the same connection
                # sometimes causes the collection to be marked as "not found" in the internal meta.
                # Let's verify if the collection exists before creating index
                if not client.has_collection(collection_name):
                    logger.error(f"phase=search_indexer | msg=collection_vanished_before_create_index | collection={collection_name}")
                else:
                    # correct usage of index_params
                    sparse_index_params = client.prepare_index_params()
                    sparse_index_params.add_index(field_name="sparse_vector", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25", params={"bm25_cg": "zh"})
                    client.create_index(collection_name=collection_name, index_params=sparse_index_params)
            except Exception as e:
                logger.warning(f"phase=search_indexer | msg=explicit_sparse_index_creation_failed_or_ignored | error={e}")

            self._load_collection_best_effort(
                client,
                collection_name,
                category=category,
                session_id=session_id,
            )

            logger.info(f"phase=search_indexer | msg=index_built_successfully | category={category} | count={len(items)} | session_id={session_id} | elapsed_sec={time.time() - start_time:.2f}")
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"phase=search_indexer | msg=milvus_build_failed | error={e} | session_id={session_id} | elapsed_sec={elapsed:.2f}")
        finally:
            collection_lock.release()

    def _safe_embed(self, query: str) -> list[float]:
        import concurrent.futures
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.embed_model.get_text_embedding, query)
                vec = future.result(timeout=1.5)  # 严格限制 1.5s 超时
            if not vec:
                # 避免纯零向量在 COSINE 距离下抛出零除异常，使用极小值占位
                logger.warning(f"phase=search_indexer | msg=query_sparse_fallback_active | reason=empty_embedding")
                return self._fallback_dense_vector()
            return vec
        except concurrent.futures.TimeoutError:
            logger.warning(f"phase=search_indexer | msg=query_embedding_timeout | query={query[:20]}")
            logger.warning("phase=search_indexer | msg=query_sparse_fallback_active | reason=timeout")
            return self._fallback_dense_vector()
        except Exception as e:
            logger.error(f"phase=search_indexer | msg=query_embedding_failed | error={e}")
            logger.warning("phase=search_indexer | msg=query_sparse_fallback_active | reason=exception")
            return self._fallback_dense_vector()

    def search(self, category: str, query: str, top_k: int = 5, session_id: str = "default") -> List[Dict[str, Any]]:
        safe_session_id = self._normalize_collection_suffix(session_id)
        collection_name = f"closedloop_{category}_{safe_session_id}"
        
        session_docs = self.category_docs.get(session_id, {})
        cached_items = session_docs.get(category, [])
        logger.info(
            f"phase=search_indexer | msg=search_started | category={category} | query={query} | top_k={top_k} | session_id={session_id} | collection={collection_name} | cached_count={len(cached_items)}"
        )
        
        collection_lock = self._get_collection_lock(collection_name)
        collection_lock.acquire()
        try:
            client = MilvusClient(uri=self.milvus_uri)
            if not client.has_collection(collection_name):
                logger.warning(
                    f"phase=search_indexer | msg=collection_not_found_fallback | collection={collection_name} | session_id={session_id} | cached_count={len(cached_items)}"
                )
                return cached_items[:top_k]
                
            if not self._load_collection_best_effort(
                client,
                collection_name,
                category=category,
                session_id=session_id,
                max_retries=2,
            ):
                return cached_items[:top_k]
            
            searcher = MilvusHybridSearcher(
                uri=self.milvus_uri,
                collection_name=collection_name,
                embed_fn=self._safe_embed
            )
            
            results = searcher.search(query=query, limit=top_k)
            
            # Match with original items
            found_items = []
            for res in results:
                for item in session_docs.get(category, []):
                    item_id = str(item.get("combo_id") or item.get("package_id") or item.get("gift_id") or item.get("id"))
                    if item_id == res.id:
                        found_items.append(item)
                        break
            
            if found_items:
                logger.info(
                    f"phase=search_indexer | msg=search_success | category={category} | session_id={session_id} | result_count={len(found_items)}"
                )
                return found_items
                
        except Exception as e:
            logger.warning(
                f"phase=search_indexer | msg=hybrid_search_failed_fallback_to_default | category={category} | session_id={session_id} | error={e}"
            )
        finally:
            collection_lock.release()
            
        # Fallback default: return top_k from category_docs directly
        logger.warning(
            f"phase=search_indexer | msg=search_returning_cached_items | category={category} | session_id={session_id} | cached_count={len(cached_items)}"
        )
        return cached_items[:top_k]

    def get_item(self, item_id: str, session_id: str = "default") -> Dict[str, Any]:
        """从内存缓存中获取完整的 item 数据"""
        session_docs = self.category_docs.get(session_id, {})
        for category, items in session_docs.items():
            for item in items:
                cand_id = str(item.get("combo_id") or item.get("package_id") or item.get("gift_id") or item.get("id"))
                if cand_id == item_id:
                    logger.info(f"phase=search_indexer | msg=get_item_hit | item_id={item_id} | session_id={session_id} | category={category}")
                    return item
        logger.warning(f"phase=search_indexer | msg=get_item_miss | item_id={item_id} | session_id={session_id}")
        return {}
