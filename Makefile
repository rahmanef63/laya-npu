.PHONY: help install start test bench lint build clean

help:
	@echo "laya-npu"
	@echo ""
	@echo "  make install   install dependencies, model, and shortcuts"
	@echo "  make start     run the app on http://localhost:8649"
	@echo "  make test      policy and accuracy harnesses (needs the model)"
	@echo "  make bench     re-measure backend latency"
	@echo "  make lint      python syntax check and svelte-check"
	@echo "  make build     build the frontend into web/dist"
	@echo "  make clean     remove build output and caches"
	@echo ""
	@echo "Windows users: use install.cmd and laya-npu.cmd instead."

install:
	@test -f install.sh || (echo "run this from the repo root"; exit 1)
	./install.sh

start:
	@test -f start.sh || (echo "run this from the repo root"; exit 1)
	./start.sh

test:
	python tests/test_policy.py
	python tests/test_accuracy.py

bench:
	python tests/bench_backends.py

lint:
	@echo "== python syntax"
	@for f in server/*.py tests/*.py portal/app.py register.py; do \
		python3 -c "import ast,sys; ast.parse(open('$$f').read())" || exit 1; \
	done
	@echo "== svelte + typescript"
	npx svelte-check --tsconfig ./tsconfig.json --threshold error

build:
	npm install
	npm run build

clean:
	rm -rf web/dist .svelte-kit .venv
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	@echo "cleaned; node_modules and models/ left alone on purpose"
