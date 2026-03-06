# LangSmith Tracing Guide

## Overview

The agent now includes **explicit LangSmith tracing** for every guardrail decision. You'll see detailed execution traces in the LangSmith dashboard showing exactly what each guardrail checked and decided.

## Setup

### 1. Get LangSmith API Key

1. Go to https://smith.langchain.com
2. Sign up or log in
3. Click your profile icon → **Settings** → **API Keys**
4. Click **Create API Key**
5. Copy the key (starts with `lsv2_pt_...`)

### 2. Enable in Streamlit App

**Option A: Via UI (Recommended)**
1. Run `streamlit run app.py`
2. In the sidebar, scroll to **"LangSmith (Observability)"**
3. Toggle **"Enable LangSmith tracing"** to ON
4. Paste your API key
5. Optionally change project name (default: `agent-guardrails-lab`)

**Option B: Via Environment Variables**
Add to your `.env` file:
```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_your_key_here
LANGCHAIN_PROJECT=agent-guardrails-lab
```

## What You'll See in LangSmith

### Trace Structure

When you run the agent, you'll see a hierarchical trace like this:

```
📊 guardrailed_agent_run
  │
  ├─ 🔍 deterministic_check
  │  └─ ✅ deterministic_result (CLEAR/FLAGGED)
  │
  ├─ 🔍 injection_check
  │  └─ ✅ injection_result (CLEAR/FLAGGED)
  │
  ├─ 🤖 model_based_input_check
  │  └─ ✅ model_based_input_result (SAFE/UNSAFE)
  │
  ├─ 🔒 pii_input_check
  │  └─ ✅ pii_input_result (PROCESSED/BLOCKED)
  │
  ├─ 🎯 tool_selection
  │  └─ LLM call to select tool
  │
  ├─ 📊 risk_scoring
  │  └─ Risk calculation details
  │
  ├─ 👤 hitl_check
  │  └─ Approval requirement check
  │
  ├─ ⚙️ tool_execution
  │  └─ ✅ tool_result
  │
  ├─ 🔒 pii_output_check
  │  └─ ✅ pii_output_result
  │
  ├─ 🤖 model_based_output_check
  │  └─ ✅ model_based_output_result
  │
  └─ 🎯 final_decision
     └─ Decision details + risk score
```

### Detailed Information Per Step

Each trace node includes:

**Inputs:**
- Description of what's being checked
- Relevant data (keywords, patterns, text)

**Outputs:**
- Decision (CLEAR, FLAGGED, SAFE, UNSAFE, etc.)
- Any matches or triggers
- Processed text (for PII)

**Metadata:**
- Risk scores
- Triggered policies
- Tool information
- Timing data

## Example Traces

### Safe Request
```
Input: "What is machine learning?"

✅ deterministic_check → CLEAR
✅ injection_check → CLEAR
✅ model_based_input → SAFE
✅ pii_input → PROCESSED (no PII)
🎯 tool_selection → No tool needed
✅ pii_output → PROCESSED (no PII)
✅ model_based_output → SAFE
✅ FINAL: allowed
```

### Blocked Request (Banned Keyword)
```
Input: "How to hack a server?"

⚠️ deterministic_check → FLAGGED (matched: "hack")
   Risk +35
✅ injection_check → CLEAR
⚠️ model_based_input → UNSAFE
   Risk +30
✅ pii_input → PROCESSED
🎯 tool_selection → search_web
📊 risk_scoring → Total: 75 (below block threshold)
✅ Tool executed
✅ FINAL: allowed (but with high risk score)
```

### Paused Request (HITL)
```
Input: "Delete all records from user table"

✅ deterministic_check → CLEAR
✅ injection_check → CLEAR
✅ model_based_input → SAFE
✅ pii_input → PROCESSED
🎯 tool_selection → delete_records
📊 risk_scoring → Total: 95 (high risk tool)
⏸️ hitl_check → PAUSED (requires approval)
   - require_approval: true
   - approved: false
⏸️ FINAL: paused_for_approval
```

## Navigating LangSmith Dashboard

### 1. Project View
- Select your project: "agent-guardrails-lab"
- See list of all runs with:
  - Timestamp
  - Input text
  - Final decision
  - Execution time
  - Status (success/error)

