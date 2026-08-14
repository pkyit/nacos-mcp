# nacos-mcp

Nacos MCP Server — 让 AI 助手能够查询和管理 Nacos 配置中心与服务注册中心。

支持 Nacos 1.x / 2.x。配置管理走 v1 API，服务发现与命名空间走 v2 API。

## 功能概览

| 能力 | 工具数 | 说明 |
|------|--------|------|
| 配置管理 | 4 | 查询、列表、发布、删除配置 |
| 服务发现 | 3 | 列出服务、查询实例、服务详情 |
| 命名空间 | 1 | 列出所有命名空间 |
| 配置历史 | 1 | 查询配置变更记录 |

## 快速开始

### 前置条件

- Python 3.10+
- 能访问目标 Nacos 服务器的网络

### 安装配置

所有 MCP 客户端配置格式相同，只需修改配置文件路径。

**Claude Code** — 项目 `.mcp.json` 或全局 `~/.claude.json`：

```json
{
  "mcpServers": {
    "nacos": {
      "command": "uvx",
      "args": ["nacos-mcp"],
      "env": {
        "NACOS_HOST": "localhost",
        "NACOS_PORT": "8848",
        "NACOS_USERNAME": "nacos",
        "NACOS_PASSWORD": "nacos",
        "NACOS_NAMESPACE": "dev",
        "NACOS_READ_ONLY": "false"
      }
    }
  }
}
```

**Cursor** — `~/.cursor/mcp.json`

**Claude Desktop** — `claude_desktop_config.json`

**Windsurf** — `~/.codeium/windsurf/mcp_config.json`

**Cline** — VS Code 设置中的 MCP 配置

> 以上客户端配置格式相同，只需把配置放到对应位置即可。

### 环境变量

| 变量 | 说明 | 默认值 | 必填 |
|------|------|--------|------|
| `NACOS_HOST` | Nacos 服务器地址 | `localhost` | 是 |
| `NACOS_PORT` | Nacos 端口 | `8848` | 是 |
| `NACOS_USERNAME` | 登录用户名 | `nacos` | 否 |
| `NACOS_PASSWORD` | 登录密码 | `nacos` | 否 |
| `NACOS_NAMESPACE` | 默认命名空间 ID | `public` | 否 |
| `NACOS_READ_ONLY` | 只读模式（禁止发布/删除） | `false` | 否 |

## 工具列表

### 1. `nacos_list_namespaces` — 列出命名空间

列出 Nacos 所有命名空间及配置数量。

```
帮我看看 Nacos 有哪些命名空间
```

### 2. `nacos_list_configs` — 配置列表

列出指定命名空间下的配置项，支持按 group/dataId 过滤。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `namespace_id` | string | 否 | 命名空间 ID |
| `group` | string | 否 | 按分组名过滤 |
| `data_id` | string | 否 | 按 dataId 过滤（精确匹配） |
| `page_no` | int | 否 | 页码，默认 1 |
| `page_size` | int | 否 | 每页条数，默认 100 |

```
列出 dev 命名空间下所有配置
```

```
查一下 dev 下有没有 group 为 PROD_GROUP 的配置
```

### 3. `nacos_get_config` — 获取配置

获取指定配置的完整内容。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `data_id` | string | 是 | 配置 ID |
| `group_name` | string | 否 | 分组名，默认 DEFAULT_GROUP |
| `namespace_id` | string | 否 | 命名空间 ID |
| `response_format` | string | 否 | `markdown`（默认）或 `json` |

```
获取 dev 下 application-common.yml 的配置内容
```

```
以 JSON 格式返回 datasource.yml 的配置
```

### 4. `nacos_publish_config` — 发布/更新配置

发布新配置或更新已有配置。只读模式下不可用。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `data_id` | string | 是 | 配置 ID |
| `content` | string | 是 | 配置内容 |
| `group_name` | string | 否 | 分组名，默认 DEFAULT_GROUP |
| `namespace_id` | string | 否 | 命名空间 ID |
| `config_type` | string | 否 | 类型：yaml/json/text/properties/xml/html/toml |
| `desc` | string | 否 | 配置描述 |

```
把以下配置发布到 dev 命名空间，dataId 为 redis.yml：
spring:
  redis:
    host: 192.168.1.100
    port: 6379
```

```
更新 application.yml，把 server.port 改成 9090
```

### 5. `nacos_delete_config` — 删除配置

删除指定配置。只读模式下不可用。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `data_id` | string | 是 | 配置 ID |
| `group_name` | string | 否 | 分组名，默认 DEFAULT_GROUP |
| `namespace_id` | string | 否 | 命名空间 ID |

```
删除 dev 下 test-config.yml 这个配置
```

### 6. `nacos_list_config_history` — 配置变更历史

查询配置的变更历史记录。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `data_id` | string | 是 | 配置 ID |
| `group_name` | string | 否 | 分组名，默认 DEFAULT_GROUP |
| `namespace_id` | string | 否 | 命名空间 ID |
| `page_no` | int | 否 | 页码 |
| `page_size` | int | 否 | 每页条数，默认 20 |

```
查看 datasource.yml 的变更历史
```

