from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr

from researchpilot.graph import (
    _parse_paper_analysis,
    _parse_reproduction_readiness,
    build_research_graph,
)
from researchpilot.models import PaperChunk, ResearchMode, ResearchRequest

ANALYSIS_JSON = """
{
  "title": "Example paper",
  "research_question": {"finding": "研究问题", "pages": [1]},
  "approach": {"finding": "研究方法", "pages": [1]},
  "key_results": {"finding": "主要结果", "pages": [2]},
  "contributions": {"finding": "主要贡献", "pages": [2]},
  "limitations": {"finding": "研究局限", "pages": [99]},
  "future_work": {"finding": "未来方向", "pages": [2]}
}
"""

READINESS_JSON = """
{
  "title": "Example paper",
  "overall_status": "unclear",
  "summary": "数据可用，但代码与环境信息不完整。",
  "resources": [
    {
      "category": "data",
      "name": "Public dataset",
      "status": "available",
      "evidence_type": "paper",
      "details": "The paper describes a public dataset.",
      "pages": [9],
      "url": "",
      "approval_required": true
    }
  ],
  "environment": [
    {
      "category": "hardware",
      "name": "GPU",
      "status": "unclear",
      "evidence_type": "inference",
      "details": "GPU requirements are not stated in the excerpts.",
      "pages": [],
      "url": "",
      "approval_required": false
    }
  ],
  "experiment": [],
  "blockers": [
    {
      "category": "code",
      "name": "Official implementation",
      "status": "missing",
      "evidence_type": "inference",
      "details": "No repository is stated in the excerpts.",
      "pages": [99],
      "url": "",
      "approval_required": false
    }
  ],
  "approval_actions": ["Download the dataset after user approval."],
  "caveats": ["No files were downloaded or executed."]
}
"""


class FakeChatModel(BaseChatModel):
    responses: list[str]
    _response_index: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        response_text = self.responses[min(self._response_index, len(self.responses) - 1)]
        self._response_index += 1
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=response_text))]
        )


def test_parse_paper_analysis_accepts_markdown_fenced_json() -> None:
    analysis = _parse_paper_analysis(f"```json\n{ANALYSIS_JSON}\n```")

    assert analysis.title == "Example paper"
    assert analysis.key_results.pages == [2]


def test_parse_reproduction_readiness_accepts_plain_json() -> None:
    readiness = _parse_reproduction_readiness(READINESS_JSON)

    assert readiness.overall_status == "unclear"
    assert readiness.resources[0].pages == [9]


def test_automatic_analysis_works_without_native_response_format() -> None:
    graph = build_research_graph(FakeChatModel(responses=[ANALYSIS_JSON]))
    chunks = [
        PaperChunk(chunk_id="p1-c1", page_number=1, text="Method and research question."),
        PaperChunk(chunk_id="p2-c1", page_number=2, text="Results and contributions."),
    ]

    result = graph.invoke(
        {
            "request": ResearchRequest(mode=ResearchMode.AUTOMATIC),
            "chunks": chunks,
        }
    )

    assert result["analysis"].title == "Example paper"
    assert result["analysis"].limitations.pages == [1]


def test_custom_question_expands_query_and_deduplicates_evidence_pages() -> None:
    model = FakeChatModel(
        responses=[
            "dataset training testing random split experiment setup",
            "The dataset is split into 80% training and 20% testing [p. 9].",
        ]
    )
    graph = build_research_graph(model)
    chunks = [
        PaperChunk(chunk_id="p1-c1", page_number=1, text="Paper introduction."),
        PaperChunk(chunk_id="p1-c2", page_number=1, text="More introduction."),
        PaperChunk(
            chunk_id="p9-c1",
            page_number=9,
            text="The dataset is randomly split into 80% training and 20% testing.",
        ),
    ]

    result = graph.invoke(
        {
            "request": ResearchRequest(
                mode=ResearchMode.CUSTOM,
                question="论文的数据集如何划分？",
            ),
            "chunks": chunks,
        }
    )

    assert "80%" in result["answer"].answer
    assert [item.page_number for item in result["answer"].evidence] == [9]


def test_custom_question_shows_only_pages_cited_in_the_answer() -> None:
    model = FakeChatModel(
        responses=[
            "paper title future work next publication",
            "The current title is provided [p. 1], but no next title is stated [p. 15].",
        ]
    )
    graph = build_research_graph(model)
    chunks = [
        PaperChunk(chunk_id="p1-c1", page_number=1, text="Current paper title."),
        PaperChunk(chunk_id="p6-c1", page_number=6, text="Method details."),
        PaperChunk(chunk_id="p11-c1", page_number=11, text="Ablation results."),
        PaperChunk(chunk_id="p15-c1", page_number=15, text="Future work plans."),
    ]

    result = graph.invoke(
        {
            "request": ResearchRequest(
                mode=ResearchMode.CUSTOM,
                question="作者下一篇论文的具体标题是什么？",
            ),
            "chunks": chunks,
        }
    )

    assert [item.page_number for item in result["answer"].evidence] == [1, 15]


def test_reproduction_readiness_filters_invalid_pages() -> None:
    graph = build_research_graph(FakeChatModel(responses=[READINESS_JSON]))
    chunks = [
        PaperChunk(chunk_id="p1-c1", page_number=1, text="Paper introduction."),
        PaperChunk(
            chunk_id="p9-c1",
            page_number=9,
            text="Dataset and evaluation details.",
        ),
    ]

    result = graph.invoke(
        {
            "request": ResearchRequest(mode=ResearchMode.REPRODUCTION),
            "chunks": chunks,
        }
    )

    assert result["readiness"].resources[0].pages == [9]
    assert result["readiness"].blockers[0].pages == []
    assert result["readiness"].blockers[0].status == "unclear"
