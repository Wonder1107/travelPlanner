from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

DEFAULT_TOP_K = 8

# 用于RAG，主要是从POI文件中查找
class POIRetriever:
    def __init__(self, data_path: Path | None = None) -> None:
        root_dir = Path(__file__).resolve().parents[3]
        self.data_path = data_path
        self.data_dir = root_dir / "data"
        self.pois: list[dict[str, Any]] = []
        self.city_pois: dict[str, list[dict[str, Any]]] = {}
        self.default_city_key = "shanghai"
        self._vector_ready = False
        self._vector_backend: Any = None
        self._vector_collection: Any = None
        self._openai_client: Any = None
        self._load_pois()

    def _normalize_city(self, city: str | None) -> str:
        if not city:
            return self.default_city_key
        head = city.strip().lower().split(",")[0]
        normalized = re.sub(r"[^a-z0-9_]+", "_", head).strip("_")
        if normalized == "shanghai_china":
            return "shanghai"
        if normalized == "beijing_china":
            return "beijing"
        return normalized or self.default_city_key

    def _city_key_from_filename(self, path: Path) -> str:
        stem = path.stem.lower()
        if stem.startswith("poi_"):
            return stem.replace("poi_", "", 1)
        return stem

    def _load_pois(self) -> None:
        self.city_pois = {}
        if self.data_path is not None:
            if self.data_path.exists():
                with self.data_path.open("r", encoding="utf-8") as fp:
                    loaded = json.load(fp)
                city_key = self._city_key_from_filename(self.data_path)
                self.city_pois[city_key] = [item for item in loaded if isinstance(item, dict)]
                self.default_city_key = city_key
        else:
            for path in sorted(self.data_dir.glob("poi_*.json")):
                try:
                    loaded = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(loaded, list):
                    continue
                city_key = self._city_key_from_filename(path)
                self.city_pois[city_key] = [item for item in loaded if isinstance(item, dict)]

        if "shanghai" in self.city_pois:
            self.default_city_key = "shanghai"
        elif self.city_pois:
            self.default_city_key = list(self.city_pois.keys())[0]

        self.pois = list(self.city_pois.get(self.default_city_key, []))

    def _pois_for_city(self, city: str | None) -> tuple[str, list[dict[str, Any]]]:
        city_key = self._normalize_city(city)
        if city_key in self.city_pois:
            return city_key, self.city_pois[city_key]
        if "default" in self.city_pois:
            return "default", self.city_pois["default"]
        return self.default_city_key, self.pois

    def build_index(self) -> None:
        # 可选向量索引：无 OPENAI_API_KEY 时自动退化到纯词法检索。
        if not self.pois:
            return
        self._init_vector_store()
        if not self._vector_ready:
            return
        points = []
        ids = []
        docs = []
        metas = []
        for poi in self.pois:
            poi_id = str(poi.get("id", ""))
            ids.append(poi_id)
            text = self._poi_to_text(poi)
            docs.append(text)
            metas.append({"category": poi.get("category", ""), "name": poi.get("name", "")})
            points.append(text)
        embeddings = self._embed_texts(points)
        if embeddings is None:
            self._vector_ready = False
            return
        self._vector_collection.upsert(ids=ids, embeddings=embeddings, documents=docs, metadatas=metas)

    def search(
        self,
        preferences: list[str],
        *,
        city: str | None = None,
        context: str = "",
        top_k: int = DEFAULT_TOP_K,
        require_indoor: bool | None = None,
        exclude_ids: set[str] | None = None,
        extra_tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """RAG 检索入口。

        排序信号由三部分组成：
        - 词法匹配（preferences / extra_tags / context）
        - 约束过滤（indoor / exclude_ids）
        - 可选向量重排（若向量后端可用）
        """
        city_key, city_pool = self._pois_for_city(city)
        exclude_ids = exclude_ids or set()
        extra_tags = extra_tags or []
        if self._vector_ready and city_key == self.default_city_key:
            combined_query = " ".join(preferences + extra_tags + [context]).strip()
            vector_hits = self._vector_query(combined_query, top_k=top_k * 2)
            if vector_hits:
                vector_rank = {poi_id: idx for idx, poi_id in enumerate(vector_hits)}
            else:
                vector_rank = {}
        else:
            vector_rank = {}

        ranked: list[tuple[float, dict[str, Any]]] = []
        pref_tokens = [token.lower() for token in preferences]
        extra_tokens = [token.lower() for token in extra_tags]
        context_tokens = [token.lower() for token in context.replace(",", " ").split() if token.strip()]

        for poi in city_pool:
            poi_id = str(poi.get("id", ""))
            if poi_id in exclude_ids:
                continue
            if require_indoor is True and not bool(poi.get("indoor", False)):
                continue
            tags = [tag.lower() for tag in poi.get("tags", [])]
            category = str(poi.get("category", "")).lower()
            desc = str(poi.get("desc", "")).lower()
            score = 0.1

            for token in pref_tokens:
                if token in tags:
                    score += 3.0
                if token in category:
                    score += 1.5
                if token in desc:
                    score += 1.0

            for token in extra_tokens:
                if token in tags:
                    score += 1.8
                if token in desc:
                    score += 0.8

            for token in context_tokens:
                if token in desc or token in tags or token in category:
                    score += 0.3

            if require_indoor is False and bool(poi.get("indoor", False)):
                score -= 0.5

            if poi_id in vector_rank:
                # 向量命中结果使用较温和加分，避免完全压制词法规则。
                score += max(0.0, 4.0 - vector_rank[poi_id] * 0.4)

            ranked.append((score, poi))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in ranked[:top_k]]

    def _poi_to_text(self, poi: dict[str, Any]) -> str:
        tags = ", ".join(poi.get("tags", []))
        return (
            f"{poi.get('name', '')}. Category: {poi.get('category', '')}. "
            f"Tags: {tags}. Description: {poi.get('desc', '')}."
        )

    def _init_vector_store(self) -> None:
        if self._vector_ready:
            return
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return
        try:
            import chromadb
            from openai import OpenAI
        except Exception:
            return

        chroma_dir = Path(__file__).resolve().parents[2] / ".chroma"
        chroma_dir.mkdir(parents=True, exist_ok=True)
        self._vector_backend = chromadb.PersistentClient(path=str(chroma_dir))
        self._vector_collection = self._vector_backend.get_or_create_collection("travel_poi")
        self._openai_client = OpenAI(api_key=api_key)
        self._vector_ready = True

    def _embed_texts(self, texts: list[str]) -> list[list[float]] | None:
        if not self._vector_ready:
            return None
        try:
            result = self._openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=texts,
            )
            return [item.embedding for item in result.data]
        except Exception:
            return None

    def _vector_query(self, query: str, top_k: int) -> list[str]:
        embeddings = self._embed_texts([query])
        if embeddings is None or self._vector_collection is None:
            return []
        try:
            result = self._vector_collection.query(query_embeddings=embeddings, n_results=top_k)
            return [str(item) for item in result.get("ids", [[]])[0]]
        except Exception:
            return []
