.PHONY: all clean react run shell test

SHELL = /bin/bash
FILE = main.py
ARGS =

all: react venv resources

react:
	cd react && make

venv: requirements-lock.txt
	rm -rf venv && \
	python3 -m venv venv && \
	source venv/bin/activate && \
	pip install --upgrade pip && \
	pip install -r requirements-lock.txt && \
	touch venv;

resources: react/build $(shell find assets)
	rm -rf resources && \
	mkdir resources && \
	cp -r react/build resources/react && \
	cp -r assets/static/* resources

clean:
	rm -rf build/*
	rm -rf build
	cd react && make clean
	rm -rf resources
	rm -rf venv

test: all
	source venv/bin/activate && \
	python3 -B -m pytest test -v

shell: all
	source venv/bin/activate && python3

build: all setup.py
	rm -rf build/*
	rm -rf build
	source venv/bin/activate && \
	python3 -B setup.py bdist_dmg

run: all
	source venv/bin/activate && \
	python3 -B $(FILE) $(ARGS)
