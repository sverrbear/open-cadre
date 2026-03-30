"""Full model creation pipeline — design, staging, implementation, testing, review."""

from cadre.workflows.types import WorkflowDef, WorkflowStep

model_creation = WorkflowDef(
    name="model-creation",
    description="Full model creation pipeline with staging layer check",
    steps=[
        WorkflowStep(
            agent="architect",
            instruction=(
                "Design the data model for this request. Include:\n"
                "1. Check if source/staging models exist, or need to be created\n"
                "2. Propose grain, primary key, materialization strategy\n"
                "3. Define all columns with types\n"
                "4. Classify risk level\n"
                "5. List all dependencies"
            ),
            wait_for_approval=True,
        ),
        WorkflowStep(
            agent="engineer",
            instruction=(
                "Implement the full model pipeline:\n"
                "1. Create staging models if needed (sources.yml + stg_ models)\n"
                "2. Create the target model with proper SQL\n"
                "3. Add schema.yml with all column descriptions\n"
                "4. Add tests (unique, not_null on PK, relationships)\n"
                "5. Run dbt compile and dbt test\n"
                "6. Create a clean git commit"
            ),
            pass_output_to_next=True,
        ),
        WorkflowStep(
            agent="qa",
            instruction=(
                "Perform a thorough review:\n"
                "1. Compare implementation against architect's design\n"
                "2. Verify grain and primary key correctness\n"
                "3. Check test coverage (PK tests, relationship tests, data tests)\n"
                "4. Verify schema.yml completeness\n"
                "5. Review SQL quality and conventions\n"
                "6. Run dbt compile and dbt test independently\n"
                "7. Approve or request specific changes"
            ),
            pass_output_to_next=True,
        ),
    ],
)
