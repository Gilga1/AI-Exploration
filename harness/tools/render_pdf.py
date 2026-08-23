from pydantic import BaseModel, Field

from harness.core.context import RunContext
from harness.core.models import ExecutionMode, ToolSpec
from harness.registry import register_tool


class RenderPdfInput(BaseModel):
    html: str = Field(description="HTML content to render as PDF")
    title: str | None = None


class RenderPdfOutput(BaseModel):
    pdf_bytes: bytes
    page_count: int


@register_tool
class RenderPdfFromHtmlTool:
    spec = ToolSpec(
        name="render_pdf_from_html",
        description="Renders HTML content into a PDF byte stream.",
        capability_tags=["document-generation", "pdf"],
        input_schema=RenderPdfInput,
        output_schema=RenderPdfOutput,
        side_effects=False,
        execution_mode=ExecutionMode.IN_PROCESS,
    )

    async def run(self, args: RenderPdfInput, *, context: RunContext) -> RenderPdfOutput:
        # Minimal PDF stub — replaced with real renderer in production.
        content = args.html.encode("utf-8")
        page_count = max(1, len(content) // 2000)
        pdf_stub = b"%PDF-1.4\n%" + content[:100]
        return RenderPdfOutput(pdf_bytes=pdf_stub, page_count=page_count)
