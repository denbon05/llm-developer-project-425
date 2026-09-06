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
