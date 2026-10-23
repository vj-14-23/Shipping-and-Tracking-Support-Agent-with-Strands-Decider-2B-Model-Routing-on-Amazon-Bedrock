# Strands Decider hackathon kit (AWS User Group Madurai). Every target runs ./kit <target>, the
# cross-platform runner (scripts/kit.py); on Windows use .\kit <target>. See ./kit help.
TARGET ?= local
MSG ?= Hello, what can you do?
SPLIT ?=
N ?= 20

.PHONY: venv tools agentcore-cli setup check-machine aws-login gh-login serve stop test run demo demo-bg demo-stop data bench deploy invoke destroy video article readme check publish status release

venv tools agentcore-cli setup check-machine aws-login gh-login serve stop test run demo-stop deploy destroy readme check status release:
	@./kit $@

demo demo-bg:
	@./kit $@ --target $(TARGET)

data:
	@./kit data $(NAME) --describe "$(DESCRIBE)" --fields "$(FIELDS)" --n $(N)

bench:
	@./kit bench $(if $(SPLIT),--split $(SPLIT),)

invoke:
	@./kit invoke "$(MSG)"

video:
	@./kit video --target $(TARGET)

article:
	@./kit article $(if $(DRAFT),--draft,)

publish:
	@./kit publish $(NAME)
