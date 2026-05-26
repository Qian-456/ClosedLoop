import os

# Disable LangSmith tracing during tests to avoid long teardown hangs
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
