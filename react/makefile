.PHONY: all clean run

all: build

venv: requirements-lock.txt
	rm -rf venv; \
	python3 -m venv venv && \
	source venv/bin/activate && \
	pip install --upgrade pip && \
	pip install -r requirements-lock.txt && \
	touch venv;

nvenv: venv
	rm -rf nvenv; \
	source venv/bin/activate && \
	nodeenv nvenv;

node_modules: nvenv package.json
	rm -rf node_modules && \
	source nvenv/bin/activate && \
	npm install;

clean:
	rm -rf build node_modules nvenv venv

build: node_modules $(shell find src) $(shell find public)
	rm -rf build && \
	source nvenv/bin/activate && \
	npm run build

run: node_modules
	source nvenv/bin/activate && \
	npm start
