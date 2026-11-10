import json
import re
from collections.abc import Callable
from typing import TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from researchpilot.models import (
    AnalysisItem,
    AnswerResult,
    Evidence,
    EvidenceType,
    PaperAnalysis,
    PaperChunk,
    ReadinessStatus,
    ReproductionItem,
    ReproductionReadiness,
    ResearchMode,
    ResearchRequest,
)
from researchpilot.retrieval import retrieve_chunks, select_analysis_chunks


class ResearchState(TypedDict, total=False):
    request: ResearchRequest
    chunks: list[PaperChunk]
    context: list[PaperChunk]
    answer: AnswerResult
    analysis: PaperAnalysis
    readiness: ReproductionReadiness


def format_context(chunks: list[PaperChunk]) -> str:
    return "\n\n".join(f"[PDF page {chunk.page_number}]\n{chunk.text}" for chunk in chunks)


PAGE_CITATION_PATTERN = re.compile(r"\[p\.\s*(\d+)\]", re.IGNORECASE)


def _cited_pages(answer: str) -> list[int]:
    return list(dict.fromkeys(int(page) for page in PAGE_CITATION_PATTERN.findall(answer)))


def _evidence(
    chunks: list[PaperChunk], answer: str = "", limit: int = 4
) -> list[Evidence]:
    evidence: list[Evidence] = []
    seen_pages: set[int] = set()
    cited_pages = _cited_pages(answer)
    if cited_pages:
        page_order = {page: index for index, page in enumerate(cited_pages)}
        candidates = sorted(
            (chunk for chunk in chunks if chunk.page_number in page_order),
            key=lambda chunk: page_order[chunk.page_number],
        )
    else:
        candidates = chunks

    for chunk in candidates:
        if chunk.page_number in seen_pages:
            continue
        evidence.append(Evidence(page_number=chunk.page_number, excerpt=chunk.text[:700].strip()))
        seen_pages.add(chunk.page_number)
        if len(evidence) >= limit:
            break
    return evidence


def _expand_search_query(model: BaseChatModel, question: str) -> str:
    try:
        response = model.invoke(
            [
                SystemMessage(
                    content=(
                        "Rewrite the user's research-paper question as one concise line of "
                        "English search keywords. Include likely academic synonyms and section "
                        "terms. Return keywords only, without explanation."
                    )
                ),
                HumanMessage(content=question),
            ]
        )
    except Exception:
        return question
    expansion = str(response.content).strip()
    return f"{question}\n{expansion}" if expansion else question


def _merge_context(
    primary: list[PaperChunk], supplementary: list[PaperChunk], limit: int = 12
) -> list[PaperChunk]:
    merged: dict[str, PaperChunk] = {}
    for chunk in [*primary, *supplementary]:
        merged[chunk.chunk_id] = chunk
        if len(merged) >= limit:
            break
    return list(merged.values())


def _sanitize_analysis(analysis: PaperAnalysis, chunks: list[PaperChunk]) -> PaperAnalysis:
    allowed_pages = {chunk.page_number for chunk in chunks}
    fallback_page = min(allowed_pages) if allowed_pages else 1
    fields = (
        "research_question",
        "approach",
        "key_results",
        "contributions",
        "limitations",
        "future_work",
    )
    updates: dict[str, AnalysisItem] = {}
    for field in fields:
        item = getattr(analysis, field)
        pages = sorted({page for page in item.pages if page in allowed_pages}) or [fallback_page]
        updates[field] = AnalysisItem(finding=item.finding, pages=pages)
    return analysis.model_copy(update=updates)


def _parse_paper_analysis(content: object) -> PaperAnalysis:
    text = str(content).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("模型未返回可解析的 JSON 结构化分析。")

    try:
        return PaperAnalysis.model_validate_json(text[start : end + 1])
    except ValueError as exc:
        raise ValueError("模型返回的结构化分析不符合预期格式。") from exc


def _parse_reproduction_readiness(content: object) -> ReproductionReadiness:
    text = str(content).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("模型未返回可解析的复现条件 JSON。")

    try:
        return ReproductionReadiness.model_validate_json(text[start : end + 1])
    except ValueError as exc:
        raise ValueError("模型返回的复现条件评估不符合预期格式。") from exc


