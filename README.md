# Video Action MCP

Remote MCP server for the Video Action Agent Skill.

## Tools

- `analyze_video_event` — records a visual event.
- `save_decision` — stores a proposed action without executing it.
- `get_decisions` — retrieves saved proposals.
- `validate_action` — validates a proposal without executing it.

No unrestricted computer-control or command-execution tool is included.

## Deploy

1. Put these files in a GitHub repository.
2. In Render, create a Web Service from that repository.
3. Render reads `render.yaml`, installs dependencies, and generates `MCP_PATH_SECRET`.
4. Open `/health` on the deployed service and confirm `{"status":"ok"}`.
5. Open `/` and copy the MCP endpoint shown there.
6. In Claude: Customize -> Connectors -> + -> Add custom connector.
7. Paste the complete MCP endpoint URL.

Keep the endpoint private. Do not post it publicly.

## Test

After enabling the connector in a conversation, upload a video and say:

Use my Video Action Agent skill. Use the Video Action MCP connector to record
important visual events, save the final proposed action, and validate it.
Do not execute any external action.
