# Requirements Document

## Introduction

A shipping and tracking support agent for an online store that helps customers check shipment status, handle delivery exceptions, and request address changes through a natural-language chat interface. The agent uses **Strands Decider 2B** with the **model routing** pattern: simple queries (status lookups, estimated delivery) are handled by a fast, low-cost model, while complex or sensitive interactions (lost packages, delivery disputes, address change requests) are routed to a more capable model. The agent integrates with a configurable real carrier API and is deployed on Amazon Bedrock AgentCore Runtime.

## Glossary

- **Agent**: The shipping and tracking support agent powered by Strands Agents and Amazon Bedrock.
- **Carrier_API**: The external shipping carrier API (e.g., EasyPost, ShipEngine, or AfterShip) used to retrieve shipment data.
- **Decider**: The Strands Decider 2B model that classifies each customer query and returns a routing score.
- **Fast_Model**: A lightweight, low-cost LLM used for simple, deterministic queries.
- **Smart_Model**: A more capable LLM used for complex, ambiguous, or high-stakes queries.
- **Shipment**: A record returned by the Carrier_API containing tracking number, status, carrier, estimated delivery date, and event history.
- **Delivery_Exception**: A Shipment event indicating a failed delivery attempt, address issue, damage, or loss.
- **Customer**: The end user interacting with the Agent via the chat interface.
- **Session**: A single conversation between a Customer and the Agent.
- **Routing_Decision**: The output of the Decider that classifies a query as `simple` or `complex` with a confidence score.

---

## Requirements

### Requirement 1: Shipment Status Lookup

**User Story:** As a customer, I want to ask about the status of my shipment, so that I can know where my package is and when it will arrive.

#### Acceptance Criteria

1. WHEN a customer provides a tracking number (6–40 alphanumeric characters) or order ID (1–20 alphanumeric characters), THE Agent SHALL query the Carrier_API and return the current shipment status, carrier name, and estimated delivery date.
2. WHEN the Carrier_API returns a valid Shipment, THE Agent SHALL present the most recent tracking event as a human-readable sentence that includes the event description, location, and timestamp.
3. IF the Carrier_API returns a valid Shipment but does not include an estimated delivery date, THEN THE Agent SHALL display all other available shipment details and indicate that the estimated delivery date is not yet available.
4. IF the Carrier_API returns no shipment for the provided identifier, THEN THE Agent SHALL inform the customer that the tracking number was not found and ask them to verify it.
5. IF the Carrier_API is unavailable, THEN THE Agent SHALL inform the customer of the temporary issue and advise them to try again within 15 minutes.
6. THE Agent SHALL respond to the customer with the shipment status within 5 seconds of receiving the tracking number or order ID.

---

### Requirement 2: Model Routing via Strands Decider 2B

**User Story:** As a store operator, I want the agent to use an inexpensive model for straightforward questions and a smarter model for complex issues, so that I minimize cost while maintaining quality where it matters.

#### Acceptance Criteria

1. WHEN a customer message is received, THE Decider SHALL classify it as either `simple` or `complex` and return a Routing_Decision paired with a numeric confidence score in the range 0.0 to 1.0 before the Agent selects a model.
2. IF the Routing_Decision is `simple` AND the confidence score is 0.5 or above, THEN THE Agent SHALL process the request using the Fast_Model.
3. IF the Routing_Decision is `complex` AND the confidence score is 0.5 or above, THEN THE Agent SHALL process the request using the Smart_Model.
4. IF the Decider returns a confidence score below 0.5 for the chosen category, THEN THE Agent SHALL process the request using the Smart_Model regardless of the Routing_Decision label.
5. IF the Decider is unavailable or returns a malformed response, THEN THE Agent SHALL process the request using the Smart_Model and record the failure reason in the log entry.
6. WHEN a customer message is processed, THE Agent SHALL log an entry containing the Routing_Decision label, confidence score, and the model selected for that request.

---

### Requirement 3: Delivery Exception Handling

**User Story:** As a customer, I want the agent to explain delivery problems clearly and tell me what my options are, so that I can resolve issues without calling customer support.

#### Acceptance Criteria

1. WHEN a Shipment contains a Delivery_Exception event, THE Agent SHALL route the query to the Smart_Model via the Decider.
2. WHEN a Delivery_Exception is detected, THE Agent SHALL describe the exception using non-technical terms drawn directly from the exception event data and present the applicable resolution options from the set (re-delivery, hold at location, carrier contact).
3. IF a Shipment status indicates the package is lost (no carrier scan recorded for more than 7 days after the estimated delivery date), THEN THE Agent SHALL inform the customer that the package may be lost, state the number of days elapsed since the estimated delivery date, and offer to initiate a carrier investigation.
4. WHEN a customer reports a damaged package, THE Agent SHALL prompt the customer to provide the order ID and a damage description of no more than 1000 characters, and SHALL reject the submission with an error message indicating missing or invalid input if either field is absent or the description exceeds 1000 characters.
5. WHEN a customer has provided a valid order ID and damage description, THE Agent SHALL present the available resolution actions (replacement or refund) and ask the customer to select one before proceeding.
6. IF the Agent is about to initiate an irreversible action (carrier investigation, replacement, or refund), THEN THE Agent SHALL present a summary of the action and require an explicit customer confirmation before executing the action.
7. IF a customer declines all presented resolution options for a Delivery_Exception, THEN THE Agent SHALL acknowledge the declination and inform the customer that they may contact support for further assistance.

