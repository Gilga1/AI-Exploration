from pydantic import BaseModel, Field

from harness.core.context import RunContext
from harness.core.models import SkillManifest
from harness.core.protocols import BaseSkill
from harness.registry import register_skill
from harness.telemetry.instrumentation import invoke_tool_with_telemetry


class MdToPdfInput(BaseModel):
    markdown: str
    title: str | None = None


class MdToPdfOutput(BaseModel):
    artifact_url: str
    page_count: int


def markdown_to_html(markdown: str, title: str | None = None) -> str:
    title_tag = f"<title>{title}</title>" if title else ""
    body = markdown.replace("\n", "<br/>\n")
    return f"<html><head>{title_tag}</head><body>{body}</body></html>"


@register_skill
class MarkdownToPdfSkill(BaseSkill):
    manifest = SkillManifest(
        name="markdown_to_pdf",
        description="Converts Markdown text into a formatted PDF document.",
        capability_tags=["document-generation", "pdf", "markdown"],
        required_tools=["render_pdf_from_html"],
        input_schema=MdToPdfInput,
        output_schema=MdToPdfOutput,
        system_prompt_fragment="Use this to turn markdown notes into a shareable PDF.",
        sandboxed=False,
    )

    async def execute(self, payload: MdToPdfInput, *, context: RunContext) -> MdToPdfOutput:
        html = markdown_to_html(payload.markdown, payload.title)
        tool = context.tools["render_pdf_from_html"]
        pdf_result = await invoke_tool_with_telemetry(
            "render_pdf_from_html",
            tool,
            tool.spec.input_schema(html=html, title=payload.title),
            context=context,
            rationale="Render markdown HTML to PDF bytes",
        )
        ref = await context.store_artifact(pdf_result.pdf_bytes, kind="pdf", metadata={"pages": pdf_result.page_count})
        return MdToPdfOutput(artifact_url=ref["url"], page_count=pdf_result.page_count)