### 7. `nacos_list_services` — 列出服务

列出 Nacos 中注册的所有服务。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `namespace_id` | string | 否 | 命名空间 ID |
| `group_name` | string | 否 | 按分组过滤 |
| `page_no` | int | 否 | 页码 |
| `page_size` | int | 否 | 每页条数 |

```
Nacos 里注册了哪些服务？
```

```
dev 命名空间下有哪些微服务？
```

### 8. `nacos_list_instances` — 查询服务实例

查询指定服务的所有实例，包含 IP、端口、健康状态、权重、元数据等。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `service_name` | string | 是 | 服务名 |
| `namespace_id` | string | 否 | 命名空间 ID |
| `group_name` | string | 否 | 分组名，默认 DEFAULT_GROUP |
| `healthy_only` | bool | 否 | 是否只返回健康实例 |

```
查看 ruoyi-gateway 有几个实例
```

```
列出 book 服务的所有健康实例
```

### 9. `nacos_get_service_detail` — 查询服务详情

查询服务的详细信息，包括保护阈值、元数据、集群配置等。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `service_name` | string | 是 | 服务名 |
| `namespace_id` | string | 否 | 命名空间 ID |
| `group_name` | string | 否 | 分组名，默认 DEFAULT_GROUP |

```
查看 ruoyi-auth 的服务详情
```

## 使用教程

### 教程 1：日常配置查看

```
用户：帮我看看 Nacos 里有哪些命名空间？
AI：（调用 nacos_list_namespaces）→ 返回表格

用户：dev 下有哪些配置？
AI：（调用 nacos_list_configs, namespace_id="dev"）→ 返回配置列表

用户：看看 gateway 的配置内容
AI：（调用 nacos_get_config, data_id="ruoyi-gateway.yml", namespace_id="dev"）
    → 返回完整 YAML 配置
```

### 教程 2：配置变更排查

```
用户：datasource.yml 最近有没有被改过？
AI：（调用 nacos_list_config_history, data_id="datasource.yml"）
    → 返回变更记录，包含操作人、IP、时间

用户：谁改的？改成什么了？
AI：根据历史记录回答操作人和操作类型（I=新增, U=更新, D=删除）
```

### 教程 3：服务健康检查

```
用户：帮我检查一下所有服务是否健康
AI：
  1.（调用 nacos_list_services）→ 获取服务列表
  2. 逐个（调用 nacos_list_instances）→ 检查每个服务的实例健康状态
  3. 汇总报告：哪些服务全健康、哪些有不健康实例
```

### 教程 4：发布新配置

```
用户：帮我在 dev 下新建一个 oss.yml 配置：
      oss:
        endpoint: oss-cn-hangzhou.aliyuncs.com
        bucket: my-bucket
AI：（调用 nacos_publish_config, data_id="oss.yml", content="...", namespace_id="dev"）
    → 返回发布成功确认

用户：确认一下发布的内容对不对
AI：（调用 nacos_get_config, data_id="oss.yml"）→ 返回刚发布的内容
```

### 教程 5：只读模式（生产环境保护）

生产环境建议开启只读模式，防止 AI 误操作修改或删除配置：

```json
{
  "env": {
    "NACOS_HOST": "nacos-prod.example.com",
    "NACOS_PORT": "8848",
    "NACOS_USERNAME": "readonly",
    "NACOS_PASSWORD": "your-password",
    "NACOS_NAMESPACE": "prod",
    "NACOS_READ_ONLY": "true"
  }
}
```

开启后 `nacos_publish_config` 和 `nacos_delete_config` 会返回"只读模式，禁止操作"，其余查询工具正常可用。

## 连接失败排查

如果 MCP 工具返回连接失败的引导信息，按以下步骤排查：

1. **检查 Nacos 是否在线** — 浏览器访问 `http://{NACOS_HOST}:{NACOS_PORT}/nacos`
2. **检查网络连通性** — `ping {NACOS_HOST}` 或 `telnet {NACOS_HOST} {NACOS_PORT}`
3. **检查账号密码** — 默认 `nacos`/`nacos`，修改后需要同步更新环境变量
4. **检查命名空间 ID** — Nacos 控制台的命名空间 ID（不是名称）

## 架构说明

```
nacos-mcp
├── client.py    # NacosClient 单例，鉴权 + 持久化 httpx 连接池 + 所有 API
└── server.py    # 9 个 MCP 工具定义
```

- **配置管理走 v1 API** — `/nacos/v1/cs/configs`（兼容性好，有配置列表接口）
- **服务发现走 v2 API** — `/nacos/v2/ns/`（字段更丰富，包含 ephemeral、metadata 等）
- **命名空间走 v2 API** — `/nacos/v2/console/namespace/list`
- **连接池管理** — httpx AsyncClient 持久化，空闲 5 分钟自动释放
- **错误处理** — 所有异常捕获为字符串返回，MCP 进程不会崩溃

## 开发

```bash
git clone https://github.com/pkyit/nacos-mcp.git
cd nacos-mcp

# 安装依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 本地启动 MCP Server
nacos-mcp
```

## License

MIT
