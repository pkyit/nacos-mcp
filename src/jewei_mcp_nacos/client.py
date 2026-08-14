"""Nacos HTTP 客户端 - 单文件实现，v1/v2 API 混合使用。

配置管理走 v1 API（兼容性好，有配置列表接口）。
服务发现 / 命名空间走 v2 API（字段更丰富）。
"""

import os
import time
from typing import Any, Optional

import httpx

# 连接池空闲释放时间（秒）
_IDLE_TTL = 300


class NacosClient:
    """Nacos HTTP 客户端。"""

    def __init__(self) -> None:
        self.host: str = os.getenv("NACOS_HOST", "localhost")
        self.port: int = int(os.getenv("NACOS_PORT", "8848"))
        self.username: str = os.getenv("NACOS_USERNAME", "nacos")
        self.password: str = os.getenv("NACOS_PASSWORD", "nacos")
        self.default_namespace: str = os.getenv("NACOS_NAMESPACE", "public")
        self.read_only: bool = os.getenv("NACOS_READ_ONLY", "false").lower() == "true"

        self._client: Optional[httpx.AsyncClient] = None
        self._last_used: float = 0
        self._access_token: Optional[str] = None
        self._token_expire_time: Optional[float] = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    # ── httpx 连接池管理 ─────────────────────────────────────────

    def _get_client(self) -> httpx.AsyncClient:
        """获取 httpx 客户端，空闲超过 TTL 自动重建。"""
        now = time.time()
        if self._client is not None:
            if now - self._last_used > _IDLE_TTL:
                # 空闲太久，释放旧连接
                try:
                    self._client.aclose()
                except Exception:
                    pass
                self._client = None
                self._access_token = None
                self._token_expire_time = None

        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(15.0, connect=10.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )

        self._last_used = now
        return self._client

    # ── 鉴权 ─────────────────────────────────────────────────────

    async def _ensure_token(self) -> Optional[str]:
        """获取 / 刷新 access token。"""
        if self._access_token and self._token_expire_time:
            if time.time() < self._token_expire_time - 300:
                return self._access_token

        client = self._get_client()
        resp = await client.post(
            "/nacos/v1/auth/login",
            data={"username": self.username, "password": self.password},
        )
        resp.raise_for_status()
        data = resp.json()

        self._access_token = data.get("accessToken")
        ttl = int(data.get("tokenTtl", 18000))
        self._token_expire_time = time.time() + ttl
        return self._access_token

    def _auth_params(self, token: Optional[str]) -> dict[str, str]:
        """给 v1 API 用的 query params 鉴权参数。"""
        if token:
            return {"accessToken": token}
        return {}

    # ── 连接检测 ─────────────────────────────────────────────────

    def _connection_guidance(self, error: Exception) -> str:
        """连接失败时返回引导文本，让 AI 主动询问用户。"""
        return (
            f"Nacos 连接失败（{type(error).__name__}: {error}）。\n\n"
            f"当前配置：\n"
            f"  NACOS_HOST: {self.host}\n"
            f"  NACOS_PORT: {self.port}\n"
            f"  NACOS_USERNAME: {self.username}\n"
            f"  NACOS_PASSWORD: {'*' * len(self.password)}\n\n"
            f"请检查：\n"
            f"1. Nacos 服务是否在线\n"
            f"2. 以上配置是否正确\n"
            f"3. 网络是否可达\n\n"
            f"如果信息有误，请提供正确的连接参数。"
        )

    # ── 通用 ─────────────────────────────────────────────────────

    def _namespace(self, namespace_id: Optional[str]) -> str:
        return namespace_id or self.default_namespace

    # ══════════════════════════════════════════════════════════════
    # 配置管理 API（v1）
    # ══════════════════════════════════════════════════════════════

    async def list_configs(
        self,
        namespace_id: Optional[str] = None,
        group: Optional[str] = None,
        data_id: Optional[str] = None,
        page_no: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """列出配置列表（v1 API）。"""
        try:
            token = await self._ensure_token()
        except Exception as e:
            return {"error": True, "message": self._connection_guidance(e)}

        params: dict[str, Any] = {
            "search": "accurate",
            "dataId": data_id or "",
            "group": group or "",
            "pageNo": page_no,
            "pageSize": page_size,
            "tenant": self._namespace(namespace_id),
            **self._auth_params(token),
        }

        client = self._get_client()
        resp = await client.get("/nacos/v1/cs/configs", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_config(
        self,
        data_id: str,
        group_name: str = "DEFAULT_GROUP",
        namespace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """获取配置内容（v1 API，返回原始文本）。"""
        try:
            token = await self._ensure_token()
        except Exception as e:
            return {"error": True, "message": self._connection_guidance(e)}

        params: dict[str, str] = {
            "dataId": data_id,
            "group": group_name,
            **self._auth_params(token),
        }
        ns = self._namespace(namespace_id)
        if ns:
            params["tenant"] = ns

        client = self._get_client()
        resp = await client.get("/nacos/v1/cs/configs", params=params)

        if resp.status_code == 404:
            return {
                "dataId": data_id,
                "groupName": group_name,
                "namespaceId": ns,
                "content": None,
            }

        resp.raise_for_status()
        return {
            "dataId": data_id,
            "groupName": group_name,
            "namespaceId": ns,
            "content": resp.text,
            "type": None,
            "md5": None,
        }

    async def publish_config(
        self,
        data_id: str,
        content: str,
        group_name: str = "DEFAULT_GROUP",
        namespace_id: Optional[str] = None,
        config_type: str = "yaml",
        desc: Optional[str] = None,
    ) -> dict[str, Any]:
        """发布/更新配置（v1 API）。"""
        if self.read_only:
            return {"success": False, "message": "当前为只读模式，禁止发布配置"}

        try:
            token = await self._ensure_token()
        except Exception as e:
            return {"error": True, "message": self._connection_guidance(e)}

        ns = self._namespace(namespace_id)
        data: dict[str, str] = {
            "dataId": data_id,
            "group": group_name,
            "content": content,
            "type": config_type,
        }
        if ns:
            data["tenant"] = ns
        if desc:
            data["desc"] = desc

        client = self._get_client()
        resp = await client.post(
            "/nacos/v1/cs/configs",
            params=self._auth_params(token),
            data=data,
        )
        resp.raise_for_status()
        result = resp.text.strip().lower()
        return {"success": result == "true", "message": resp.text.strip()}

    async def delete_config(
        self,
        data_id: str,
        group_name: str = "DEFAULT_GROUP",
        namespace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """删除配置（v1 API）。"""
        if self.read_only:
            return {"success": False, "message": "当前为只读模式，禁止删除配置"}

        try:
            token = await self._ensure_token()
        except Exception as e:
            return {"error": True, "message": self._connection_guidance(e)}

        params: dict[str, str] = {
            "dataId": data_id,
            "group": group_name,
            **self._auth_params(token),
        }
        ns = self._namespace(namespace_id)
        if ns:
            params["tenant"] = ns

        client = self._get_client()
        resp = await client.delete("/nacos/v1/cs/configs", params=params)
        resp.raise_for_status()
        result = resp.text.strip().lower()
        return {"success": result == "true", "message": resp.text.strip()}

    async def list_config_history(
        self,
        data_id: str,
        group_name: str = "DEFAULT_GROUP",
        namespace_id: Optional[str] = None,
        page_no: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """查询配置变更历史（v2 API）。"""
        try:
            token = await self._ensure_token()
        except Exception as e:
            return {"error": True, "message": self._connection_guidance(e)}

        params: dict[str, Any] = {
            "dataId": data_id,
            "group": group_name,
            "namespaceId": self._namespace(namespace_id),
            "pageNo": page_no,
            "pageSize": min(page_size, 500),
            **self._auth_params(token),
        }

        client = self._get_client()
        resp = await client.get("/nacos/v2/cs/history/list", params=params)
        resp.raise_for_status()
        return resp.json()

    # ══════════════════════════════════════════════════════════════
    # 命名空间 API（v2）
    # ══════════════════════════════════════════════════════════════

    async def list_namespaces(self) -> dict[str, Any]:
        """列出所有命名空间（v2 API）。"""
        try:
            token = await self._ensure_token()
        except Exception as e:
            return {"error": True, "message": self._connection_guidance(e)}

        client = self._get_client()
        resp = await client.get(
            "/nacos/v2/console/namespace/list",
            params=self._auth_params(token),
        )
        resp.raise_for_status()
        return resp.json()

    # ══════════════════════════════════════════════════════════════
    # 服务发现 API（v2）
    # ══════════════════════════════════════════════════════════════

    async def list_services(
        self,
        namespace_id: Optional[str] = None,
        group_name: Optional[str] = None,
        page_no: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """列出注册的服务（v2 API）。"""
        try:
            token = await self._ensure_token()
        except Exception as e:
            return {"error": True, "message": self._connection_guidance(e)}

        params: dict[str, Any] = {
            "namespaceId": self._namespace(namespace_id),
            "pageNo": page_no,
            "pageSize": min(page_size, 500),
            **self._auth_params(token),
        }
        if group_name:
            params["groupName"] = group_name

        client = self._get_client()
        resp = await client.get("/nacos/v2/ns/service/list", params=params)
        resp.raise_for_status()
        return resp.json()

    async def list_instances(
        self,
        service_name: str,
        namespace_id: Optional[str] = None,
        group_name: str = "DEFAULT_GROUP",
        healthy_only: bool = False,
    ) -> dict[str, Any]:
        """查询服务的实例列表（v2 API）。"""
        try:
            token = await self._ensure_token()
        except Exception as e:
            return {"error": True, "message": self._connection_guidance(e)}

        params: dict[str, Any] = {
            "serviceName": service_name,
            "namespaceId": self._namespace(namespace_id),
            "groupName": group_name,
            "healthyOnly": str(healthy_only).lower(),
            **self._auth_params(token),
        }

        client = self._get_client()
        resp = await client.get("/nacos/v2/ns/instance/list", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_service_detail(
        self,
        service_name: str,
        namespace_id: Optional[str] = None,
        group_name: str = "DEFAULT_GROUP",
    ) -> dict[str, Any]:
        """查询服务详情（v2 API）。"""
        try:
            token = await self._ensure_token()
        except Exception as e:
            return {"error": True, "message": self._connection_guidance(e)}

        params: dict[str, str] = {
            "serviceName": service_name,
            "namespaceId": self._namespace(namespace_id),
            "groupName": group_name,
            **self._auth_params(token),
        }

        client = self._get_client()
        resp = await client.get("/nacos/v2/ns/service", params=params)
        resp.raise_for_status()
        return resp.json()


# ── 全局单例 ─────────────────────────────────────────────────────

_client: Optional[NacosClient] = None


def get_client() -> NacosClient:
    """获取全局 NacosClient 单例。"""
    global _client
    if _client is None:
        _client = NacosClient()
    return _client
