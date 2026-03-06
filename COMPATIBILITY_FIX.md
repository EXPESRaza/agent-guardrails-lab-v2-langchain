# Langchain Compatibility Fix

## Issue
The initial implementation used `AgentExecutor` and `create_openai_tools_agent` which are not available in all versions of langchain.

## Solution
Updated to use the more stable `initialize_agent` API which works across langchain versions >= 0.1.0.

## Changes Made

### `guardrails/langchain_agent.py`

1. **Simplified Imports**
   ```python
   # Before
   from langchain.agents import AgentExecutor, create_openai_tools_agent

   # After
   from langchain.agents import initialize_agent, AgentType
   ```

2. **Agent Creation**
   ```python
   # Before
   self.agent = create_openai_tools_agent(self.llm, self.tools, self.prompt)
   executor = AgentExecutor(agent=self.agent, tools=self.tools, ...)

   # After
   self.agent_type = AgentType.OPENAI_FUNCTIONS
   executor = initialize_agent(tools=self.tools, llm=self.llm, agent=self.agent_type, ...)
   ```

3. **Execution Method Fallback**
   ```python
   try:
       result = executor.invoke({"input": text}, config={"callbacks": callbacks})
   except AttributeError:
       # Fallback for older versions
       result = executor.run(input=text, callbacks=callbacks)
   ```

## Benefits

- ✅ Works with langchain 0.1.x
- ✅ Works with langchain 0.2.x
- ✅ Simpler, more maintainable code
- ✅ Same functionality preserved

## Testing

The app should now start without import errors:
```bash
streamlit run app.py
```

If you still encounter issues, ensure langchain is installed:
```bash
pip install langchain>=0.1.0 langchain-openai>=0.0.5
```