RESOURCE_EVIDENCE_PATTERN = re.compile(
    r"(?im)^\s*(?:references|bibliography|参考文献)\s*$"
    r"|^\s*(?:\[\d+\]|\d{1,3}\.)\s+[^\n]+"
    r"|(?:data|code|artifact) availability|availability of (?:data|code)"
    r"|supplementary materials?|https?://(?:www\.)?github\.com/|数据可用性|代码可用性"
)
TABLE_PATTERN = re.compile(r"(?im)^\s*(?:table\s*\d+|表\s*\d+)\b")


def _reproduction_context(chunks: list[PaperChunk]) -> list[PaperChunk]:
    query = (
        "source code repository dataset implementation environment hardware "
        "hyperparameters training evaluation metrics supplementary reproducibility"
    )
    primary = retrieve_chunks(query, chunks, limit=10)
    tables = []
    for index, chunk in enumerate(chunks):
        if TABLE_PATTERN.search(chunk.text):
            tables.append(chunk)
            if index + 1 < len(chunks) and chunks[index + 1].page_number == chunk.page_number:
                tables.append(chunks[index + 1])
    tables = _merge_context(tables, [], limit=5)
    resources = [chunk for chunk in chunks if RESOURCE_EVIDENCE_PATTERN.search(chunk.text)][:8]
    return _merge_context(
        tables + resources + primary, select_analysis_chunks(chunks), limit=24
    )


def _sanitize_reproduction_readiness(
    readiness: ReproductionReadiness, chunks: list[PaperChunk]
) -> ReproductionReadiness:
    allowed_pages = {chunk.page_number for chunk in chunks}

    def sanitize_items(items: list[ReproductionItem]) -> list[ReproductionItem]:
        sanitized = []
        for item in items:
            pages = sorted({page for page in item.pages if page in allowed_pages})
            updates = {"pages": pages}
            if item.category.strip().lower() in {"data", "dataset"}:
                if item.status == ReadinessStatus.AVAILABLE and not item.url.strip():
                    updates.update(status=ReadinessStatus.UNCLEAR)
            if not pages or item.evidence_type == EvidenceType.INFERENCE:
                updates.update(evidence_type=EvidenceType.INFERENCE, pages=[])
                if item.status in (ReadinessStatus.MISSING, ReadinessStatus.AVAILABLE):
                    updates.update(
                        status=ReadinessStatus.UNCLEAR,
                        details="当前摘录中未找到足以确认该项状态的依据，需进一步核查。",
                        url="",
                    )
            sanitized.append(item.model_copy(update=updates))
        return sanitized

    return readiness.model_copy(
        update={
            **(
                {
                    "overall_status": ReadinessStatus.UNCLEAR,
                    "summary": "当前摘录不足以确认复现所需条件是否齐全，请核查下列条目。",
                }
                if readiness.overall_status == ReadinessStatus.MISSING
                else {}
            ),
            "resources": sanitize_items(readiness.resources),
            "environment": sanitize_items(readiness.environment),
            "experiment": sanitize_items(readiness.experiment),
            "blockers": sanitize_items(readiness.blockers),
        }
    )


