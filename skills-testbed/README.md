# Skills Testbed

This folder is a local sandbox for testing newly generated Codex skills before moving them into the main `skills` directory.

## Layout

- `inputs/`: sample prompts, source documents, or other test inputs
- `fixtures/`: stable mock data and reusable test assets
- `outputs/`: generated files from skill runs
- `logs/`: command output and debugging logs
- `tmp/`: scratch files that can be deleted safely

Keep tests here isolated from production skill definitions.
