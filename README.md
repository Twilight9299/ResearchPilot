# ResearchPilot

ResearchPilot 是一个面向科研论文的开源 AI Agent 原型。V1 使用 Python、LangGraph 与 Streamlit，支持上传 PDF、提取文本、带 PDF 页码来源的论文问答，以及结构化论文分析。

V2 提供带页码的复现条件评估。V3 支持编辑实验计划、手动对照一个指标并导出 Markdown 报告。沙箱执行和自动结果验证仍在路线图中。

## V1 能力

- 上传单篇 PDF（最大 50 MB、500 页）
- 按 PDF 原始页码提取并切分文本
- 本地轻量关键词检索，不需要向量数据库
- 自定义论文问答，并展示命中的原文片段与页码
- 自动生成研究问题、方法、结果、贡献、局限和未来方向分析
- LangGraph 工作流编排
- OpenAI 或兼容 Chat Completions API

## 运行要求

- Windows 10/11
- PowerShell
- Python 3.11 或更高版本
- 一个可用的 OpenAI API Key，或兼容 API 的 Key 与地址

## Windows 快速开始

```powershell
git clone <your-repository-url>
cd ResearchPilot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

编辑本地 `.env`：

```dotenv
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=gpt-4.1-mini
OPENAI_BASE_URL=
```

启动应用：

```powershell
streamlit run app.py
```

如果 PowerShell 禁止激活脚本，可以不激活虚拟环境，直接运行：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

浏览器通常会自动打开 `http://localhost:8501`。

## V3 实验记录与指标对照

1. 上传 PDF，选择「复现评估」并开始评估。
2. 在「V3 实验记录与指标对照」中编辑计划，填写指标、单位、论文值及其 PDF 页码。
3. 填写实测值、结果来源和条件差异。确认数据划分、指标定义和单位一致后，勾选可直接比较，界面会计算实测值减论文值。
4. 下载 Markdown 对照报告。报告保留手动填写的数值、页码和备注。

## 测试与代码检查

```powershell
python -m pytest
python -m ruff check .
```

## 项目结构

```text
ResearchPilot/
├── app.py                      # Streamlit 界面
├── src/researchpilot/
│   ├── graph.py                # LangGraph 问答与分析工作流
│   ├── llm.py                  # 模型客户端配置
│   ├── models.py               # 数据模型
│   ├── pdf.py                  # PDF 文本提取与分页切分
│   └── retrieval.py            # 本地关键词检索
├── tests/                      # 基础单元测试
├── pyproject.toml              # 依赖与工具配置
├── requirements.txt            # 兼容常见安装流程
└── .env.example                # 环境变量模板，不包含密钥
```

## 数据与隐私

- PDF 文本在 Streamlit 当前进程内提取与缓存。
- 运行问答或分析时，选中的论文片段会发送给你配置的模型服务商。
- API Key 可从 `.env` 读取，也可在侧栏临时输入；项目不会主动写回 Key。
- `.env`、Streamlit secrets 和常见缓存目录已加入 `.gitignore`。

## 已知限制

- 扫描版 PDF 暂无 OCR，因此可能无法提取文本。
- 双栏排版、公式和复杂表格的读取顺序取决于 PDF 内部文本层。
- V1 使用轻量词频检索；语义检索和跨论文检索留待后续版本。
- 自动分析只基于送入模型的代表性片段，不应替代人工通读和学术判断。
- 页码指 PDF 文件页序，可能与论文印刷页码不同。

## 后续路线

1. OCR、版面分析、公式与表格抽取
2. 可选语义向量检索与多论文对比
3. 公开代码检索与复现计划生成
4. 需要用户审批的隔离沙箱实验
5. 论文结果对照、误差分析与证据记录
6. 可导出的可复现研究报告

## License

MIT
