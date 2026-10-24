import pathlib

p = pathlib.Path("README.md")
content = p.read_text(encoding="utf-8")

old = "python -m unittest test_comparison_agent.TestComparisonAgentUnit test_report_agent.TestReportAgentUnit test_research_agent.TestResearchAgentUnit test_conversational_api.TestConversationalResearchAPI -v"
new = "python -m unittest tests.test_comparison_agent.TestComparisonAgentUnit tests.test_report_agent.TestReportAgentUnit tests.test_research_agent.TestResearchAgentUnit tests.test_conversational_api.TestConversationalResearchAPI -v"

if old in content:
    content = content.replace(old, new, 1)
    p.write_text(content, encoding="utf-8")
    print("README test command patched OK")
else:
    print("NOT FOUND")