### 2. Run Details
Click any run to see:
- **Tree View**: Hierarchical trace of all steps
- **Timeline**: Visual timeline showing duration of each step
- **Inputs/Outputs**: Full data at each step
- **Metadata**: Risk scores, policies, decisions

### 3. Filtering
Use filters to find specific scenarios:
- Search by input text
- Filter by status (success/error)
- Filter by tags (if added)
- Time range selection

### 4. Comparison
- Compare multiple runs side-by-side
- See differences in guardrail behavior
- Analyze performance variations

## Advanced Features

### Custom Tags
You can add custom tags to traces for better organization:
```python
# In app.py or your code
os.environ["LANGCHAIN_TAGS"] = "production,high-risk"
```

### Feedback
Add feedback to traces in LangSmith UI:
- 👍 Correct behavior
- 👎 Incorrect behavior
- Comments for debugging

### Analytics
LangSmith provides analytics:
- Latency distribution
- Success rate
- Common error patterns
- Token usage (for LLM calls)

## Debugging with LangSmith

### Common Scenarios

**Scenario 1: Guardrail Not Triggering**
1. Find the run in LangSmith
2. Expand the specific guardrail step
3. Check inputs: Are keywords/patterns correct?
4. Check outputs: What was the decision?
5. Review metadata: Any errors?

**Scenario 2: Unexpected Blocking**
1. Look at risk_scoring step
2. See cumulative risk breakdown
3. Identify which guardrail added most risk
4. Review triggered policies list

**Scenario 3: Performance Issues**
1. Check Timeline view
2. Identify slow steps (usually model_based checks)
3. See LLM call durations
4. Optimize based on bottlenecks

## Costs

LangSmith pricing:
- **Free tier**: 5,000 traces/month
- **Developer**: $39/month for 100K traces
- **Team**: Custom pricing

For this demo app, free tier is sufficient.

## Privacy Considerations

**What gets sent to LangSmith:**
- User inputs (may contain sensitive data)
- Tool arguments
- LLM responses
- Guardrail decisions
- Risk scores

**Recommendations:**
- Use LangSmith's data redaction features
- Review LangSmith privacy policy
- Consider self-hosted alternatives for sensitive data
- Use PII guardrails before tracing

## Troubleshooting

### Traces Not Appearing

**Check 1: Environment Variable**
```bash
echo $LANGCHAIN_TRACING_V2  # Should be "true"
```

**Check 2: API Key**
- Ensure key starts with `lsv2_pt_`
- Check it's not expired in LangSmith settings

**Check 3: Network**
- Ensure you can reach `api.smith.langchain.com`
- Check firewall/proxy settings

**Check 4: App Logs**
- Look for LangSmith errors in Streamlit console
- Check if tracing is silently failing

### Partial Traces

If you see incomplete traces:
- Check for errors mid-execution
- Ensure all methods are decorated with `@traceable`
- Verify `get_current_run_tree()` returns valid tree

### Performance Impact

Tracing adds ~10-50ms overhead per trace:
- Minimal for most use cases
- Can disable for production if needed
- Async tracing coming soon

## Comparison: With vs Without LangSmith

### Without LangSmith
- Local audit logs only
- Limited visibility into execution
- Hard to debug guardrail behavior
- No historical analysis

### With LangSmith
- ✅ Full execution traces
- ✅ Visual timeline of guardrails
- ✅ Easy debugging
- ✅ Historical analysis
- ✅ Performance monitoring
- ✅ Team collaboration

## Next Steps

1. ✅ Enable tracing in app
2. ✅ Run test scenarios
3. ✅ Explore traces in dashboard
4. ✅ Add custom tags for organization
5. ✅ Set up alerts for errors
6. ✅ Share traces with team

## Resources

- **LangSmith Docs**: https://docs.smith.langchain.com
- **API Reference**: https://api.smith.langchain.com/redoc
- **Examples**: https://github.com/langchain-ai/langsmith-cookbook
- **Support**: https://github.com/langchain-ai/langsmith-sdk/issues

---

**Happy Tracing! 🚀**
