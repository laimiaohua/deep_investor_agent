# Deep Investor Agent

Deep Investor Agent 是一个基于 AI 的智能投资决策系统，通过多个专业投资智能体协同工作，为股票投资提供分析和决策建议。本项目基于 [ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) 项目改造而来，采用 MIT 开源协议。

### 主要优化与改造

相比原项目 [ai-hedge-fund](https://github.com/virattt/ai-hedge-fund)，本项目进行了以下重要优化与改造：

1. **🌏 扩展市场覆盖范围**: 在原有美股分析的基础上，新增了对 **A股** 和 **港股** 市场的支持，使系统能够分析中国内地和香港市场的股票
2. **🇨🇳 增加中国投资大师智能体**: 新增了 5 个中国投资大师智能体（段永平、张磊、邱国鹭、冯柳、但斌），这些智能体基于中国市场的投资理念和实践，能够更好地理解和分析中国市场的投资机会
3. **📝 多语言支持**: 增加了 **简体中文** 和 **繁体中文** 支持，方便中国大陆、香港、台湾等地区的投资者使用，提升了系统的本地化体验
4. **📄 可读性改进**: 技术分析师、基本面分析师、情绪分析师、估值分析师的分析结果现在以**可读的文字描述**形式返回，而不是原始的JSON格式，大大提升了用户体验和可读性

> **⚠️ 重要提示**: 本项目仅用于**教育和研究目的**，不用于实际交易或投资。系统不会执行任何实际交易。

## 项目简介

Deep Investor Agent 是一个概念验证项目，旨在探索使用 AI 进行投资决策的可能性。系统通过多个模拟不同投资风格的智能体协同工作，从多个维度分析股票，最终生成投资建议。

本项目在 [ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) 的基础上，针对中国市场的特点和需求进行了深度定制和优化，不仅支持美股分析，还扩展了对 A股和港股的支持，并增加了中国投资大师的投资理念，为中文用户提供了更好的使用体验。

### 核心特性

- 🤖 **多智能体协同**: 23 个专业投资智能体，涵盖价值投资、成长投资、技术分析等多种投资风格
  - 包含 12 个国际投资大师智能体（巴菲特、芒格、达摩达兰等）
  - 包含 5 个中国投资大师智能体（段永平、张磊、邱国鹭、冯柳、但斌）
  - 包含 6 个专业分析智能体（估值、情绪、基本面、技术、风险管理、组合管理）
- 📊 **多维度分析**: 基本面分析、技术分析、估值分析、市场情绪分析
- 🌍 **多市场支持**: 支持美股、A股、港股市场
  - 美股：支持所有美股股票代码（如 AAPL、MSFT、NVDA 等）
  - A股：支持沪深两市股票代码（如 000001、600000 等）
  - 港股：支持港股股票代码（如 00700、09988 等）
- 🌐 **多语言支持**: 支持简体中文、繁体中文，方便中国、香港、台湾等地区的投资者使用
- 🎯 **风险管理**: 内置风险管理和投资组合管理模块
- 💻 **多种使用方式**: 支持命令行界面和 Web 应用界面
- 🔄 **回测功能**: 内置回测引擎，可以验证投资策略的历史表现

## 投资智能体列表

本系统包含以下 23 个投资智能体：

### 国际投资大师智能体

1. **Aswath Damodaran Agent** - 估值大师，专注于故事、数据和严谨的估值方法
2. **Ben Graham Agent** - 价值投资之父，只买入具有安全边际的隐藏宝石
3. **Bill Ackman Agent** - 激进投资者，采取大胆立场并推动变革
4. **Cathie Wood Agent** - 成长投资女王，相信创新和颠覆的力量
5. **Charlie Munger Agent** - 巴菲特合伙人，只以合理价格买入优秀企业
6. **Michael Burry Agent** - 《大空头》中的逆向投资者，寻找深度价值
7. **Mohnish Pabrai Agent** - Dhandho 投资者，寻找低风险的双倍回报
8. **Peter Lynch Agent** - 实用投资者，在日常业务中寻找"十倍股"
9. **Phil Fisher Agent** - 严谨的成长投资者，使用深入的"小道消息"研究
10. **Rakesh Jhunjhunwala Agent** - 印度大牛
11. **Stanley Druckenmiller Agent** - 宏观传奇，寻找具有增长潜力的不对称机会
12. **Warren Buffett Agent** - 奥马哈先知，以合理价格寻求优秀公司

### 中国投资大师智能体

13. **段永平 Agent** - 中国长期价值投资者，专注于高质量消费和互联网公司
14. **张磊 Agent** - 中国长期复利投资者，强调"好公司 + 好价格 + 长时间"
15. **邱国鹭 Agent** - 中国宏观和周期价值投资者，结合自上而下和自下而上的思维
16. **冯柳 Agent** - 中国逆向、耐心投资者，专注于预期差距和静默的基本面改善
17. **但斌 Agent** - 中国价值投资者，偏爱领先消费和优质蓝筹公司作为"时间的朋友"

### 专业分析智能体

18. **Valuation Agent** - 计算股票内在价值并生成交易信号
19. **Sentiment Agent** - 分析市场情绪并生成交易信号
20. **Fundamentals Agent** - 分析基本面数据并生成交易信号
21. **Technicals Agent** - 分析技术指标并生成交易信号
22. **Risk Manager** - 计算风险指标并设置仓位限制
23. **Portfolio Manager** - 做出最终交易决策并生成订单

## 免责声明

本项目仅用于**教育和研究目的**。

- ❌ 不用于实际交易或投资
- ❌ 不提供投资建议或保证
- ❌ 创建者不对财务损失承担责任
- ✅ 投资决策请咨询财务顾问
- ⚠️ 过往表现不代表未来结果

使用本软件即表示您同意仅将其用于学习目的。

## 目录

- [快速开始](#快速开始)
- [安装指南](#安装指南)
- [使用方式](#使用方式)
  - [命令行界面](#命令行界面)
  - [Web 应用](#web-应用)
- [生产环境部署](#生产环境部署)
- [功能特性](#功能特性)
- [贡献指南](#贡献指南)
- [许可证](#许可证)

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/deep_investor_agent.git
cd deep_investor_agent
```

### 2. 安装依赖

```bash
# 安装 Poetry (如果尚未安装)
curl -sSL https://install.python-poetry.org | python3 -

# 安装项目依赖
poetry install
```

### 3. 配置 API 密钥

创建 `.env` 文件并配置必要的 API 密钥：

```bash
# 复制示例文件
cp .env.example .env
```

编辑 `.env` 文件，添加以下 API 密钥：

```bash
# LLM API 密钥 (至少需要配置一个)
OPENAI_API_KEY=your-openai-api-key
# 或
GROQ_API_KEY=your-groq-api-key
# 或
ANTHROPIC_API_KEY=your-anthropic-api-key
# 或
DEEPSEEK_API_KEY=your-deepseek-api-key

# 美股数据 API 密钥
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key

# Massive 数据源 API 密钥（备用美股数据源）
MASSIVE_API_KEY=your-massive-api-key

# OpenBB 数据源（免费，可选）
# 如果启用，系统会优先使用 OpenBB 获取美股数据
# 安装方法：pip install openbb 或 poetry add openbb
USE_OPENBB=true  # 设置为 true 启用 OpenBB（默认 false）

# A股/港股数据 API 密钥
DEEPALPHA_API_KEY=your-deepalpha-api-key
```

**重要提示**:
- 必须至少配置一个 LLM API 密钥（如 `OPENAI_API_KEY`、`GROQ_API_KEY` 等）
- **美股数据源优先级**：
  - **价格数据**：
    1. **OpenBB**（免费，推荐）：如果启用 `USE_OPENBB=true` 且已安装 OpenBB，系统会优先使用 OpenBB 获取美股数据。OpenBB 是免费的开源金融数据平台，集成了多个数据源，无需 API 密钥。
    2. **Financial Datasets API**：主要付费数据源，需要配置 `FINANCIAL_DATASETS_API_KEY`
    3. **Polygon.io (Massive API)**：备用付费数据源，当主要数据源不可用时自动切换，需要配置 `MASSIVE_API_KEY`。注意：Polygon.io使用不同的API端点和认证方式（`https://api.polygon.io`，使用query参数 `?apikey=xxx`），代码已正确集成。
    4. **yfinance**（免费，自动备用）：当主要API失败时，系统会自动使用yfinance作为备用数据源。yfinance是免费的Python库，可以获取美股价格和财务数据，无需API密钥。
  - **财务数据**（财务指标、财务报表等）：
    1. **OpenBB**（免费，推荐）：如果启用 `USE_OPENBB=true` 且已安装 OpenBB，系统会优先使用 OpenBB 获取美股财务数据。
    2. **yfinance**（免费，主要数据源）：yfinance是美股财务数据的主要数据源，无需API密钥，可以获取财务指标、财务报表等数据。
    3. **Financial Datasets API**：付费备用数据源，当yfinance不可用时使用，需要配置 `FINANCIAL_DATASETS_API_KEY`
- 美股数据：AAPL、GOOGL、MSFT、NVDA、TSLA 的数据在某些数据源中是免费的，不需要 API 密钥
- A股/港股数据：如需分析 A 股（如 000001、600000）或港股，需要配置 `DEEPALPHA_API_KEY`

### 4. 运行示例

```bash
# 使用命令行界面分析股票
poetry run python src/main.py --ticker AAPL,MSFT,NVDA

# 使用本地 LLM (Ollama)
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --ollama

# 运行回测
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA
```

## 安装指南

### 系统要求

- Python 3.11 或更高版本
- Poetry (Python 包管理器)
- 至少一个 LLM API 密钥

### 详细安装步骤

1. **安装 Poetry**

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. **安装项目依赖**

```bash
poetry install
```

3. **配置环境变量**

创建 `.env` 文件并添加必要的 API 密钥（见[快速开始](#快速开始)部分）

## 使用方式

### 命令行界面

命令行界面提供更细粒度的控制，适合自动化、脚本和集成场景。

#### 基本用法

```bash
# 分析指定股票
poetry run python src/main.py --ticker AAPL,MSFT,NVDA

# 指定时间范围
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01

# 使用本地 LLM (Ollama)
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --ollama

# 显示详细推理过程
poetry run python src/main.py --ticker AAPL --show-reasoning
```

#### 回测功能

```bash
# 运行回测
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA

# 回测指定时间范围
poetry run python src/backtester.py --ticker AAPL --start-date 2024-01-01 --end-date 2024-12-31
```

### Web 应用

Web 应用提供友好的图形界面，推荐给偏好可视化界面的用户。

详细的 Web 应用安装和运行说明请参考 [app/README.md](app/README.md)。

#### 启动 Web 应用

```bash
# 启动后端服务
cd app/backend
poetry run uvicorn main:app --reload

# 启动前端服务 (新终端窗口)
cd app/frontend
npm install
npm run dev
```

访问 `http://localhost:5173` 使用 Web 界面。

#### Web 应用使用说明

Web 应用提供了完整的使用说明功能，帮助用户快速上手：

1. **打开使用说明**：
   - 点击顶部工具栏中的"使用说明"图标（❓）
   - 或在设置页面底部点击"使用说明"链接

2. **使用说明内容**：
   - **配置 API 密钥**：详细说明如何配置金融数据 API 密钥（Financial Datasets API 用于美股，Massive API 作为备用美股数据源，DeepAlpha API 用于 A 股和港股）和语言模型 API 密钥
   - **使用默认流程**：介绍如何创建和使用系统预设的分析流程
   - **流程定制**：说明如何基于组件自定义分析流程，包括添加节点、连接节点等操作
   - **语言切换**：说明如何切换系统语言（简体中文、繁体中文、English）

3. **快速访问**：
   - 使用说明以标签页形式打开，可以随时切换查看
   - 支持多语言，会根据当前系统语言自动显示对应版本

## 生产环境部署

本项目支持使用 Docker 和 Nginx 部署到生产环境。详细的部署指南请参考 [docker/DEPLOYMENT.md](docker/DEPLOYMENT.md)。

### Docker 目录精简说明
- 仅保留 `docker-compose.prod.yml`（内置 Nginx）与 `docker-compose.prod-no-nginx.yml`（外部 Nginx）两条生产路径
- 旧版单容器/命令行运行文件已移除：`docker-compose.yml`、`Dockerfile`（单容器）、`run.sh`、`run.bat`、`docker-compose.prod-alt.yml`
- 常用脚本：`deploy.sh`、`deploy-no-nginx.sh`、`setup-ssl.sh`、`clean-docker.sh`，诊断脚本：`check-ports.sh`、`check-existing-nginx.sh`、`check-dns.sh`

### 快速部署

1. **准备环境**
   ```bash
   # 确保已安装 Docker 和 Docker Compose
   docker --version
   docker-compose --version
   ```

2. **配置环境变量**
   ```bash
   # 复制并编辑 .env 文件
   cp .env.example .env
   nano .env
   ```

3. **配置 SSL 证书**
   ```bash
   # 将 SSL 证书放置在 docker/nginx/ssl/ 目录
   mkdir -p docker/nginx/ssl
   cp /path/to/fullchain.pem docker/nginx/ssl/
   cp /path/to/privkey.pem docker/nginx/ssl/
   ```

4. **部署应用**
   ```bash
   cd docker
   chmod +x deploy.sh
   ./deploy.sh
   ```

### 部署架构

```
Internet
   |
   v
Nginx (HTTPS:443)
   |
   +---> Frontend (Vue3/React)
   |
   +---> Backend API (/api/*)
   |      |
   |      v
   |    FastAPI (8000)
   |
   +---> Documentation (/documentation)
         |
         v
       FastAPI Docs
```

### 访问地址

部署成功后，可以通过以下地址访问：

- **前端应用**: `https://deepinvestoragent.gravitechinnovations.com`
- **API 文档**: `https://deepinvestoragent.gravitechinnovations.com/documentation`
- **API 端点**: `https://deepinvestoragent.gravitechinnovations.com/api`
- **健康检查**: `https://deepinvestoragent.gravitechinnovations.com/api/health`（Nginx 需使用 `location /api/ { proxy_pass http://127.0.0.1:8000/; }` 去掉 `/api` 前缀）

### 服务管理

```bash
cd docker

# 查看服务状态
docker-compose -f docker-compose.prod.yml ps

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f

# 重启服务
docker-compose -f docker-compose.prod.yml restart

# 停止服务
docker-compose -f docker-compose.prod.yml down

# 更新应用
git pull
docker-compose -f docker-compose.prod.yml up -d --build
```

更多详细信息请参考 [docker/DEPLOYMENT.md](docker/DEPLOYMENT.md)。

## 功能特性

### 分析报告优化

- **详细的分析依据和结论**: 所有智能体会生成详细的分析报告（200-500 字符），包含：
  - 核心分析依据：具体的数据指标、财务表现、估值水平
  - 关键因素分析：业务模式、竞争优势、管理质量等
  - 投资逻辑：为什么做出这个判断，基于哪些关键因素
  - 风险提示：需要注意的风险点
  - 明确结论：投资建议和理由

### 多市场数据支持

- **独立的 API Key 配置**: 支持为美股和 A 股/港股配置独立的 API keys
- **备用数据源支持**: 支持配置 Massive API 作为备用美股数据源，当主要数据源不可用时自动切换
- **改进的错误处理**: 提供清晰的错误信息，帮助快速定位和解决问题
- **自动数据源选择**: 系统会根据股票代码自动选择正确的数据源，并支持自动故障转移
- **A股港股行情数据接口**: A股和港股行情数据统一使用 `STOCK_KLINE` 接口获取，接口地址为 `/api/data_query?function=STOCK_KLINE&security_code=股票代码&apikey=YOUR_API_KEY`，确保能够获取最新的行情数据
- **yfinance支持**: 
  - **财务数据主要数据源**：yfinance是美股财务数据（财务指标、财务报表等）的主要数据源，无需API密钥，免费使用。
  - **价格数据备用数据源**：当主要价格数据API失败时，yfinance会自动作为备用数据源。
  - 已验证可以成功获取PLTR等美股数据（价格、财务信息、财务报表等）。
  - **多期间财务指标**：yfinance现在可以返回多个历史期间的财务指标（最多4年），支持竞争护城河分析。
  - **管理层质量数据**：从yfinance现金流表提取股票回购、分红等数据，支持管理层质量分析。
  - **内在价值计算**：支持从FinancialMetrics中的自由现金流数据计算内在价值和安全边际。
- **Polygon.io (Massive API) 支持**: 已正确集成Polygon.io API，使用正确的端点和认证方式。当主要API失败时自动切换到Polygon.io作为备用数据源
- **巴菲特智能体数据完整性改进**：
  - **竞争护城河分析**：现在可以从yfinance获取多个历史期间的财务指标，支持分析ROE一致性、营业利润率稳定性等护城河指标。
  - **管理层质量分析**：现在可以从yfinance现金流表提取股票回购、分红等数据，评估管理层的股东友好程度。
  - **内在价值和安全边际计算**：即使没有完整的财务报表数据，也可以从FinancialMetrics中的自由现金流数据计算内在价值和安全边际。

### 完整的中文本地化支持

- **进度状态消息完整翻译**: 所有智能体的数据获取和分析过程中的状态消息都已完整翻译为中文
  - 数据获取阶段：如"正在获取财务指标"、"正在获取市值"等
  - 分析阶段：如"正在分析基本面"、"正在分析竞争护城河"等
  - 计算阶段：如"正在计算内在价值"、"正在计算WACC和增强DCF"等
  - 生成阶段：如"正在生成巴菲特风格分析"、"正在生成芒格风格分析"等
- **智能体语言自动设置**: 所有智能体都会根据用户选择的语言自动设置进度显示语言
- **LLM 输出强制中文**: 在中文版本中，所有 LLM 生成的分析报告和推理过程都强制使用中文输出
- **中文名称优化**: 统一群组名称翻译，现使用「经典分析」（Data Wizards）、「独特观点」（Market Mavericks）、「价值投资」（Value Investors），确保界面术语易懂且符合中文习惯

### 用户使用说明功能

- **内置使用说明**: Web 应用提供了完整的使用说明功能，帮助用户快速上手
  - 可通过顶部工具栏的"使用说明"图标快速访问
  - 也可在设置页面底部找到使用说明入口
  - 使用说明以标签页形式打开，支持多语言显示
- **详细的操作指南**: 使用说明包含以下内容：
  - API 密钥配置指南（金融数据密钥和语言模型密钥）
  - 默认流程使用方法
  - 基于组件的流程定制教程
  - 语言切换操作说明

### 健壮的错误处理和重试机制

- **自动重试机制**: API 请求失败时会自动重试（最多 3 次），支持：
  - 网络超时错误（自动重试，指数退避策略）
  - 连接错误（自动重试，指数退避策略）
  - 服务器错误（5xx，自动重试）
  - 频率限制（429，自动重试，延迟退避）
- **容错处理**: 单个股票的数据获取失败不会影响其他股票的分析
  - 如果某个股票的数据获取失败，会跳过该股票并继续处理其他股票
  - 失败的股票会返回中性信号（neutral）和详细的错误说明
  - 确保即使部分数据源不可用，也能完成其他股票的分析
- **港股数据缺失处理**: 针对港股数据源的特殊处理机制
  - **自动降级**: 当港股某个接口（如 BALANCE_SHEET）的所有候选接口都失败时，系统会返回空列表而不是抛出异常
  - **继续分析**: 即使部分数据缺失（如资产负债表），智能体仍会使用可用数据（如财务指标）继续分析
  - **中性信号**: 当关键数据（如财务指标）完全缺失时，智能体会生成中性信号（neutral），而不是导致整个分析任务失败
  - **错误记录**: 数据缺失信息会被记录在分析结果中，帮助用户了解数据可用性
  - **多接口尝试**: 对于港股，系统会尝试多个候选接口（如 HKSTK_BALANCE_SHEET_GENE、HKSTK_BALANCE_BANK、HKSTK_BALANCE_INSUR），只有全部失败时才返回空数据
- **友好的错误提示**: 提供详细的中文错误信息，帮助快速定位问题
  - API 余额不足（402）：提示充值
  - API 密钥无效（401）：提示检查配置
  - 网络错误：提示检查网络连接
  - 超时错误：自动重试，无需手动干预
  - 数据缺失：提示数据不可用，但不影响其他股票的分析
- **降级策略**: 当主要数据源失败时，尝试使用备用数据源或返回默认值
  - A 股/港股数据获取失败时，会尝试使用备用 API
  - 部分数据缺失时，使用可用数据进行部分分析
  - 港股数据缺失时，智能体使用可用数据生成分析结果，而不是直接失败

### 分析结果展示与进度

- **LLM 输出**: 当前版本已关闭流式输出，分析结果在完成后一次性展示
- **实时进度更新**: 仍保留进度状态更新（获取数据、分析步骤、生成阶段），但不再流式展示内容
- **智能状态显示**: 根据分析进度自动更新节点状态
  - 进行中：显示加载动画和当前步骤
  - 完成：显示完成状态和最终结果
  - 错误：显示错误信息和失败原因

### 交易决策逻辑说明

- **分析师信号 vs 交易决策**: 系统区分了两种不同的概念：
  - **分析师信号（看多/看空/中性）**: 这是各个智能体对股票未来走势的**市场观点**，表示对股票基本面的判断
  - **交易决策（买入/卖出/持有）**: 这是投资组合管理器根据**分析师信号和当前持仓**做出的**具体操作指令**

- **信号到动作的映射规则（优先级顺序）**:
  1. **主要规则 - 优先遵循分析师信号**:
     - **分析师看多** → 如果未持有：**买入**（buy）；如果已持有：**持有或加仓**（hold/buy more）
     - **分析师中性** → **持有**（hold）
     - **分析师看空** → 如果未持有：**做空或持有**（short/hold）；如果已持有：**卖出**（sell）
     - **分析师意见分歧** → 根据加权平均置信度决定
  
  2. **例外规则 - 仅在特殊情况下偏离**:
     - **看多但卖出**: 仅在同时满足以下条件时：(a) 已持有较大仓位 AND (b) 需要获利了结/调整仓位 AND (c) 价格已充分反映看多预期
     - **看空但买入**: 仅在存在明确的逆向投资机会且风险收益比有利时
     - 如果偏离主要规则，系统会在决策理由中详细说明原因

  3. **持仓感知决策**:
     - **未持有 + 看多** → 买入
     - **未持有 + 中性** → 持有（不操作）
     - **未持有 + 看空** → 做空或持有（避免买入）
     - **已持有 + 看多** → 持有或加仓
     - **已持有 + 中性** → 持有（维持仓位）
     - **已持有 + 看空** → 卖出（减仓或清仓）

- **系统改进**:
  - 投资组合管理器现在**优先遵循分析师信号**，确保决策逻辑合理
  - 只有在有明确、充分的理由时才会偏离分析师信号
  - 系统会在决策理由中明确说明信号共识和决策依据
  - 前端界面会显示提示信息，帮助用户理解决策逻辑

### 支持的 LLM 提供商

- OpenAI (GPT-4, GPT-4o, GPT-3.5 等)
- Anthropic (Claude)
- Groq (快速推理)
- DeepSeek
- Ollama (本地运行)
- Google Gemini
- GigaChat
- xAI (Grok)

## 项目结构

```
deep_investor_agent/
├── src/                    # 核心源代码
│   ├── agents/            # 投资智能体
│   ├── backtesting/       # 回测引擎
│   ├── data/              # 数据获取和处理
│   ├── graph/             # 工作流图
│   ├── llm/               # LLM 集成
│   ├── tools/             # 工具函数
│   └── utils/             # 工具类
├── app/                   # Web 应用
│   ├── backend/           # FastAPI 后端
│   └── frontend/          # Vue3 前端
├── tests/                 # 测试文件
├── docker/               # Docker 配置
├── LICENSE               # MIT 许可证
└── README.md             # 本文件
```

## 贡献指南

我们欢迎所有形式的贡献！请遵循以下步骤：

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

**重要提示**: 请保持 Pull Request 小而专注，这将使审查和合并更容易。

### 开发规范

- 遵循 Python PEP 8 代码风格
- 为新功能添加测试
- 更新相关文档
- 确保所有测试通过

## 功能请求

如果您有功能请求，请打开一个 [Issue](https://github.com/your-username/deep_investor_agent/issues) 并确保标记为 `enhancement`。

## 许可证

本项目采用 [MIT 许可证](LICENSE) 开源。

### 版权声明

```
Copyright (c) 2025 Deep Investor Agent Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 致谢

本项目基于 [ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) 项目改造而来，感谢原项目的贡献者。

### 主要改进点

相比原项目，本项目的主要改进包括：

1. **市场扩展**: 新增 A股和港股市场支持，使系统能够分析中国内地和香港市场的股票
2. **智能体扩展**: 新增 5 个中国投资大师智能体，基于中国市场的投资理念和实践
3. **本地化优化**: 增加简体中文和繁体中文支持，提升中文用户的使用体验
4. **多语言修复**: 
   - 修复了中国投资大师智能体（段永平、张磊、邱国鹭、冯柳、但斌）的语言输出问题，现在这些智能体能够根据用户设置的语言（中文/英文）正确输出对应语言的分析结果，而不是始终输出中文内容
   - 修复了创建和编辑流程对话框的语言适配问题，现在这些对话框会根据用户选择的语言（简体中文、繁体中文、英文）显示对应的界面文本
   - 修复了所有美国投资大师智能体的语言输出问题，现在这些智能体能够根据用户设置的语言（中文/英文）正确输出对应语言的分析结果。已修复的智能体包括：巴菲特、芒格、彼得·林奇、本杰明·格雷厄姆、比尔·阿克曼、凯西·伍德、迈克尔·伯里、莫尼什·帕伯莱、菲利普·费雪、拉凯什·君君瓦拉、斯坦利·德鲁肯米勒、达摩达兰

## 联系方式

如有问题或建议，请通过以下方式联系：

- 提交 [Issue](https://github.com/your-username/deep_investor_agent/issues)
- 创建 [Pull Request](https://github.com/your-username/deep_investor_agent/pulls)

---

**再次提醒**: 本项目仅用于教育和研究目的，不用于实际交易或投资。使用本软件即表示您理解并同意此免责声明。