def build_research_graph(model: BaseChatModel):
    def retrieve(state: ResearchState) -> ResearchState:
        request = state["request"]
        if request.mode == ResearchMode.AUTOMATIC:
            context = select_analysis_chunks(state["chunks"])
        elif request.mode == ResearchMode.REPRODUCTION:
            context = _reproduction_context(state["chunks"])
        else:
            expanded_query = _expand_search_query(model, request.question)
            primary = retrieve_chunks(expanded_query, state["chunks"], limit=8)
            supplementary = select_analysis_chunks(state["chunks"], limit=8)
            context = _merge_context(primary, supplementary)
        return {"context": context}

    def answer_question(state: ResearchState) -> ResearchState:
        context = state["context"]
        response = model.invoke(
            [
                SystemMessage(
                    content=(
                        "You answer questions only from the supplied paper excerpts. "
                        "Cite factual claims with the exact PDF page marker [p. N]. "
                        "If the excerpts are insufficient, say so clearly. "
                        "Reply in the user's language."
                    )
                ),
                HumanMessage(
                    content=(
                        f"Question:\n{state['request'].question}\n\n"
                        f"Paper excerpts:\n{format_context(context)}"
                    )
                ),
            ]
        )
        answer = str(response.content)
        return {"answer": AnswerResult(answer=answer, evidence=_evidence(context, answer))}

    def analyze_paper(state: ResearchState) -> ResearchState:
        context = state["context"]
        schema = json.dumps(PaperAnalysis.model_json_schema(), ensure_ascii=False)
        response = model.invoke(
            [
                SystemMessage(
                    content=(
                        "Analyze only the supplied paper excerpts. Every finding must name "
                        "one or more supporting PDF page numbers. Distinguish author-stated "
                        "limitations from your careful inferences. Use concise Chinese unless "
                        "the paper is clearly requested otherwise. Return only one valid JSON "
                        "object without Markdown fences or additional commentary. The JSON must "
                        f"follow this schema exactly: {schema}"
                    )
                ),
                HumanMessage(
                    content=f"Create a structured paper analysis.\n\n{format_context(context)}"
                ),
            ]
        )
        analysis = _parse_paper_analysis(response.content)
        return {"analysis": _sanitize_analysis(analysis, context)}

    def assess_reproduction(state: ResearchState) -> ResearchState:
        context = state["context"]
        schema = json.dumps(ReproductionReadiness.model_json_schema(), ensure_ascii=False)
        response = model.invoke(
            [
                SystemMessage(
                    content=(
                        "Assess reproduction readiness only from the supplied paper excerpts. "
                        "Identify code, datasets, supplementary materials, dependencies, model "
                        "checkpoints, hardware, parameters, training procedures, and evaluation "
                        "metrics. Use evidence_type='paper' for statements directly supported by "
                        "the paper and cite exact PDF pages. Use evidence_type='inference' only "
                        "for cautious unclear assessments. When excerpts omit a detail, set "
                        "status='unclear' and say it was not found in the excerpts. Use "
                        "status='missing' only if the paper explicitly confirms absence. "
                        "Use overall_status='unclear' when information is insufficient. "
                        "For cited datasets, report the matching bibliography title and its "
                        "PDF page if present. If access is unclear, use status='unclear' even "
                        "if the paper describes the dataset as public. Read table rows as "
                        "evidence when present. Separate the proposed method from baselines "
                        "when listing or counting comparison methods. Use the paper's reported "
                        "baseline count and flag any discrepancy with the visible rows. "
                        "Put checks within the uploaded PDF in pdf_checks "
                        "and only external actions in approval_actions. "
                        "distinguish identifying a source from confirming access. Never invent "
                        "URLs, resources, commands, or results. Set approval_required=true for any "
                        "later download or external action. Reply in concise Chinese. Return one "
                        "valid JSON object without Markdown fences or commentary. The JSON must "
                        f"follow this schema exactly: {schema}"
                    )
                ),
                HumanMessage(
                    content=(
                        "Create a reproduction-readiness assessment. Do not execute or download "
                        f"anything.\n\n{format_context(context)}"
                    )
                ),
            ]
        )
        readiness = _parse_reproduction_readiness(response.content)
        return {"readiness": _sanitize_reproduction_readiness(readiness, context)}

    def route(state: ResearchState) -> str:
        mode = state["request"].mode
        if mode == ResearchMode.AUTOMATIC:
            return "analyze"
        if mode == ResearchMode.REPRODUCTION:
            return "readiness"
        return "answer"

    workflow = StateGraph(ResearchState)
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("answer", answer_question)
    workflow.add_node("analyze", analyze_paper)
    workflow.add_node("readiness", assess_reproduction)
    workflow.add_edge(START, "retrieve")
    workflow.add_conditional_edges(
        "retrieve",
        route,
        {"answer": "answer", "analyze": "analyze", "readiness": "readiness"},
    )
    workflow.add_edge("answer", END)
    workflow.add_edge("analyze", END)
    workflow.add_edge("readiness", END)
    return workflow.compile()


GraphFactory = Callable[[BaseChatModel], object]
