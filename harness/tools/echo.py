from pydantic import BaseModel, Field

from harness.core.models import ExecutionMode, ToolSpec
from harness.core.context import RunContext
from harness.registry import register_tool


class EchoInput(BaseModel):
    message: str = Field(description="Text to echo back")


class EchoOutput(BaseModel):
    message: str
    length: int


@register_tool
class EchoTool:
    spec = ToolSpec(
        name="echo",
        description="Echoes a message back to the caller. Useful for smoke-testing the harness.",
        capability_tags=["utility", "debug"],
        input_schema=EchoInput,
        output_schema=EchoOutput,
        side_effects=False,
        execution_mode=ExecutionMode.IN_PROCESS,
    )

    async def run(self, args: EchoInput, *, context: RunContext) -> EchoOutput:
        return EchoOutput(message=args.message, length=len(args.message))
