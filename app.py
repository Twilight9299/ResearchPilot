import hashlib
import os

import streamlit as st
from dotenv import load_dotenv

from researchpilot.graph import build_research_graph
from researchpilot.llm import create_chat_model
from researchpilot.models import (
    EvidenceType,
    PaperAnalysis,
    ReproductionReadiness,
    ResearchMode,
    ResearchRequest,
)
from researchpilot.pdf import PdfError, chunk_pages, extract_pages

load_dotenv()

st.set_page_config(page_title="ResearchPilot", page_icon="🔬", layout="wide")


@st.cache_data(show_spinner=False)
def parse_pdf(file_bytes: bytes):
    pages = extract_pages(file_bytes)
    return pages, chunk_pages(pages)


def render_sources(evidence) -> None:
    st.markdown("#### 原文依据")
    for source in evidence:
        with st.expander(f"PDF 第 {source.page_number} 页"):
            st.write(source.excerpt)


def render_analysis(analysis: PaperAnalysis) -> None:
    st.subheader(analysis.title or "论文结构化分析")
    sections = [
        ("研究问题", analysis.research_question),
        ("方法与技术路线", analysis.approach),
        ("关键结果", analysis.key_results),
        ("主要贡献", analysis.contributions),
        ("局限性", analysis.limitations),
        ("后续研究方向", analysis.future_work),
    ]
    for heading, item in sections:
        st.markdown(f"### {heading}")
        st.write(item.finding)
        st.caption("来源页码：" + "、".join(f"第 {page} 页" for page in item.pages))


def render_readiness(readiness: ReproductionReadiness) -> None:
    status_labels = {
        "available": "可用",
        "missing": "缺失",
        "unclear": "不明确",
        "not_applicable": "不适用",
    }
    st.subheader(readiness.title or "论文复现条件评估")
    st.info(
        f"总体状态：{status_labels[readiness.overall_status.value]}\n\n{readiness.summary}"
    )

    sections = [
        ("资源与材料", readiness.resources),
        ("环境与依赖", readiness.environment),
        ("实验与指标", readiness.experiment),
        ("当前阻碍", readiness.blockers),
    ]
    for heading, items in sections:
        st.markdown(f"### {heading}")
        if not items:
            st.caption("论文摘录中没有识别到相关信息。")
            continue
        for item in items:
            with st.container(border=True):
                st.markdown(
                    f"**{item.name}** · {status_labels[item.status.value]} · `{item.category}`"
                )
                st.write(item.details)
                if item.url:
                    st.code(item.url, language=None)
                if item.pages:
                    st.caption("来源页码：" + "、".join(f"第 {page} 页" for page in item.pages))
                elif item.evidence_type == EvidenceType.INFERENCE:
                    st.caption("系统推断：论文摘录中未找到明确依据。")
                if item.approval_required:
                    st.warning("后续如需访问或下载此资源，必须先获得你的确认。")

    if readiness.pdf_checks:
        st.markdown("### PDF 内待复核")
        for check in readiness.pdf_checks:
            st.text(check)

    st.markdown("### 外部操作（需审批）")
    if readiness.approval_actions:
        for action in readiness.approval_actions:
            st.markdown(f"- {action}")
    else:
        st.caption("当前没有待审批操作。")

    if readiness.caveats:
        with st.expander("评估边界与注意事项"):
            for caveat in readiness.caveats:
                st.markdown(f"- {caveat}")
    st.caption("本阶段只评估复现条件，不会下载文件、运行代码或声称复现成功。")


with st.sidebar:
    st.header("模型设置")
    environment_key = os.getenv("OPENAI_API_KEY", "")
    api_key = st.text_input(
        "OpenAI API Key",
        value=environment_key,
        type="password",
        help="仅在当前进程中使用；推荐通过本地 .env 配置。",
    )
    model_name = st.text_input("模型", value=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    base_url = st.text_input("兼容 API 地址（可选）", value=os.getenv("OPENAI_BASE_URL", ""))
    st.divider()
    st.caption("V1：PDF 文本提取、页码证据、论文问答、结构化分析。")
    st.caption("V2 阶段 1：复现资源识别与条件评估，不执行下载或实验。")
    st.caption("尚未实现：OCR、沙箱实验、结果验证、完整报告导出。")

st.title("🔬 ResearchPilot")
st.write("上传论文，获得可追溯到 PDF 页码的问答与结构化研究分析。")

uploaded_file = st.file_uploader("上传一篇 PDF 论文", type=["pdf"])
if not uploaded_file:
    st.info("请先上传 PDF。文件只在当前应用会话中处理。")
    st.stop()

file_bytes = uploaded_file.getvalue()
document_id = hashlib.sha256(file_bytes).hexdigest()[:12]

try:
    with st.spinner("正在提取论文文本……"):
        pages, chunks = parse_pdf(file_bytes)
except PdfError as exc:
    st.error(str(exc))
    st.stop()

text_characters = sum(len(page.text) for page in pages)
col1, col2, col3 = st.columns(3)
col1.metric("PDF 页数", len(pages))
col2.metric("文本字符", f"{text_characters:,}")
col3.metric("文档编号", document_id)

if not api_key:
    st.warning("PDF 已解析。配置 API Key 后即可运行问答和分析；密钥不会写入项目文件。")

mode_label = st.radio(
    "选择研究模式",
    ["自动研究", "自定义研究", "复现评估"],
    horizontal=True,
    help="自动研究生成结构化分析；自定义研究回答问题；复现评估检查代码、数据和实验条件。",
)

if mode_label == "自动研究":
    st.write("系统将分析研究问题、方法、结果、贡献、局限与未来方向，并标注来源页码。")
    run = st.button("开始自动分析", type="primary", disabled=not api_key)
    question = ""
    mode = ResearchMode.AUTOMATIC
elif mode_label == "复现评估":
    st.write("系统将识别代码、数据、环境、参数与指标，并列出缺失条件和待审批操作。")
    run = st.button("开始复现条件评估", type="primary", disabled=not api_key)
    question = ""
    mode = ResearchMode.REPRODUCTION
else:
    question = st.text_area(
        "你希望研究什么？",
        placeholder="例如：论文的核心创新是什么？实验设计是否充分？",
    )
    run = st.button("提交研究问题", type="primary", disabled=not api_key or not question.strip())
    mode = ResearchMode.CUSTOM

if run:
    try:
        model = create_chat_model(api_key=api_key, model_name=model_name, base_url=base_url or None)
        graph = build_research_graph(model)
        with st.spinner("ResearchPilot 正在阅读与组织证据……"):
            result = graph.invoke(
                {
                    "request": ResearchRequest(mode=mode, question=question),
                    "chunks": chunks,
                }
            )
        if mode == ResearchMode.AUTOMATIC:
            render_analysis(result["analysis"])
        elif mode == ResearchMode.REPRODUCTION:
            render_readiness(result["readiness"])
        else:
            st.markdown("### 回答")
            st.write(result["answer"].answer)
            render_sources(result["answer"].evidence)
    except Exception as exc:
        st.error("模型调用失败。请检查 API Key、模型名称、网络或兼容 API 地址。")
        with st.expander("技术详情"):
            st.code(f"{type(exc).__name__}: {exc}")

st.divider()
with st.expander("后续能力路线图"):
    st.write("以下能力仅为预留，当前版本不会假装执行：")
    st.checkbox("查找或生成算法复现代码", disabled=True)
    st.checkbox("在隔离沙箱中运行实验", disabled=True)
    st.checkbox("对照论文结果进行验证", disabled=True)
    st.checkbox("导出可复现研究报告", disabled=True)
