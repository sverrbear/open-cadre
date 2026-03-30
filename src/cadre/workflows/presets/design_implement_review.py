"""3-phase data team workflow: architect designs, engineer implements, QA reviews."""

from cadre.workflows.types import WorkflowDef, WorkflowStep

design_implement_review = WorkflowDef(
    name="design-implement-review",
    description="3-phase data team workflow: architect designs, engineer implements, QA reviews",
    steps=[
        WorkflowStep(
            agent="architect",
            instruction=(
                "Design the data model for this request. "
                "Propose grain, primary key, materialization, and classify risk level."
            ),
            wait_for_approval=True,
        ),
        WorkflowStep(
            agent="engineer",
            instruction=(
                "Implement the approved design. "
                "Write the dbt model, tests, and schema docs. Run validation."
            ),
            pass_output_to_next=True,
        ),
        WorkflowStep(
            agent="qa",
            instruction=(
                "Review the implementation against the design. "
                "Check grain, tests, docs, PR description. Approve or request changes."
            ),
            pass_output_to_next=True,
        ),
    ],
)
