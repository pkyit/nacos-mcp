"""Nacos MCP Server

提供 9 个工具，覆盖配置管理、服务发现、命名空间查询。
配置管理走 v1 API，服务发现/命名空间走 v2 API。
"""

import json
from enum import Enum
from typing import Any, Optional, cast

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from .client import NacosClient, get_client

mcp = FastMCP("nacos-mcp")


# ── 公共模型 ─────────────────────────────────────────────────────


class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


class ConfigType(str, Enum):
    TEXT = "text"
    JSON = "json"
    YAML = "yaml"
    XML = "xml"
    PROPERTIES = "properties"
    HTML = "html"
    TOML = "toml"


class GetConfigInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    data_id: str = Field(
        ...,
        description="配置 ID，如 'application.yaml'",
        min_length=1,
        max_length=256,
    )
    group_name: str = Field(
        default="DEFAULT_GROUP",
        description="配置分组",
        min_length=1,
        max_length=128,
    )
    namespace_id: Optional[str] = Field(default=None, description="命名空间 ID，可选")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="输出格式：markdown 或 json",
    )


class ListConfigsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    namespace_id: Optional[str] = Field(default=None, description="命名空间 ID")
    group: Optional[str] = Field(default=None, description="按分组名过滤")
    data_id: Optional[str] = Field(default=None, description="按 dataId 过滤（精确匹配）")
    page_no: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=100, ge=1, le=500, description="每页条数")


class PublishConfigInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    data_id: str = Field(..., description="配置 ID", min_length=1, max_length=256)
    group_name: str = Field(
        default="DEFAULT_GROUP",
        description="配置分组",
        min_length=1,
        max_length=128,
    )
    namespace_id: Optional[str] = Field(default=None, description="命名空间 ID")
    content: str = Field(..., description="配置内容", min_length=1)
    config_type: ConfigType = Field(default=ConfigType.YAML, description="配置类型")
    desc: Optional[str] = Field(default=None, description="配置描述")


class DeleteConfigInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    data_id: str = Field(..., description="配置 ID", min_length=1, max_length=256)
    group_name: str = Field(
        default="DEFAULT_GROUP",
        description="配置分组",
        min_length=1,
        max_length=128,
    )
    namespace_id: Optional[str] = Field(default=None, description="命名空间 ID")


class ConfigHistoryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    data_id: str = Field(..., description="配置 ID", min_length=1, max_length=256)
    group_name: str = Field(
        default="DEFAULT_GROUP",
        description="配置分组",
        min_length=1,
        max_length=128,
    )
    namespace_id: Optional[str] = Field(default=None, description="命名空间 ID")
    page_no: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=500, description="每页条数")


class ListServicesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    namespace_id: Optional[str] = Field(default=None, description="命名空间 ID")
    group_name: Optional[str] = Field(default=None, description="按分组过滤")
    page_no: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=100, ge=1, le=500, description="每页条数")


class ListInstancesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    service_name: str = Field(..., description="服务名", min_length=1)
    namespace_id: Optional[str] = Field(default=None, description="命名空间 ID")
    group_name: str = Field(
        default="DEFAULT_GROUP",
        description="分组名",
        min_length=1,
        max_length=128,
    )
    healthy_only: bool = Field(default=False, description="是否只返回健康实例")


class ServiceDetailInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    service_name: str = Field(..., description="服务名", min_length=1)
    namespace_id: Optional[str] = Field(default=None, description="命名空间 ID")
    group_name: str = Field(
        default="DEFAULT_GROUP",
        description="分组名",
        min_length=1,
        max_length=128,
    )


class NamespacesInput(BaseModel):
    """无必填参数，但保留模型以兼容 MCP 框架。"""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")


# ── 错误处理 ─────────────────────────────────────────────────────


def _safe_error(e: Exception) -> str:
    """兜底错误处理，永远返回字符串，不崩溃。"""
    try:
        c = get_client()
        return c._connection_guidance(e)
    except Exception:
        return f"未知错误：{type(e).__name__}: {e}"


# ── 结果格式化 ───────────────────────────────────────────────────


def _format_config(data: dict[str, Any], fmt: ResponseFormat) -> str:
    if fmt == ResponseFormat.JSON:
        return json.dumps(data, ensure_ascii=False, indent=2)

    content = data.get("content", "") or ""
    config_type = data.get("type") or "yaml"
    lines = [
        f"**Data ID:** {data.get('dataId', 'N/A')}",
        f"**Group:** {data.get('groupName', 'N/A')}",
        f"**Namespace:** {data.get('namespaceId', 'N/A')}",
        "",
        f"```{config_type}",
        content,
        "```",
    ]
    return "\n".join(lines)