---

### Requirement 4: Address Change Requests

**User Story:** As a customer, I want to request an address change for an in-transit shipment, so that I can redirect my package if needed.

#### Acceptance Criteria

1. WHEN a customer requests an address change for an in-transit shipment, THE Decider SHALL classify the query as `complex`.
2. WHEN the Routing_Decision is `complex` for an address change, THE Agent SHALL use the Smart_Model to confirm the request details with the customer before calling the Carrier_API.
3. IF the Carrier_API confirms a successful address change, THEN THE Agent SHALL inform the customer of the updated delivery address and revised estimated delivery date.
4. IF the Carrier_API cannot fulfill the address change (e.g., shipment already out for delivery), THEN THE Agent SHALL explain the limitation and suggest alternatives (hold at carrier facility, neighbor delivery).
5. WHEN the Agent is ready to submit an address change to the Carrier_API, THE Agent SHALL present the new address to the customer and require explicit confirmation before submitting; IF the customer does not confirm within 5 minutes or cancels the request, THEN THE Agent SHALL discard the pending change and notify the customer that the request was not submitted.
6. WHEN a customer provides a new delivery address, THE Agent SHALL verify that the address includes at minimum a street, city, postal code, and country, and SHALL prompt the customer for any missing fields before proceeding.
7. IF the Carrier_API call for an address change fails due to a network error or timeout (exceeding 10 seconds), THEN THE Agent SHALL notify the customer of the failure and advise them to retry or contact the carrier directly.

---

### Requirement 5: Configurable Carrier API Integration

**User Story:** As a developer, I want the carrier integration to be configurable, so that I can switch providers without rewriting the agent.

#### Acceptance Criteria

1. WHEN the Agent initializes, THE Agent SHALL read the `CARRIER_PROVIDER` and `CARRIER_API_KEY` values from environment variables, where "not set" means the variable is either absent or set to an empty string.
2. THE Agent SHALL designate EasyPost as the default carrier provider, and SHALL support EasyPost, ShipEngine, and AfterShip as valid values for `CARRIER_PROVIDER`.
3. IF `CARRIER_PROVIDER` is not set at initialization, THEN THE Agent SHALL use EasyPost as the carrier provider and SHALL emit a warning message indicating that `CARRIER_PROVIDER` was not set and the default provider is in use.
4. IF `CARRIER_API_KEY` is not set at initialization, THEN THE Agent SHALL refuse to process any carrier requests and SHALL emit an error message indicating that the API key is missing, without including the key value.
5. THE Agent SHALL support registration of additional carrier providers such that adding a new provider requires no changes to the criteria files defining existing provider behavior.
6. THE Agent SHALL never include the `CARRIER_API_KEY` value in log output, API responses, or error messages.

---

### Requirement 6: Session Context and Conversation Memory

**User Story:** As a customer, I want the agent to remember my order details within a conversation, so that I don't have to repeat myself.

#### Acceptance Criteria

1. WHILE a Session is active, THE Agent SHALL retain up to 20 tracking numbers and order IDs mentioned by the customer and reuse them in follow-up queries without asking the customer to repeat them; if the 20-item limit is reached, THE Agent SHALL retain the most recently mentioned items and discard the oldest.
2. WHEN a customer asks a follow-up question about the same shipment, THE Agent SHALL answer using the already-retrieved Shipment data without re-querying the Carrier_API, provided the Shipment data was retrieved within the last 5 minutes of the current Session; IF the cached Shipment data is older than 5 minutes, THEN THE Agent SHALL re-query the Carrier_API to retrieve updated Shipment data before responding.
3. WHEN a customer explicitly requests a refresh of Shipment data, THE Agent SHALL re-query the Carrier_API and update the retained Shipment data for that tracking number or order ID.
4. WHEN a Session ends due to 30 minutes of customer inactivity or an explicit session-termination signal, THE Agent SHALL discard all retained tracking numbers, order IDs, and Shipment data associated with that Session.
5. WHEN a new Session starts, THE Agent SHALL not carry over any Shipment or personal data from a previous Session.

---

### Requirement 7: Transparency and Decision Logging

**User Story:** As a store operator, I want to see why the agent chose a particular model, so that I can tune routing thresholds and audit behavior.

#### Acceptance Criteria

1. THE Agent SHALL expose a `decisions` field in every chat response containing the list of Routing_Decisions made during that turn, where the list contains between 0 and 50 entries inclusive, and is empty when no routing decision was made during that turn.
2. WHEN a Routing_Decision is logged, THE Agent SHALL record the query category (`simple` or `complex`), confidence score as a decimal value between 0.0 and 1.0 inclusive, selected model identifier, and latency as a non-negative integer in milliseconds.
3. THE demo UI SHALL display the Routing_Decision panel alongside the chat, showing each decision's query category, confidence score, selected model, and latency in a structured list that updates with each chat response.
