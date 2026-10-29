# Optional real LLM demo: inventory decisions

**Status:** implemented and tested with mocked HTTP responses. No live OpenAI result has been verified yet. Do not claim a real prompt regression until you run the experiment and inspect its evidence.

The agent uses OpenAI's Responses API with one read-only `lookup_stock` tool and a fixed synthetic inventory. A six-case suite checks the final `{sku, stock, reorder}` object with deterministic assertions. There is no LLM judge.

The baseline prompt recommends reorder when `stock <= threshold`. The intentionally changed candidate says `stock < threshold`. Boundary cases should expose this change if the selected model follows the prompts, but actual outcomes are measured rather than assumed. The two agents share the same code, tools, and suite; only the instructions differ. OpenAI seeds are not supported by this demo; matching trial labels do not make model outputs deterministic.

## Run locally

Set credentials in the terminal where you run the experiment. Do not paste a key into chat, store it in source, or commit it. Choose a model your OpenAI account supports with Responses tool calling and structured JSON output.

```sh
# In the activated project virtual environment:
# Set OPENAI_API_KEY securely in your shell or secret manager.
export OPENAI_MODEL='your-supported-model-id'
python scripts/llm_demo.py
```

The script uses six cases per variant, one trial per case, with a maximum of three model requests per trial: **at most 36 requests**, each capped at 1,500 output tokens. Requests cost money according to the model selected. HTTP requests have 30-second timeouts; the trial timeout is 100 seconds. No provider retries are performed. Reduce the fixture deliberately and version it if you need a smaller experiment.

The script saves both runs in your configured store and writes `reports/llm-comparison.json`. Exit 1 can indicate a detected regression or a failed experiment; read the accompanying message and inspect trial errors. It explicitly checks for infrastructure errors and requires the baseline to pass every case before presenting the final regression exit status. Keep the report and trace evidence; do not cherry-pick a successful run. A six-case convenience suite cannot establish population reliability.

Traces include requested/resolved model identifiers, prompt hash, usage, validated tool calls, and tool outputs. Raw reasoning and encrypted continuation state are not logged. Credentials are masked before storage. Model/tool outputs remain untrusted and are validated. The tool cannot modify inventory or perform purchases.

The agent follows the [official function-calling protocol](https://developers.openai.com/api/docs/guides/function-calling): return tool outputs with their call IDs and preserve response items needed for continuation. This API integration is separate from the mocked protocol tests; passing those tests does not prove provider access or model quality.
