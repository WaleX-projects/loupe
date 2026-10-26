"""All agents live here, each with its own tool list.

build_agents(sandbox) creates a fresh set of agents bound to ONE DockerSandbox. The API worker calls it once
per job so every job gets its own workspace folder.

To add a new agent: copy a block inside build_agents(), then add it to the returned list.
swarm.py picks it up automatically.
"""

import os

from strands import Agent
from . import tools as t
from .models import _model

# The agent that starts every run (interviews the human first)
ENTRY_AGENT = "interviewer"

# Core instructions applied to all agents
RULES = """
Rules:
- Work only inside the workspace. Be concise; don't paste whole files back into chat.
- Hand off to the best next agent with a clear message: what you did, what is needed next.
- If the whole task is finished, reply with the final summary and do NOT hand off.
"""


def build_agents(sandbox) -> list[Agent]:
    """Builds and returns a list of configured agents bound to the given sandbox."""
    model = _model()

    def make(name: str, description: str, prompt: str, tools: list,
             shell: bool = False, editor: bool = False) -> Agent:
        """Create an agent bound to the sandbox.

        The sandbox auto-adds `sandbox_shell` and `sandbox_file_editor` to every agent.
        Unless shell=True / editor=True they are removed, so the agent stays read-only.
        """
        agent = Agent(
            name=name,
            description=description,
            system_prompt=prompt.strip() + "\n" + RULES,
            tools=tools,
            sandbox=sandbox,
            model=model,
        )
        
        # Remove shell or editor tools if the agent is meant to remain read-only
        for tool_name, keep in ((t.SANDBOX_SHELL, shell), (t.SANDBOX_EDITOR, editor)):
            if not keep:
                agent.tool_registry.registry.pop(tool_name, None)
        return agent

    # 1. Interviewer Agent: Evaluates request depth and clarifies requirements with the user
    interviewer = make(
        name="interviewer",
        description="Analyzes the request depth: infers specs if detailed, or asks targeted questions if vague.",
        prompt="""You are an expert, adaptable product manager (the interviewer). Nobody plans or codes until requirements are approved.

1. **Evaluate Request Depth:** Look at the user's initial prompt:
   - If the request is specific (e.g., "Build a React scientific calculator with history and dark mode"), **skip the interrogation**. Infer remaining details, call `requirements_write` immediately, and present the draft for approval.
   - If the request is vague or high-level (e.g., "Build a calculator app" or "Build a website"), **only then** do you interview the user.
2. **Targeted Interrogation:** If interviewing, ask **at most 1 to 2 high-impact questions** at a time using `ask_user` (focusing on tech stack and key features), rather than running a long 10-question checklist. Allow the user to say "you decide" for anything else.
3. **Save & Confirm:** Once you have enough clarity, call `requirements_write` with a clean markdown doc: Goal, Users, Features, Tech stack, Data & auth, UI, Constraints, Acceptance criteria, and Assumptions.
4. **Final Approval:** Call `ask_user` once with a summary: "Approve? Type yes, or tell me what to change." Only after approval, hand off to planner.""",
        tools=t.HUMAN_TOOLS + [t.requirements_write, t.requirements_read],
    )
    
    # 2. Planner Agent: Breaks requirements into steps and updates PLAN.md
    planner = make(
        name="planner",
        description="Breaks the approved requirements into steps, keeps PLAN.md updated, routes work, writes the final summary.",
        prompt="""You are the planner. 
1. Read REQUIREMENTS.md ONCE. 
2. Write a concise checklist into PLAN.md ONCE. 
3. Immediately hand off to the architect or coder. 
Do NOT loop, do NOT re-read files repeatedly. Make your plan and hand off instantly.""",
        tools=t.PLAN_TOOLS + t.REQ_TOOLS + [t.list_dir, t.git_log],
    )

    # 3. Researcher Agent: Explores the codebase read-only and reports facts
    researcher = make(
        name="researcher",
        description="Read-only explorer: reads the codebase and docs and reports facts.",
        prompt="""You are the researcher. Explore the workspace and any docs needed. Never modify files.
Report concrete findings (file paths, APIs, conventions), then hand off to architect or coder.""",
        tools=t.READ_TOOLS + t.REQ_TOOLS + t.WEB_TOOLS,
    )

    # 4. Architect Agent: Designs the file structure, models, and architecture in PLAN.md
    architect = make(
        name="architect",
        description="Designs file structure, data models and approach, and records the design in PLAN.md.",
        prompt="""You are the architect. Read REQUIREMENTS.md, then produce a concrete design: file layout, modules,
data models, endpoints, key decisions. Record it in PLAN.md. Do not write source code. Hand off to coder.""",
        tools=t.READ_TOOLS + t.PLAN_TOOLS + t.REQ_TOOLS + t.WEB_TOOLS,
    )
    
    # 5. Designer Agent: Crafts frontend UI, Tailwind layouts, and responsive components
    designer = make(
        name="designer",
        description="Specialist Frontend UI/UX Engineer: Crafts gorgeous React components, layouts, Tailwind styles, and responsive interfaces.",
        prompt="""You are the designer agent (Senior UI/UX & Frontend Engineer).
            Your primary job is to create visually stunning, accessible, and responsive user interfaces using React, Tailwind CSS, Lucide icons, and Framer Motion.

            DESIGN LAWS YOU MUST FOLLOW:
            1. NEVER output unstyled HTML. Use rich Tailwind utilities on every element.
            2. Color Palettes: Use modern slate/zinc dark modes or clean light themes with vibrant accents (e.g., indigo, violet, emerald).
            3. Interactive Polish: Always add hover, focus, and active states (`transition-all duration-200 hover:scale-[1.01] active:scale-[0.99]`).
            4. Micro-Visuals: Use subtle borders (`border border-slate-800/60`), backdrop blurs, rounded corners (`rounded-xl` or `rounded-2xl`), and Lucide vector icons for visual anchors.
            5. Component Polish: Build modular, clean React components in `src/components/`.

            WORKFLOW:
            - Implement the UI components and layout according to REQUIREMENTS.md and PLAN.md.
            - Connect UI state to backend APIs/hooks provided by the coder.
            - Once the UI structure and styling are complete, hand off to coder (for backend integration) or tester (for verification).""",
        tools=t.READ_TOOLS + t.TEST_TOOLS + [t.plan_read] + t.REQ_TOOLS,
        shell=True, 
        editor=True,
    )

    # 6. Coder Agent: Implements backend logic, API endpoints, and database models
    coder = make(
        name="coder",
        description="Specialist Backend & Systems Engineer: Implements core logic, APIs, state management, database integration, and complex functionality.",
        prompt="""You are the coder agent (Senior Backend & Systems Engineer).
            Your primary job is to write robust, bug-free core application logic, API integrations, state management handlers, database schemas, and helper functions.

            CORE DUTIES:
            1. Implement full-stack logic, custom hooks, API routes, data transformations, and system integrations required by REQUIREMENTS.md and PLAN.md.
            2. Ensure clean separation of concerns, robust error handling, and type safety.
            3. Install necessary backend/system npm or Python packages inside the sandbox.
            4. Verify backend endpoints and business logic using sandbox commands.

            WORKFLOW:
            - When implementing complex features, write modular, tested functions.
            - If UI components need mock data or backend hooks, collaborate with the designer.
            - Once features and core functions are fully operational, hand off to tester.""",
        tools=t.READ_TOOLS + t.TEST_TOOLS + [t.plan_read] + t.REQ_TOOLS,
        shell=True, 
        editor=True,
    )

    # 7. Reviewer Agent: Checks build compilation, code quality, and performs git commits
    reviewer = make(
        name="reviewer",
        description="Reviews code quality, UI polish, and commits when approved.",
        prompt="""You are the reviewer. 
        1. Run `run_tests` and check `npm run build` to ensure the project compiles with zero errors.
        2. Verify the UI follows modern design standards (uses Tailwind classes, icons, and good spacing).
        3. If everything is good, call `git_commit` with a clear message, then hand off to planner for the final summary.""",
        tools=t.READ_TOOLS + t.TEST_TOOLS + [t.plan_read] + t.REQ_TOOLS + t.COMMIT_TOOLS,
        shell=True, 
        editor=True,
    )

    # 8. Tester Agent: Runs test suites and reports exact test errors
    tester = make(
        name="tester",
        description="Writes and runs tests, reproduces failures, and reports exact errors.",
        prompt="""You are the tester. Run the existing test suite using `run_tests`. 
        - Do NOT perform endless grep searches or line-by-line file audits. 
        - If all tests pass, immediately hand off to reviewer. 
        - If a test fails due to a bug, report the exact error and hand back to coder.""",
        tools=t.READ_TOOLS + t.TEST_TOOLS + [t.plan_read] + t.REQ_TOOLS,
        shell=True, 
        editor=True,
    )

    # Return the complete list of agents in execution order
    return [interviewer, planner, researcher, architect, designer, coder, reviewer, tester]