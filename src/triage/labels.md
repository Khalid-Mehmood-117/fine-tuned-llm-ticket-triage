# Label definitions

One ticket gets one label per field. If a ticket raises several issues, label the most urgent
issue (the one that would decide routing). Labels and reason are always in English, whatever the
ticket language.

## category
- billing: charges, invoices, payment methods, plan prices, double or unexpected charges. Not a request for money back on a purchase (that is refund).
- refund: the customer asks for money back for an order, item or service.
- shipping: delivery status, delays, lost or wrong address parcels, tracking, delivery damage before arrival.
- account_access: cannot log in, password reset, 2FA problems, locked or compromised account.
- technical_issue: app or device bug, crash, error message, feature not working, outage.
- product_question: how to use something, compatibility, specs, availability, before or after purchase.
- cancellation: the customer wants to cancel a subscription, plan, contract or order that has not shipped.
- complaint: dissatisfaction with service, staff, quality or policy where the main ask is to be heard or compensated, not a specific fix above.
- feature_request: asks for a new feature or change to the product.
- other: spam, wrong company, thank you notes, partnership offers, anything that fits nowhere else.

## priority
- urgent: risk to safety or health, legal threat or legal data request, or the customer is fully blocked from money or an essential service right now with harm ongoing.
- high: customer blocked from the core product or money taken wrongly, security concern, hard deadline within about 48 hours, or a strongly escalating repeat contact.
- medium: a real problem with a workaround, or a normal request that needs action (refund, cancellation, delivery delay).
- low: questions, feature requests, feedback, thank you notes, no action pressure.

## sentiment
- negative: frustrated, angry, disappointed, worried, sarcastic.
- neutral: factual, no clear emotion.
- positive: friendly, grateful, enthusiastic (a polite request with thanks is positive only if the warmth is clear).

## needs_human
True when the next step needs a person's judgment or authority: refund decisions, escalations,
safety, legal, security or fraud concerns, chargebacks, urgent priority, or an angry customer
threatening to leave after repeated failed contacts. False when an agent macro, knowledge base
article or simple routing is enough.

## suggested_action
- reply_with_kb_article: a standard answer or how-to article solves it.
- ask_for_details: the ticket does not contain enough information to act.
- route_to_billing: billing team needs to check or fix a charge or invoice.
- route_to_technical: technical team needs to investigate a bug or outage.
- route_to_shipping: shipping team needs to trace, re-ship or change a delivery.
- start_refund_review: open a refund case for a person to approve.
- reset_account_access: run the identity-checked access reset flow.
- process_cancellation: cancel the subscription, plan or unshipped order.
- escalate_to_supervisor: a senior agent should handle it (repeat failures, threats to leave, compensation demands).
- escalate_to_safety_legal: safety risk, injury, legal threat or legal data request.

## reason
One English sentence, at most 25 words, saying what the customer needs and why the labels fit.
