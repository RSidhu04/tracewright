def baseline(inputs, trace, seed):
    trace.emit("tool.call", {"tool": "calculator", "arguments": inputs, "api_key": "demo-secret"})
    a, b = inputs["a"], inputs["b"]
    output = {"answer": a + b}
    trace.emit("tool.result", output)
    return output


def candidate(inputs, trace, seed):
    output = baseline(inputs, trace, seed)
    # Deliberate regression: loses signs on negative totals.
    output["answer"] = abs(output["answer"])
    return output
