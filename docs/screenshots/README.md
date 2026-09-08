# Demo screenshots

Local GreenMail and Thunderbird. The mailbox is up only while
`make app-stack-up` is running. How to send mail: the root
[README](../../README.md).

1. Employee question (knowledge hit).

   ![Employee writes to support](01_employee_question_kb_hit.png)

2. Agent reply with a `Sources:` footer.

   ![Knowledge-hit reply](02_llm_answer_kb_hit.png)

3. Employee follow-up the knowledge base cannot answer.

   ![Follow-up that misses the knowledge base](03_employee_follow_up_kb_miss.png)

4. Knowledge-gap reply: `I don't know` and a `Ticket:` id.

   ![Knowledge-gap reply with ticket id](04_llm_answer_knowledge_gap.png)

5. Operator escalation digest for that ticket.

   ![Escalation digest](05_ticket_escalated.png)

Dify Studio Logs → Tracing for the knowledge-gap run (item 4).
Tool-node Input / Output is what the workflow wrote on MCP calls.

6. Tracing tab: node list, timings, and token counts.

   ![Dify tracing log](06_dify_tracing_log.png)

7. Workflow graph for that run.

   ![Dify workflow graph](07_dify_workflow_graph.png)

8. `list-user-tickets` (empty; no open ticket yet).

   ![list-user-tickets tool](08_dify_tool_list_user_tickets.png)

9. `create-ticket` after the knowledge miss.

   ![create-ticket tool](09_dify_tool_create_ticket.png)

10. `append-user-message` for the inbound mail.

    ![append-user-message tool](10_dify_tool_append_user_message.png)

11. `append-agent-message` for the `I don't know` reply.

    ![append-agent-message tool](11_dify_tool_append_agent_message.png)
