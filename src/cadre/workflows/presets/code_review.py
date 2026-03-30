"""Single-agent code review workflow."""

from cadre.workflows.types import WorkflowDef, WorkflowStep

code_review = WorkflowDef(
    name="code-review",
    description="Single-agent code review — QA reviews current changes",
    steps=[
        WorkflowStep(
            agent="qa",
            instruction=(
                "Review the current git diff. Check code quality, testing, documentation, "
                "and adherence to project conventions. Provide a structured review."
            ),
            wait_for_approval=False,
        ),
    ],
)