def _format_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    headers = [h for h, _ in columns]
    keys = [k for _, k in columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        vals = [str(row.get(k, "")) for k in keys]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
# 工具定义
# ══════════════════════════════════════════════════════════════════


@mcp.tool(
    name="nacos_list_namespaces",
    annotations=cast(
        Any,
        {"title": "列出命名空间", "readOnlyHint": True, "idempotentHint": True},
    ),
)
async def nacos_list_namespaces(params: NamespacesInput) -> str:
    """列出 Nacos 所有命名空间及其配置数量。"""
    try:
        client = get_client()
        result = await client.list_namespaces()

        if result.get("error"):
            return result["message"]

        data = result.get("data", [])
        if not data:
            return "未找到任何命名空间"

        table = _format_table(
            data,
            [
                ("命名空间 ID", "namespace"),
                ("名称", "namespaceShowName"),
                ("描述", "namespaceDesc"),
                ("配置数", "configCount"),
                ("配额", "quota"),
            ],
        )
        return f"共 {len(data)} 个命名空间：\n\n{table}"

    except Exception as e:
        return _safe_error(e)


@mcp.tool(
    name="nacos_list_configs",
    annotations=cast(
        Any,
        {"title": "列出配置列表", "readOnlyHint": True, "idempotentHint": True},
    ),
)
async def nacos_list_configs(params: ListConfigsInput) -> str:
    """列出 Nacos 中的配置项，支持按 group/dataId 过滤。"""
    try:
        client = get_client()
        result = await client.list_configs(
            namespace_id=params.namespace_id,
            group=params.group,
            data_id=params.data_id,
            page_no=params.page_no,
            page_size=params.page_size,
        )

        if result.get("error"):
            return result["message"]

        items = result.get("pageItems", [])
        total = result.get("totalCount", 0)

        if not items:
            ns = params.namespace_id or client.default_namespace
            return f"命名空间 {ns} 下未找到配置"

        table = _format_table(
            items,
            [
                ("Data ID", "dataId"),
                ("Group", "group"),
                ("Type", "type"),
                ("ID", "id"),
            ],
        )
        return f"共 {total} 条配置（第 {params.page_no} 页）：\n\n{table}"

    except Exception as e:
        return _safe_error(e)


@mcp.tool(
    name="nacos_get_config",
    annotations=cast(
        Any,
        {"title": "获取配置", "readOnlyHint": True, "idempotentHint": True},
    ),
)
async def nacos_get_config(params: GetConfigInput) -> str:
    """获取 Nacos 中指定配置的内容。"""
    try:
        client = get_client()
        data = await client.get_config(
            data_id=params.data_id,
            group_name=params.group_name,
            namespace_id=params.namespace_id,
        )

        if data.get("error"):
            return data["message"]

        if data.get("content") is None:
            ns = params.namespace_id or client.default_namespace
            return f"配置不存在：dataId={params.data_id}, group={params.group_name}, namespace={ns}"

        return _format_config(data, params.response_format)

    except Exception as e:
        return _safe_error(e)


@mcp.tool(
    name="nacos_publish_config",
    annotations=cast(
        Any,
        {"title": "发布/更新配置", "readOnlyHint": False, "idempotentHint": True},
    ),
)
async def nacos_publish_config(params: PublishConfigInput) -> str:
    """发布新配置或更新已有配置。只读模式下不可用。"""
    try:
        client = get_client()
        if client.read_only:
            return "当前为只读模式，禁止发布配置"

        result = await client.publish_config(
            data_id=params.data_id,
            content=params.content,
            group_name=params.group_name,
            namespace_id=params.namespace_id,
            config_type=params.config_type.value,
            desc=params.desc,
        )

        if result.get("error"):
            return result["message"]

        if result.get("success"):
            ns = params.namespace_id or client.default_namespace
            return (
                f"配置发布成功\n\n"
                f"| 属性 | 值 |\n|---|---|\n"
                f"| Data ID | {params.data_id} |\n"
                f"| Group | {params.group_name} |\n"
                f"| Namespace | {ns} |\n"
                f"| Type | {params.config_type.value} |"
            )
        return f"配置发布失败：{result.get('message', '未知原因')}"

    except Exception as e:
        return _safe_error(e)


@mcp.tool(
    name="nacos_delete_config",
    annotations=cast(
        Any,
        {"title": "删除配置", "readOnlyHint": False, "idempotentHint": True},
    ),
)
async def nacos_delete_config(params: DeleteConfigInput) -> str:
    """删除指定配置。只读模式下不可用。"""
    try:
        client = get_client()
        if client.read_only:
            return "当前为只读模式，禁止删除配置"

        result = await client.delete_config(
            data_id=params.data_id,
            group_name=params.group_name,
            namespace_id=params.namespace_id,
        )

        if result.get("error"):
            return result["message"]

        if result.get("success"):
            ns = params.namespace_id or client.default_namespace
            return f"配置已删除：dataId={params.data_id}, group={params.group_name}, namespace={ns}"
        return f"配置删除失败：{result.get('message', '未知原因')}"

    except Exception as e:
        return _safe_error(e)


@mcp.tool(
    name="nacos_list_config_history",
    annotations=cast(
        Any,
        {"title": "配置变更历史", "readOnlyHint": True, "idempotentHint": True},
    ),
)
async def nacos_list_config_history(params: ConfigHistoryInput) -> str:
    """查询配置的变更历史列表。"""
    try:
        client = get_client()
        result = await client.list_config_history(
            data_id=params.data_id,
            group_name=params.group_name,
            namespace_id=params.namespace_id,
            page_no=params.page_no,
            page_size=params.page_size,
        )

        if result.get("error"):
            return result["message"]

        data = result.get("data", {})
        items = data.get("pageItems", [])
        total = data.get("totalCount", 0)

        if not items:
            return f"未找到配置 {params.data_id} 的变更历史"

        table = _format_table(
            items,
            [
                ("操作", "opType"),
                ("操作人", "srcUser"),
                ("来源 IP", "srcIp"),
                ("修改时间", "lastModifiedTime"),
            ],
        )
        return f"配置 {params.data_id} 共 {total} 条变更记录（第 {params.page_no} 页）：\n\n{table}"

    except Exception as e:
        return _safe_error(e)


@mcp.tool(
    name="nacos_list_services",
    annotations=cast(
        Any,
        {"title": "列出服务", "readOnlyHint": True, "idempotentHint": True},
    ),
)
async def nacos_list_services(params: ListServicesInput) -> str:
    """列出 Nacos 中注册的所有服务。"""
    try:
        client = get_client()
        result = await client.list_services(
            namespace_id=params.namespace_id,
            group_name=params.group_name,
            page_no=params.page_no,
            page_size=params.page_size,
        )

        if result.get("error"):
            return result["message"]

        data = result.get("data", {})
        services = data.get("services", [])
        count = data.get("count", 0)

        if not services:
            ns = params.namespace_id or client.default_namespace
            return f"命名空间 {ns} 下未注册任何服务"

        lines = [f"共 {count} 个服务（第 {params.page_no} 页）：\n"]
        for svc in services:
            lines.append(f"- **{svc}**")
        return "\n".join(lines)

    except Exception as e:
        return _safe_error(e)


@mcp.tool(
    name="nacos_list_instances",
    annotations=cast(
        Any,
        {"title": "查询服务实例", "readOnlyHint": True, "idempotentHint": True},
    ),
)
async def nacos_list_instances(params: ListInstancesInput) -> str:
    """查询指定服务的实例列表，包含 IP、端口、健康状态、元数据等。"""
    try:
        client = get_client()
        result = await client.list_instances(
            service_name=params.service_name,
            namespace_id=params.namespace_id,
            group_name=params.group_name,
            healthy_only=params.healthy_only,
        )

        if result.get("error"):
            return result["message"]

        data = result.get("data", {})
        hosts = data.get("hosts", [])

        if not hosts:
            return f"服务 {params.service_name} 没有实例"

        table = _format_table(
            hosts,
            [
                ("IP", "ip"),
                ("端口", "port"),
                ("健康", "healthy"),
                ("可用", "enabled"),
                ("临时", "ephemeral"),
                ("权重", "weight"),
                ("集群", "clusterName"),
            ],
        )
        return f"服务 {params.service_name} 共 {len(hosts)} 个实例：\n\n{table}"

    except Exception as e:
        return _safe_error(e)


@mcp.tool(
    name="nacos_get_service_detail",
    annotations=cast(
        Any,
        {"title": "查询服务详情", "readOnlyHint": True, "idempotentHint": True},
    ),
)
async def nacos_get_service_detail(params: ServiceDetailInput) -> str:
    """查询服务的详细信息，包括集群配置、保护阈值、元数据等。"""
    try:
        client = get_client()
        result = await client.get_service_detail(
            service_name=params.service_name,
            namespace_id=params.namespace_id,
            group_name=params.group_name,
        )

        if result.get("error"):
            return result["message"]

        if result.get("code") != 0:
            return f"查询失败：{result.get('message', '未知错误')}"

        data = result.get("data", {})
        lines = [
            f"**服务详情：{params.service_name}**\n",
            "| 属性 | 值 |",
            "|---|---|",
            f"| 命名空间 | {data.get('namespace', 'N/A')} |",
            f"| 分组 | {data.get('groupName', 'N/A')} |",
            f"| 服务名 | {data.get('name', params.service_name)} |",
            f"| 保护阈值 | {data.get('protectThreshold', 'N/A')} |",
            f"| 元数据 | {json.dumps(data.get('metadata', {}), ensure_ascii=False)} |",
        ]
        return "\n".join(lines)

    except Exception as e:
        return _safe_error(e)


# ── 入口 ─────────────────────────────────────────────────────────


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
